#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""灯珠数量标定：把每路 LED 按固定块长刷成不同颜色，用来反推单个风扇的灯珠数。

用法:
  python calib_leds.py            # 默认块长 4，8 色循环
  python calib_leds.py 8          # 块长 8
"""
import sys
import time

import openrgb_sdk as o
import openrgb_ctl as ctl

# 8 个高辨识度颜色，按顺序循环
PALETTE = [
    ("红", (255, 0, 0)),
    ("橙", (255, 96, 0)),
    ("黄", (255, 255, 0)),
    ("绿", (0, 255, 0)),
    ("青", (0, 255, 255)),
    ("蓝", (0, 0, 255)),
    ("紫", (160, 0, 255)),
    ("白", (255, 255, 255)),
]


def block_pattern(n, block):
    """返回长度 n 的颜色数组：每 block 颗 LED 一种颜色，颜色按 PALETTE 循环"""
    return [PALETTE[(i // block) % len(PALETTE)][1] for i in range(n)]


def main():
    block = int(sys.argv[1]) if len(sys.argv) > 1 else 4

    c, did, dev = ctl.connect()
    try:
        # 先切 Direct（逐灯控制模式）
        ctl.set_direct(c, did, dev)
        time.sleep(0.4)
        dev = o.parse_device(c.controller_data(did))
        n = len(dev["leds"])
        ranges = ctl.zone_ranges(dev)

        colors = [(0, 0, 0)] * n
        pat = block_pattern(n, block)
        for name in ("JRAINBOW1", "JRAINBOW2"):
            if name not in ranges:
                continue
            start, cnt = ranges[name]
            for i in range(start, start + cnt):
                colors[i] = pat[i - start]

        c.update_leds(did, colors)
        time.sleep(0.3)
        c.update_mode(did)
        time.sleep(1.0)

        # 回读确认
        dev = o.parse_device(c.controller_data(did))
        print("模式:", dev["modes"][dev["active_mode"]]["name"])
        print("块长:", block, "颗/块")
        print("颜色顺序:", " → ".join(x[0] for x in PALETTE))
        for name in ("JRGB1", "JRAINBOW1", "JRAINBOW2"):
            if name in ranges:
                s, cnt = ranges[name]
                print("%-10s LED %3d..%3d  共 %d 颗" % (name, s, s + cnt - 1, cnt))
        print()
        print("前 12 颗的颜色:")
        for i in range(min(12, n)):
            print("  LED %2d = %s" % (i, dev["colors"][i]))
    finally:
        c.close()


if __name__ == "__main__":
    main()
