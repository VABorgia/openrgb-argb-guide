#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RGB 灯效按需控制 —— 平时不需要 OpenRGB 常驻

工作流程:
  1. 检查 SDK 端口 6742 是否在监听
  2. 没监听就临时启动 OpenRGB（--server，不显示窗口）
  3. 下发灯效
  4. 若是可写 flash 的模式，顺手写进主板（掉电保存）
  5. 关闭临时启动的 OpenRGB

用法:
  python rgb.py white              # 纯白（写入 flash，之后不启动也保持）
  python rgb.py static FF0000      # 纯红
  python rgb.py rainbow            # 彩虹波浪（写入 flash）
  python rgb.py breathing          # 白色呼吸（写入 flash）
  python rgb.py off                # 关灯
  python rgb.py zones              # 查看区域
  python rgb.py info               # 查看设备详情
  python rgb.py keep on|off        # 是否让 OpenRGB 保持运行（默认改完就关）
"""
import os
import socket
import subprocess
import sys
import time

DIR = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
# 可用环境变量 OPENRGB_EXE 覆盖（默认安装路径）
OPENRGB = os.environ.get("OPENRGB_EXE", r"C:\Program Files\OpenRGB\OpenRGB.exe")
HOST, PORT = "127.0.0.1", 6742


def port_open(host=HOST, port=PORT, timeout=1.0):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except OSError:
        return False


def start_openrgb(wait=15.0):
    """后台启动 OpenRGB --server，等到端口就绪"""
    if port_open():
        return None
    if not os.path.exists(OPENRGB):
        raise SystemExit("找不到 OpenRGB: %s" % OPENRGB)
    creation = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    p = subprocess.Popen(
        [OPENRGB, "--server", "--startminimized"],
        cwd=os.path.dirname(OPENRGB),
        creationflags=creation,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    t0 = time.time()
    while time.time() - t0 < wait:
        if port_open():
            time.sleep(0.5)
            return p
        time.sleep(0.25)
    raise SystemExit("OpenRGB 启动超时（%.0f 秒内端口未就绪）" % wait)


def stop_openrgb():
    """按端口找到进程并终止（Session 隔离下 taskkill 无效，用 WinAPI）"""
    script = os.path.join(DIR, "kill_openrgb.py")
    if os.path.exists(script):
        subprocess.run([PY, script], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=30)
        return


# 能写 flash 的模式（硬件效果模式，非 Direct）
FLASHABLE = {
    "static", "white", "rainbow", "breathing", "flashing", "lightning",
    "meteor", "color ring", "planetary", "double meteor", "energy", "blink",
    "clock", "color pulse", "color shift", "color wave", "marquee",
    "rainbow wave", "visor", "rainbow flashing", "stack", "fire",
}


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    keep = False
    if args[0].lower() == "keep":
        # 只改配置，不启动不关闭
        on = len(args) > 1 and args[1].lower() in ("on", "1", "true")
        set_keep(on)
        print("OpenRGB 保持运行:", "开" if on else "关（改完自动关闭）")
        return

    cmd = args[0].lower()

    # 只读命令不需要写 flash，也不该关闭用户手动开的 OpenRGB
    readonly = cmd in ("info", "zones")

    started = None
    try:
        started = start_openrgb()

        r = subprocess.run(
            [PY, os.path.join(DIR, "openrgb_ctl.py")] + args,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=120)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if out:
            print(out)
        if err:
            print(err, file=sys.stderr)

        # 写 flash（让效果掉电保持，之后不需要 OpenRGB）
        # 注意：zone 分区设色本质上是 Direct 逐灯珠模式，无法写 flash
        if not readonly and cmd in FLASHABLE:
            mode_name = "Static" if cmd in ("static", "white", "off") else None
            flash_args = [PY, os.path.join(DIR, "flash_effect.py")]
            if mode_name:
                if cmd in ("static", "white") and len(args) > 1:
                    flash_args.append(args[1])
                elif cmd == "white":
                    flash_args.append("FFFFFF")
                elif cmd == "off":
                    flash_args.append("000000")
                else:
                    flash_args.append("FFFFFF")
            else:
                flash_args.append({"rainbow": "rainbow", "breathing": "breathing"}.get(cmd, cmd))
            fr = subprocess.run(flash_args, capture_output=True, text=True,
                                encoding="utf-8", errors="replace",
                                env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                                timeout=120)
            fo = (fr.stdout or "").strip()
            if "已写入 flash" in fo:
                print("[flash] 已写入主板，掉电保持，无需 OpenRGB 常驻")
            elif fo:
                print("[flash]", fo.replace("\n", " | "))
        elif cmd == "zone":
            print("[提示] 分区设色走 Direct 逐灯珠模式，无法写入主板 flash；")
            print("       重启后失效，需要 OpenRGB 常驻才能保持。")

    finally:
        if started is not None:
            time.sleep(0.3)
            stop_openrgb()
            print("[OpenRGB] 已关闭（按需启动模式）")


def set_keep(on):
    """记录偏好（写个小文件）"""
    p = os.path.join(DIR, ".rgb_keep")
    with open(p, "w", encoding="utf-8") as f:
        f.write("1" if on else "0")


if __name__ == "__main__":
    main()
