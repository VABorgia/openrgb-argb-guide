# 用 OpenRGB 统一管控 ARGB 风扇，并把灯效写进主板（掉电保持）

> 一次真实落地记录：微星 B760M BOMBER DDR4 + 7 个 ARGB 风扇，从零到「不装任何灯控软件、开机就是纯白」。
> 文末附华硕平台的差异说明。全部结论来自实测，不是照抄文档。

---

## 0. TL;DR — 五步

```
1. 装 OpenRGB 1.1
2. 让它识别出主板灯控（微星走 HID，华硕走 HID，都不需要刷固件）
3. Zone Initialization 里手工填每路 ARGB 的灯珠数（必须用键盘真实输入）
4. 选一个硬件效果模式（Static / Breathing / Rainbow …），不要用 Direct
5. 点「保存到设备」→ 关掉 OpenRGB → 断电重启 → 灯效仍在 = 成功
```

做完第 5 步之后，**OpenRGB 可以完全卸载或永不启动**，灯效由主板固件负责。

---

## 1. 先勘察硬件，别急着装软件

### 1.1 查主板型号

```powershell
wmic baseboard get manufacturer,product,serialnumber
# 或
Get-CimInstance Win32_BaseBoard | Format-List Manufacturer,Product,Version
```

本次实测：`Micro-Star International Co., Ltd. B760M BOMBER DDR4 (MS-7D90)`

### 1.2 查主板有几个 ARGB 接口、每路能带多少

必须查**官方手册**，不要猜。以微星 B760M BOMBER DDR4 为例：

| 接口 | 类型 | 额定 | 能力 |
|---|---|---|---|
| `JARGB_V2_1` / `JARGB_V2_2` | 5V 3-pin | 3A (5V) | 最多 240 颗可寻址 LED，兼容 ARGB Gen1/Gen2 |
| `JRGB1` | 12V 4-pin | 3A (12V) | 最长 2 米 5050 灯条，**不能逐灯珠控制** |
| `CPU_FAN1` | 风扇 | 2A / 24W | — |
| `SYS_FAN1` / `SYS_FAN2` | 风扇 | 1A / 12W | **默认 DC 模式** |

> ⚠️ 两个容易踩的坑：
> 1. **SYS_FAN 默认是 DC 模式**。PWM 风扇插上去会异响、转速跳动、低速转不动。要进 BIOS → HARDWARE MONITOR 手动改成 PWM。
> 2. **风扇数量 > 接口数量时必然有分线器**。如果是无源分线器，把 5 个风扇（单个 0.2~0.3A）全并到一个 1A 的 SYS_FAN 上，总电流 1.0~1.5A **已经超限**。需要带 SATA 独立供电的集线器。

### 1.3 确认主板灯控被系统识别

```powershell
Get-PnpDevice -Class HIDClass | Where-Object { $_.InstanceId -like "*VID_1462*" }
# 微星：USB\VID_1462&PID_7D90\...   ← 1462 = MSI 的 USB VID
# 华硕：USB\VID_0B05&PID_19AF\...   ← 0B05 = ASUS 的 USB VID
```

看到这个设备，说明主板 RGB 控制器走的是 USB HID 私有协议，OpenRGB 能直接接管，**不需要装驱动、不需要刷固件**。

---

## 2. 工具怎么选

| 工具 | 优点 | 缺点 | 适合谁 |
|---|---|---|---|
| **OpenRGB** | 免费开源、跨平台、支持写主板 flash、有 SDK 可脚本化 | 界面简陋、灯珠数要手工填 | **推荐**，尤其想「设一次永久生效」 |
| SignalRGB | 效果最炫、6000+ 设备、游戏联动 | 核心功能要 Pro 订阅（$5.99/月）；常驻占资源 | 想玩灯效、不在乎常驻 |
| 厂商原厂软件 | 兼容性最稳 | 臃肿、只能管自家生态、常驻后台抢控制权 | 只想简单用 |

### 关于「奥创中心能不能用」

**不能。** Armoury Crate 是华硕自家软件，Aura Sync 只认华硕主板的 RGB 控制器。微星主板走 Mystic Light 私有协议，奥创根本不会把它列为可控设备——装上去主板灯效那一栏是空的。

反过来，华硕主板上如果装了奥创，它的 `LightingService` 会在每次开机时把华硕自己的配置刷回控制器，**直接覆盖掉 OpenRGB 写进 flash 的状态**。所以在华硕平台用 OpenRGB 前，务必先卸载/禁用奥创。

---

## 3. 安装 OpenRGB

### 3.1 下载

官方发布页：<https://openrgb.org/releases.html>
（2026-10 起 release notes 迁到 Codeberg，但下载仍走 GitHub Releases）

本次用的是 `OpenRGB_1.1_Windows_64.msi`。**开源项目没有代码签名证书，安装时 Windows 会报「未知发布者」，属正常。** 完整性请用 SHA256 对齐官方 asset digest，不要看签名。

### 3.2 安装时的权限问题

如果安装器返回 **ExitCode 1601**，日志里有：

```
连接到服务器失败。错误: 0x80070005
Failed to connect to server.
MainEngineThread is returning 1601
```

这不是安装包坏了，是**当前进程没有权限访问 Windows Installer 服务**。用管理员权限运行即可。

同理，OpenRGB 启动时崩溃、退出码 `-1073740791`（`0xC0000409`）、事件日志显示 `ucrtbase.dll` 出错，是因为它要写 `%APPDATA%\OpenRGB`（配置和日志）但被拒绝了。**给足写权限就能解决**。

---

## 4. 首次配置：灯珠数量必须手工填

### 4.1 为什么会弹 Zone Initialization

5V ARGB 是可寻址灯带，控制器**无法自动探测上面有几颗灯珠**。所以 OpenRGB 第一次识别到 ARGB 接口时会弹窗让你填。

本次弹窗内容：

| 控制器 | 区域 | 大小 |
|---|---|---|
| MSI B760M BOMBER DDR4 (MS-7D90) | `JRAINBOW1` | 待填（上限 200） |
| MSI B760M BOMBER DDR4 (MS-7D90) | `JRAINBOW2` | 待填（上限 240） |

> 注意：接口丝印叫 `JARGB_V2_1`，OpenRGB 里显示叫 `JRAINBOW1`，是同一个东西。

### 4.2 ⚠️ 最大的坑：自动化填值不生效

如果你用 UI 自动化（UIA / pywinauto 之类）往那个数字框里 `set_value("56")`，**界面上会显示 56，但保存后配置文件里还是 0**。

原因：那个控件是 Qt 的 `QSpinBox`，UIA 的 `ValuePattern` 只改了显示文本，没有触发 Qt 内部的 `value` 变更信号。所以 `ResizeZone()` 从来没被调用过。

**唯一可靠的做法是真键盘输入**：

```
1. 点击那个数字框（真实鼠标坐标点击，不是 elementId 点击）
2. Ctrl+A 全选
3. 键盘输入数字（SendInput）
4. 截图确认框里显示的是你要的数字
5. 点「保存并关闭」
```

### 4.3 怎么验证真的写进去了

保存后去看这个文件：

```
%APPDATA%\OpenRGB\Configuration.json
```

判断标准看 `controllers[0].leds` 的**条目总数**：

- 失败时：`leds` 只有 1 条（只有 12V 接口那颗占位）
- 成功时：`leds` = 1 + JRAINBOW1 颗数 + JRAINBOW2 颗数

本次成功时是 **113 条**（1 + 56 + 56），后来按实测改成 8/8 后变成 17 条（1 + 8 + 8）。

> 另外两个文件别搞混：
> - `OpenRGB.json` — 程序设置（语言、服务器端口、profile 自动加载），**不含灯区尺寸**
> - `profiles\*.json` — 灯效快照（模式 + 每颗颜色），也不含灯区尺寸
> - `Configuration.json` — **只有它存灯区尺寸**

---

## 5. 标定：每扇几颗灯珠？并联还是串联？

这一步决定了你后续能不能做「分区控制」，非常关键。

### 5.1 方法：下发分段颜色，让用户看实际效果

准备 8 种差异明显的颜色：

```python
PALETTE = [
    (255, 0, 0), (255, 128, 0), (255, 255, 0), (0, 255, 0),
    (0, 255, 255), (0, 0, 255), (128, 0, 255), (255, 255, 255),
]
# 红、橙、黄、绿、青、蓝、紫、白
```

然后按「每 N 颗换一个颜色」刷进去，问用户看到几个颜色段。

### 5.2 本次三轮实验（完整证据链）

| 轮次 | 下发内容 | 用户观察 | 推论 |
|---|---|---|---|
| 1 | 每 **4 颗**一色循环 | 每个风扇显示 **2 段**颜色（红+橙） | 每扇 = 4 × 2 = **8 颗** |
| 2 | 路1=16颗（8红+8绿）<br>路2=40颗（5色各8颗） | 底面 2 个**全红**<br>其余 5 个**全蓝** | 所有风扇只用到了**前 8 个数据** → 每路是**并联** |
| 3 | 两路各 8 颗，8 色互不相同 | 每个风扇显示 **8 种不同颜色** | 每个风扇完整收到同一份 8 颗数据 → **确认并联** |

**第 2 轮的关键反证**：如果一路是串联，底面应该是「第 1 个红、第 2 个绿」。实际两个都是红，说明它们收到的是同一份数据 → 并联。

### 5.3 并联意味着什么

```
JARGB_V2_1 ──[并联分线器]── 底面风扇 ×2（各 8 颗）
JARGB_V2_2 ──[并联分线器]── 后面板 ×1 + 右侧板 ×2 + 顶面水冷 ×2（共 5 个）
JRGB1      ── 空（12V 4-pin 未接）
```

**同一路分线器上的多个风扇，永远显示完全相同的图案，无法各自独立变色。** 这是并联的电路特性，换任何软件都改不了。

想每个风扇独立控制，只能换**串联式 ARGB 集线器**（每个风扇单独一根数据线）。

不过实际影响不大：彩虹波之类的效果在 8 颗上跑，每个风扇都是一整圈完整渐变，看起来仍然正常。

### 5.4 标定完记得改回真实颗数

```python
# 通过 OpenRGB SDK 的 RESIZEZONE 包改尺寸
c.send(dev_id, 1000, struct.pack("<ii", zone_idx, new_size))
```

改完 `Configuration.json` 里 `leds` 条目数会同步变化。

---

## 6. 核心：怎么把灯效写进主板 flash

### 6.1 为什么 Direct 模式不行

这是本次最关键的发现，直接看源码。

**微星（`MSIMotherboard185Controller::Update(bool save)`）**：

```cpp
// :760  direct_mode 分支 —— save 参数被完全忽略
if(direct_mode) {
    // 只发 per-LED 数据包，根本没有 save_data 这个字段
}
// :840  非 direct_mode 分支 —— 这里才处理 save
else {
    ReadSettings();
    data.save_data = save;          // ← 置 1 才让固件写 flash
    hid_send_feature_report(dev, &data, sizeof(data));
    // Windows 上 Mystic Light 要连发两次 report
    memcpy(&data, &new_data, ...);
    data.save_data = save;
    hid_send_feature_report(dev, &data, sizeof(data));
}
```

注释原文（`:402-409`）：

> *The last byte of the packet is the save flag. This byte is stored as a zero in the data flash, but is set to 1 at the protocol level to tell the firmware to save the active configuration to flash.*

**结论：Direct 逐灯珠模式永远存不进 flash，只有硬件效果模式（Static / Breathing / Rainbow …）能写。**

### 6.2 正确的写入链路

```
GUI 点「保存到设备」
  → OpenRGBDevicePage::on_DeviceSaveButton_clicked()
  → if(modes[active_mode].flags & MODE_FLAG_MANUAL_SAVE) device->SaveMode()
  → RGBController::SaveMode()  →  DeviceSaveMode()
  → controller->Update(true)   →  data.save_data = 1  →  固件写 flash
```

注意那个 `MODE_FLAG_MANUAL_SAVE` 判断：**只有带这个标志的模式，按钮才是亮的**。微星这边 Direct 模式没有这个标志，所以按钮本来就是灰的——这本身就是个提示。

### 6.3 用 SDK 脚本写（无需 GUI）

如果想脚本化，协议是：

```
包 ID 1102 = SAVEMODE
数据体 = uint32 data_size_pkt + int32 mode_idx + 完整 mode 结构
```

`data_size_pkt` **必须等于整个数据体的长度（含自己这 4 字节）**，否则服务端直接返回 `ERROR_INVALID_DATA`，而且**不会报错给你看**，静默失败。

完整流程三步：

```python
# 1) 先铺色（非 Direct 模式下，固件只用 zone 的第 0 颗颜色驱动整圈，所以铺满更稳妥）
c.update_leds(dev_id, [rgb] * n_leds)
time.sleep(0.3)

# 2) 切模式 —— 走 DeviceUpdateMode() → SetDirectMode(false) → DeviceUpdateLEDs() → Update(false)
apply_mode(c, dev_id, dev, mode_idx, speed=..., brightness=...)
time.sleep(0.6)

# 3) 发 SAVEMODE 包 —— 走 SaveMode() → DeviceSaveMode() → Update(true)
c.send(dev_id, 1102, mode_payload(mode_idx, mode, speed, brightness))
time.sleep(1.0)
```

### 6.4 验收

**唯一可信的验收方式是**：

```
关掉 OpenRGB 进程 → 拔电源/断电重启 → 看灯
```

本次实测：写入 `Static` + 纯白 → 杀掉 OpenRGB（确认端口 6742 已关闭、进程已退出）→ 用户确认「灯没灭也没变」→ **成功**。

---

## 7. 华硕平台有什么不同

同样的思路，但协议不一样。

### 7.1 硬件

以 PRIME B650M-K 为例（[官方规格](https://www.asus.com.cn/motherboards-components/motherboards/prime/prime-b650m-k/techspec/)）：

| 接口 | 数量 | 说明 |
|---|---|---|
| Addressable Gen 2 header（5V 3-pin） | 2 个 | 逐灯珠，单口最大 3A(5V)，支持 WS2812B |
| Aura RGB header（12V 4-pin） | 1 个 | 整条同色 |

跟微星是同一套配置：2 路 ARGB + 1 路 12V RGB。

### 7.2 写入机制更「正规」

华硕在 OpenRGB 源码里是**官方标注支持保存**的：

```cpp
// RGBController_AsusAuraMainboard.cpp:18
@save :white_check_mark:      // ← 官方标注
@direct :white_check_mark:
@effects :white_check_mark:
```

写入方式是一条独立的 COMMIT 命令，而不是在报文末尾塞一个标志位：

```cpp
// AsusAuraMainboardController.cpp:227-247
void AuraMainboardController::SendCommit() {
    usb_buf[0x00] = 0xEC;
    usb_buf[0x01] = 0x3F;   // AURA_MAINBOARD_CONTROL_MODE_COMMIT
    usb_buf[0x02] = 0x55;
    hid_write(dev, usb_buf, 65);
}
```

而且 `DeviceSaveMode()` 会顺手把**关机灯效**也写一遍：

```cpp
void RGBController_AuraMainboard::DeviceSaveMode() {
    DeviceUpdateMode();            // 下发当前效果
    DeviceUpdateShutdownEffect();  // 写关机灯效（仅对板载 FIXED 灯珠生效）
    ((AuraMainboardController*)controller)->SendCommit();
}
```

### 7.3 差异对照

| | 微星 B760M | 华硕 B650-K |
|---|---|---|
| USB ID | `1462:7D90` | `0B05:19AF`（B650 世代基本都是这个） |
| 写入方式 | 185 字节包最后一字节 `save_data=1` | 独立 COMMIT 命令 `0xEC 0x3F 0x55` |
| 需要特定模式 | 是，必须非 Direct | 是，同样只有非 Direct 带 `MANUAL_SAVE` |
| 关机灯效 | 无此概念 | 会额外写一次 |
| 源码标注 | 无 `@save` 标注 | **`@save :white_check_mark:`** |
| ARGB 上限 | 200 / 240 颗 | 500 颗/口 |
| 最大干扰源 | 无（MSI Center 不常驻抢控制） | **奥创中心的 `LightingService` 会覆盖 flash** |

华硕的 PID 白名单（`AsusAuraUSBControllerDetect.cpp:26-34`）：`0x18F3 / 0x1939 / 0x19AF / 0x1AA6 / 0x1BED`。源码注释写明适用范围：*"applies to most AMD and Intel mainboards from the x570 chipset onwards"*。

### 7.4 华硕平台上必须注意

1. **先卸载奥创中心**。不卸就等于白写——开机时会被华硕自己的服务刷回去。
2. **BIOS 里 Aura 选项保持默认**，别开 Stealth Mode 之类的强制关灯。
3. 如果写完 flash 重启失效，先试**用管理员权限运行 OpenRGB**。有用户报告过华硕主板刷 BIOS 后出现这个问题，管理员权限能解决（[SuperUser 案例](https://superuser.com/questions/1782985/asus-tuf-gaming-x570-wifi-motherboard-not-remembering-rgb-settings-when-powered)）。

---

## 8. 开机自启 vs 写 flash，该选哪个

| | 写 flash | OpenRGB 常驻/自启 |
|---|---|---|
| 需要软件在跑吗 | **不需要** | 需要 |
| 支持逐灯珠自定义图案吗 | **不支持**（只有预设效果） | 支持 |
| 支持分区独立设色吗 | 不支持 | 支持（Direct 模式） |
| 断电保持 | 是 | 是（靠 profile 自动加载） |
| 稳定性 | 高（固件负责） | 依赖软件不崩、不被抢控制权 |
| 开机速度影响 | 无 | 略有（要等它加载 profile） |

**推荐组合**：

- 日常固定灯效（比如纯白/纯蓝）→ **写 flash**，然后把 OpenRGB 的开机自启关掉
- 偶尔想玩效果 → 需要时手动启动 OpenRGB（或做个按需启动脚本）

### 踩坑：OpenRGB 会删掉你的自启快捷方式

如果你在 `Startup` 目录放了 `OpenRGB.lnk`，OpenRGB 启动时会读自己的 `AutoStart.enabled` 设置（默认 false），发现是 false 就调 `DisableAutoStart()`，**把你的 `OpenRGB.lnk` 删掉**。

解决办法：换个文件名（比如 `OpenRGB-RGB.lnk`），就不会被识别成它自己管理的那一项。

---

## 9. 附：实测数据速查

### 9.1 本次设备

| 项 | 值 |
|---|---|
| 主板 | MSI B760M BOMBER DDR4 (MS-7D90) |
| 灯控设备 | `USB\VID_1462&PID_7D90\<序列号>`（HIDClass） |
| 固件 | `AP/LD 0.4 / 1.5` |
| 设备描述 | `MSI Mystic Light Device (185-byte)` |
| 风扇 | 7 个（后面板 1 + 右侧板 2 + 顶面水冷 2 + 底面 2） |
| 每扇灯珠 | 8 颗 |
| 灯区 | `JRGB1`=1（空置占位）、`JRAINBOW1`=8、`JRAINBOW2`=8，共 17 颗 |
| 接线 | 两路均为**并联**分线器 |

### 9.2 OpenRGB SDK 协议要点（手写客户端用）

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
- 颜色格式 `RGBColor = (b<<16)|(g<<8)|r`，**低字节是 R**。
- 服务端会主动推 `SIGNALUPDATE(1150)` 和 `ACK(10)`，收包时要按 pkt_id 过滤，否则错位。

### 9.3 23 个模式里哪些能写 flash

微星 B760M 实测共 23 个模式，其中 **22 个能写 flash**（除 `Direct`）：

```
Static / Breathing / Flashing / Double flashing / Lightning / Meteor /
Color ring / Planetary / Double meteor / Energy / Blink / Clock /
Color pulse / Color shift / Color wave / Marquee / Rainbow wave / Visor /
Rainbow flashing / Color ring double flashing / Stack / Fire
```

**`Direct` 不能写**，因为它的 flags 只有 `HAS_PER_LED_COLOR(32)`，没有 `MANUAL_SAVE(256)`。

---

## 10. 踩坑清单（按踩到的顺序）

| # | 现象 | 原因 | 解法 |
|---|---|---|---|
| 1 | MSI 安装器 ExitCode 1601 | 无权访问 Windows Installer 服务 | 管理员权限运行 |
| 2 | OpenRGB 启动崩溃，退出码 `-1073740791` | 无法写 `%APPDATA%\OpenRGB` | 给足写权限 |
| 3 | 自动化填的数字保存后变 0 | QSpinBox 的 UIA set_value 只改文本 | 用真实键盘输入 |
| 4 | 改了 `OpenRGB.json` 灯区尺寸没反应 | 尺寸存在 `Configuration.json`，不是 `OpenRGB.json` | 改对文件 |
| 5 | 手改 `Configuration.json` 后 GUI 还是灰的 | 只改 `leds_count` 不会重建 LED 列表 | 必须走 `ResizeZone()` |
| 6 | 「保存到设备」按钮是灰的 | 当前模式没有 `MANUAL_SAVE` 标志（Direct 就是这样） | 换成 Static 等硬件效果模式 |
| 7 | 发 SAVEMODE 包没反应也不报错 | `data_size_pkt` 不等于整个数据体长度 | 让它等于 `4 + 4 + mode_body_len` |
| 8 | 重启后灯效回到默认 | 写 flash 时处于 Direct 模式 | 先切非 Direct 模式再写 |
| 9 | `Startup\OpenRGB.lnk` 自己消失了 | OpenRGB 的 `AutoStart.enabled=false` 会删掉同名快捷方式 | 换个文件名 |
| 10 | 两个风扇只能同色，无法分别控制 | 并联分线器 | 换串联式集线器，或用软件规避 |
| 11 | PWM 风扇接 SYS_FAN 有异响 | SYS_FAN 默认 DC 模式 | 进 BIOS 改成 PWM |
| 12 | 华硕平台写完 flash 重启失效 | 奥创中心开机时刷回自己的配置 | 卸载/禁用奥创 |

---

## 11. 参考

- OpenRGB 官网：<https://openrgb.org/>
- OpenRGB 源码：<https://github.com/CalcProgrammer1/OpenRGB>
  - 微星：`Controllers/MSIMotherboardController/MSIMotherboard185Controller/`
  - 华硕：`Controllers/AsusAuraUSBController/`
  - 协议：`NetworkProtocol.h`、`NetworkServer.cpp`
- OpenRGB Wiki（Aura USB 协议）：<https://openrgb-wiki.readthedocs.io/en/latest/asus/ASUS-Aura-USB/>
- OpenDeviceDB（设备支持查询）：<https://opendevicedb.org/>
- 微星 B760M BOMBER DDR4 规格：<https://www.msi.cn/Motherboard/B760M-BOMBER-DDR4/Specification>
- 华硕 PRIME B650M-K 规格：<https://www.asus.com.cn/motherboards-components/motherboards/prime/prime-b650m-k/techspec/>
- 风扇转速控制（与灯效互不干扰）：<https://getfancontrol.com/>

---

*本文基于 2026-11 的一次真实部署整理。硬件配置：MSI B760M BOMBER DDR4 + RTX 4060 + 7 个 ARGB 风扇。*
