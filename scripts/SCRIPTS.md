# scripts/ — 配套脚本

[`../docs/guide.md`](../docs/guide.md) 的参考实现。**只在微星 B760M BOMBER DDR4 (MS-7D90) 上实测通过。**

## 文件

| 文件 | 作用 | 依赖 |
|---|---|---|
| `openrgb_sdk.py` | OpenRGB SDK 协议客户端（手写，纯标准库，protocol 6） | 无 |
| `openrgb_ctl.py` | 命令行控制：`info` / `zones` / `static` / `zone` / `off` / `rainbow` / `breathing` / `white` / `mode` / `save` | `openrgb_sdk.py` |
| `flash_effect.py` | 把硬件效果模式写进主板 flash（掉电保持） | 上面两个 |
| `flash_precheck.py` | 写 flash 前的只读安全体检 | 上面两个 |
| `rgb.py` | 按需启动器：临时起 OpenRGB → 设灯效 → 写 flash → 关掉 | 全部 |
| `kill_openrgb.py` | 关闭 OpenRGB（能处理 Session 隔离的进程） | 无 |
| `calib_leds.py` | 灯珠标定：每 N 颗刷一色，反推每扇几颗 | 上面两个 |

## 先改硬编码路径

`openrgb_ctl.py` / `rgb.py` / `kill_openrgb.py` 里写死了本机路径，换机器必须改：

```python
PY      = r"C:\Users\<you>\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
OPENRGB = r"C:\Program Files\OpenRGB\OpenRGB.exe"
```

## 典型用法

```bash
# 看设备 / 分区
python rgb.py info
python rgb.py zones

# 设纯白并写进 flash（之后不需要 OpenRGB 常驻）
python rgb.py white

# 换彩虹波并写进 flash
python rgb.py rainbow

# 标定每扇灯珠数：每 4 颗一色，然后问用户看到几段颜色
python calib_leds.py 4
```

## 前置条件

1. OpenRGB 已安装，且已手工填过每路 ARGB 的灯珠数（见 guide 第 4 节）
2. 微星平台需要 OpenRGB 带 `--server` 启动，或让 `rgb.py` 自己拉起
3. 写 flash 前先跑一次 `python flash_precheck.py` 确认灯区尺寸与接线一致

## 重要限制

- **`zone` 子命令写不进 flash**。分区设色走 Direct 逐灯珠模式，而 Direct 模式在固件层被排除在 flash 保存路径外（见 guide 第 6 节）。分区设色只在 OpenRGB 运行期间有效。
- **`Direct` 模式永远无法写 flash**，`flash_effect.py` 会直接拒绝执行。
- **这些脚本是微星专用的**，按 185 字节 HID 报文和 `MSI_MODE_*` 枚举实现。华硕平台要改用 OpenRGB 自己的 `SaveMode()` 通路，协议不同（见 guide 第 7 节）。

## 协议实现要点（想自己重写的话）

```
包头 16 字节（小端）：magic "ORGB" + uint32 dev_id + uint32 pkt_id + uint32 pkt_size
协议版本 6，默认端口 6742
```

握手顺序有讲究：

1. 先发 `REQ_PROTOCOL_VERSION(40)`，**数据体里必须带 `uint32 6`**。只发空包会得到 protocol=0，之后 `CONTROLLER_COUNT` 就不会返回设备 ID 数组。
2. `SET_CLIENT_NAME(50)` 的数据体是 **`uint16 长度 + 字符串（含 \0）`**，不是 uint32。
3. `SET_CLIENT_FLAGS(52)` 发 `uint32 1`。
4. 要调 ProfileManager / SettingsManager，必须置 `REQUEST_LOCAL_CLIENT(1<<16)`，且连接来自 127.0.0.1。

几个容易错的地方：

- `REQ_CONTROLLER_DATA(1)` 的回复数据**开头多一个 `uint32 reply_size`**，漏读这 4 字节后面全错位。
- `UPDATEMODE(1101)` 数据体 = `uint32 data_size_pkt` + `int32 mode_idx` + 完整 mode 结构。**只发 mode_idx 是错的**，会静默失败。
- `SAVEMODE(1102)` 的 `data_size_pkt` 必须等于整个数据体长度（含自己这 4 字节），否则返回 `ERROR_INVALID_DATA` 且不报错。
- 颜色格式 `RGBColor = (b<<16)|(g<<8)|r`，**低字节是 R**。
- 服务端会主动推 `SIGNALUPDATE(1150)` 和 `ACK(10)`，收包时要按 pkt_id 过滤，否则错位。
