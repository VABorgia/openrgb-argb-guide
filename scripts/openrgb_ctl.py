#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenRGB 灯效控制工具

用法:
  python openrgb_ctl.py info                       # 查看设备/区域/模式
  python openrgb_ctl.py static RRGGBB              # 全部灯珠统一静态色
  python openrgb_ctl.py zone <idx|名称> RRGGBB     # 只设某个区域
  python openrgb_ctl.py zones                      # 列出区域及其灯珠区间
  python openrgb_ctl.py mode <名称> [speed] [bright]  # 切换效果模式
  python openrgb_ctl.py rainbow                    # 彩虹波
  python openrgb_ctl.py off                        # 全部熄灭
  python openrgb_ctl.py save                       # 把当前状态存成 profile
"""
import struct
import sys
import time

import openrgb_sdk as o

MODE_FLAG_HAS_SPEED = 1
MODE_FLAG_HAS_BRIGHTNESS = 16
MODE_FLAG_HAS_PER_LED_COLOR = 32
MODE_FLAG_HAS_MODE_SPECIFIC_COLOR = 64
MODE_FLAG_HAS_RANDOM_COLOR = 128

MODE_COLORS_NONE = 0
MODE_COLORS_PER_LED = 1
MODE_COLORS_MODE_SPECIFIC = 2
MODE_COLORS_RANDOM = 3


def hex2rgb(s):
    s = s.strip().lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def rgb2color(rgb):
    r, g, b = rgb
    return (b << 16) | (g << 8) | r


def connect():
    c = o.ORGB()
    c.handshake()
    n, ids = c.controller_count()
    if not n:
        raise SystemExit("没有检测到设备")
    did = ids[0]
    dev = o.parse_device(c.controller_data(did))
    return c, did, dev


def zone_ranges(dev):
    """返回 {名称: (起始索引, 数量)}，按 zones 顺序累加"""
    out = {}
    start = 0
    for z in dev["zones"]:
        out[z["name"]] = (start, z["leds_count"])
        start += z["leds_count"]
    return out


def find_mode(dev, name):
    for i, m in enumerate(dev["modes"]):
        if m["name"].lower() == name.lower():
            return i, m
    return None, None


def mode_payload(mode_idx, m, speed=None, brightness=None, colors=None, color_mode=None):
    """UPDATEMODE(1101) 的数据体：data_size_pkt(u32) + mode_idx(i32) + mode 结构(protocol 6)"""
    speed = m["speed"] if speed is None else speed
    brightness = m["brightness"] if brightness is None else brightness
    cols = m["colors"] if colors is None else colors
    color_mode = m["color_mode"] if color_mode is None else color_mode

    name = (m["name"] + "\0").encode("utf-8")
    body = bytearray()
    body += struct.pack("<H", len(name))
    body += name
    body += struct.pack(
        "<I" "I I" "I I" "I I" "I I" "I I",
        m["flags"],
        m["speed_min"], m["speed_max"],
        m["brightness_min"], m["brightness_max"],
        m["colors_min"], m["colors_max"],
        speed, brightness,
        m["direction"], color_mode,
    )
    body += struct.pack("<H", len(cols))
    for c in cols:
        body += struct.pack("<I", rgb2color(c) if isinstance(c, tuple) else c)

    total = 4 + 4 + len(body)          # size 字段 + mode_idx + mode 结构
    return struct.pack("<Ii", total, mode_idx) + bytes(body)


def apply_mode(c, did, dev, mode_idx, speed=None, brightness=None, colors=None,
               color_mode=None):
    m = dev["modes"][mode_idx]
    c.send(did, o.UPDATEMODE, mode_payload(mode_idx, m, speed, brightness, colors, color_mode))
    time.sleep(0.4)


def set_direct(c, did, dev):
    idx, m = find_mode(dev, "Direct")
    if idx is None:
        c.set_custom_mode(did)
        time.sleep(0.4)
        return dev["active_mode"]
    apply_mode(c, did, dev, idx)
    return idx


def fill(dev, rgb, zone=None):
    total = len(dev["leds"])
    colors = [(0, 0, 0)] * total
    if zone is None:
        colors = [rgb] * total
    else:
        ranges = zone_ranges(dev)
        if isinstance(zone, int):
            z = dev["zones"][zone]
            start, cnt = ranges[z["name"]]
        else:
            start, cnt = ranges[zone]
        for i in range(start, start + cnt):
            colors[i] = rgb
    return colors


def do_static(c, did, dev, rgb, zone=None):
    set_direct(c, did, dev)
    c.update_leds(did, fill(dev, rgb, zone))
    time.sleep(0.25)
    c.update_mode(did)
    time.sleep(0.6)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1].lower()
    c, did, dev = connect()
    try:
        if cmd == "info":
            o.show(dev, did)
        elif cmd == "zones":
            for i, z in enumerate(dev["zones"]):
                start, cnt = zone_ranges(dev)[z["name"]]
                print("[%d] %-14s %3d 颗  LED 索引 %d..%d" % (i, z["name"], cnt, start, start + cnt - 1))
        elif cmd == "static":
            rgb = hex2rgb(sys.argv[2]) if len(sys.argv) > 2 else (255, 255, 255)
            do_static(c, did, dev, rgb)
            print("全部 %d 颗 LED = RGB%s" % (len(dev["leds"]), rgb))
        elif cmd == "zone":
            key = sys.argv[2]
            zone = int(key) if key.isdigit() else key
            rgb = hex2rgb(sys.argv[3])
            do_static(c, did, dev, rgb, zone)
            print("区域 %s = RGB%s" % (key, rgb))
        elif cmd == "off":
            do_static(c, did, dev, (0, 0, 0))
            print("已熄灭")
        elif cmd == "rainbow":
            idx, m = find_mode(dev, "Rainbow wave")
            if idx is None:
                print("没有 Rainbow wave 模式")
                return
            apply_mode(c, did, dev, idx)
            print("已切换到 Rainbow wave")
        elif cmd == "breathing":
            idx, m = find_mode(dev, "Breathing")
            if idx is None:
                print("没有 Breathing 模式")
                return
            # 呼吸模式本身没有 mode-specific 颜色，先铺底色再切模式
            c.update_leds(did, [(255, 255, 255)] * len(dev["leds"]))
            time.sleep(0.2)
            apply_mode(c, did, dev, idx, speed=1, brightness=10)
            print("已切换到 Breathing（白色呼吸）")
        elif cmd == "white":
            do_static(c, did, dev, (255, 255, 255))
            print("全部 %d 颗 LED = 纯白" % len(dev["leds"]))
        elif cmd == "mode":
            name = sys.argv[2]
            speed = int(sys.argv[3]) if len(sys.argv) > 3 else None
            bright = int(sys.argv[4]) if len(sys.argv) > 4 else None
            idx, m = find_mode(dev, name)
            if idx is None:
                print("未找到模式:", name)
                print("可用:", ", ".join(x["name"] for x in dev["modes"]))
                return
            apply_mode(c, did, dev, idx, speed, bright)
            print("已切换到模式", m["name"], "speed=", speed, "brightness=", bright)
        elif cmd == "save":
            import openrgb_sdk
            c.send(did, o.SAVEMODE)
            time.sleep(0.3)
            print("已下发 SaveMode（写入设备）")
        else:
            print(__doc__)
    finally:
        c.close()


if __name__ == "__main__":
    main()
