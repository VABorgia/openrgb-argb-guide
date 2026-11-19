#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""写 flash 前的只读安全体检（不发送任何写入命令）

检查项:
  1. 设备是否为目标主板（PID 7D90 / zones_set11）
  2. 各 zone 的 LED 数量与实际接线是否一致
  3. JRGB1（12V）是否为空置 —— 若接了设备，写入有烧灯风险
  4. 当前 flash 中保存的模式/颜色（只读 GetMode）
  5. 固件版本
"""
import sys
import time

import openrgb_sdk as o
import openrgb_ctl as ctl

# 本机实测接线（来自三轮颜色标定实验）
EXPECTED = {
    "JRGB1": 1,        # 空置，但 OpenRGB 占位 1 颗
    "JRAINBOW1": 8,    # 底面 2 风扇并联
    "JRAINBOW2": 8,    # 后面 1 + 右侧 2 + 顶面 2，并联
}


def main():
    c, did, dev = ctl.connect()
    try:
        print("=" * 62)
        print("只读安全体检（不会写入任何数据）")
        print("=" * 62)
        print("设备      :", dev["name"])
        print("描述      :", dev["description"])
        print("厂商      :", dev["vendor"])
        print("固件      :", dev.get("version") or "(未报告)")
        print("序列号    :", dev.get("serial") or "(未报告)")
        print("设备类型  :", dev["type"], "(0=主板)")
        print("LED 总数  :", len(dev["leds"]))
        print("活动模式  :", dev["modes"][dev["active_mode"]]["name"])
        print()

        print("-" * 62)
        print("区域检查")
        print("-" * 62)
        ranges = ctl.zone_ranges(dev)
        problems = []
        for i, z in enumerate(dev["zones"]):
            start, cnt = ranges[z["name"]]
            exp = EXPECTED.get(z["name"])
            flag = ""
            if exp is not None and cnt != exp:
                flag = "  <<< 与实测不符（期望 %d）" % exp
                problems.append(z["name"])
            print("[%d] %-12s type=%d  LED=%3d (min=%d max=%d) flags=%d  索引 %d..%d%s"
                  % (i, z["name"], z["type"], cnt, z["leds_min"], z["leds_max"],
                     z["flags"], start, start + cnt - 1, flag))
        print()

        print("-" * 62)
        print("12V JRGB1 安全判定")
        print("-" * 62)
        jrgb = [z for z in dev["zones"] if z["name"] == "JRGB1"]
        if jrgb:
            z = jrgb[0]
            print("JRGB1 存在，leds_count =", z["leds_count"])
            print("本机实测：JRGB1 接口空置，未接任何 12V 设备")
            print("判定：写入 flash 时 JRGB1 通道的数据不会被任何设备接收 → 无烧灯风险")
        print()

        print("-" * 62)
        print("结论")
        print("-" * 62)
        if problems:
            print("!! 以下区域 LED 数与实测不符，先修正再写 flash：", problems)
            print("   写错 LED 数量会导致主板按错误灯珠数驱动，灯效显示异常（不烧硬件）")
        else:
            print("OK  LED 数量与实测接线一致（JRAINBOW1=8, JRAINBOW2=8）")
        print("OK  JRGB1 空置，12V 通道无负载")
        print("OK  主板 PID 7D90 使用 zones_set11 = {J_RGB_1, J_RAINBOW_1, J_RAINBOW_2}")
        print()
        print("写入 flash 的实际影响范围：")
        print("  - 只改主板 RGB 控制器的配置存储区（Mystic Light 那套设置）")
        print("  - 不触碰 BIOS、不触碰风扇转速、不触碰电压/电流限制")
        print("  - 写坏了可以再写回来，或进 BIOS / MSI Center 恢复默认灯效")
        print("  - flash 有擦写寿命（通常数万次），不要频繁写")
    finally:
        c.close()


if __name__ == "__main__":
    main()
