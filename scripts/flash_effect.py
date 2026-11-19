#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把灯效写入主板 flash（掉电保存，不需要 OpenRGB 常驻）

原理（源码 MSIMotherboard185Controller::Update(bool save)）:
  - direct_mode == true 时，发送的是 per-LED 数据包，save 参数被完全忽略
  - direct_mode == false 时，才走 `data.save_data = save` 那条路径
  - save_data=1 时固件把当前配置写入 flash，断电后保留

因此必须使用硬件效果模式（Static/Breathing/Rainbow wave 等），
不能用 Direct 逐灯珠模式。

用法:
  python flash_effect.py                 # 写白色 Static
  python flash_effect.py FF0000          # 写红色 Static
  python flash_effect.py rainbow         # 写 Rainbow wave
  python flash_effect.py breathing       # 写 Breathing
  python flash_effect.py list            # 列出可用模式
"""
import struct
import sys
import time

import openrgb_sdk as o
import openrgb_ctl as ctl

# 硬件效果模式（能写 flash 的那些，值为 MSI_MODE_*）
FLASHABLE = [
    "Static", "Breathing", "Flashing", "Double flashing", "Lightning",
    "Meteor", "Color ring", "Planetary", "Double meteor", "Energy",
    "Blink", "Clock", "Color pulse", "Color shift", "Color wave",
    "Marquee", "Rainbow wave", "Visor", "Rainbow flashing",
    "Color ring double flashing", "Stack", "Fire",
]


def flash_mode(c, did, dev, mode_name, rgb=(255, 255, 255), speed=None, brightness=None):
    """把指定硬件效果模式写入主板 flash"""
    idx, m = ctl.find_mode(dev, mode_name)
    if idx is None:
        raise SystemExit("未找到模式 %r\n可用: %s" % (
            mode_name, ", ".join(x["name"] for x in dev["modes"])))

    if m["name"].lower() == "direct":
        raise SystemExit(
            "Direct 模式无法写入 flash（源码中 save 参数在 direct_mode 下被忽略）。\n"
            "请改用 Static / Breathing / Rainbow wave 等硬件效果模式。")

    n = len(dev["leds"])

    # 1) 先把颜色铺进 zone 的 colors 数组
    #    （非 Direct 模式下 UpdateLed 只用 zones[zone].colors[0]，但先铺满更稳妥）
    c.update_leds(did, [rgb] * n)
    time.sleep(0.3)

    # 2) 切到目标模式：DeviceUpdateMode -> SetDirectMode(false) -> DeviceUpdateLEDs
    #    这条路径会把 SetMode/SetZoneColor 写进 data 包，然后 Update(save=false) 下发
    ctl.apply_mode(c, did, dev, idx, speed=speed, brightness=brightness)
    time.sleep(0.6)

    # 3) 再发一次同模式，但用 SAVEMODE(1102) 包
    #    服务端会走 ProcessRequest_RGBController_UpdateSaveMode(..., save_mode=true)
    #    -> controllers[idx]->SaveMode() -> DeviceSaveMode() -> controller->Update(true)
    #    -> data.save_data = 1 -> 固件写 flash
    payload = ctl.mode_payload(idx, m, speed=speed, brightness=brightness)
    c.send(did, o.SAVEMODE, payload)
    time.sleep(1.0)

    return idx, m


def main():
    if len(sys.argv) < 2:
        arg = "FFFFFF"
    else:
        arg = sys.argv[1]

    if arg.lower() == "list":
        c, did, dev = ctl.connect()
        try:
            for name in FLASHABLE:
                idx, m = ctl.find_mode(dev, name)
                if idx is not None:
                    print("[%2d] %s" % (idx, name))
        finally:
            c.close()
        return

    # 模式名 or 颜色
    if arg.lower() in ("rainbow", "breathing", "static", "fire", "colorwave",
                       "color wave", "rainbow wave", "clock", "stack", "visor"):
        mode_name = {"rainbow": "Rainbow wave", "colorwave": "Color wave",
                     "color wave": "Color wave", "static": "Static"}.get(
                         arg.lower(), arg.title() if arg.lower() != "rainbow wave" else "Rainbow wave")
        rgb = (255, 255, 255)
    elif len(arg) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in arg):
        mode_name = "Static"
        rgb = ctl.hex2rgb(arg)
    else:
        mode_name = arg
        rgb = (255, 255, 255)

    c, did, dev = ctl.connect()
    try:
        idx, m = flash_mode(c, did, dev, mode_name, rgb)
        print("已写入 flash: 模式=%s 颜色=RGB%s" % (m["name"], rgb))

        # 回读确认
        time.sleep(0.4)
        dev2 = o.parse_device(c.controller_data(did))
        print("回读 active_mode =", dev2["modes"][dev2["active_mode"]]["name"])
    finally:
        c.close()


if __name__ == "__main__":
    main()
