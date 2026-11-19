# OpenRGB ARGB 风扇统一管控 —— 实战指南

> 从「7 个 RGB 风扇各吹各的」到「不装任何灯控软件、开机就是纯白」的完整落地记录。
>
> 基于微星 B760M BOMBER DDR4 + 7 个 ARGB 风扇实测。文末附华硕平台差异。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 这个仓库解决什么问题

大多数人的 RGB 风扇是**分线器并联**接在主板 ARGB 接口上的，于是遇到三个典型困境：

1. **厂商软件互斥**：华硕奥创不认微星主板，微星 Mystic Light 不认华硕主板
2. **必须常驻后台**：原厂软件不启动，灯效就回到默认的彩虹循环
3. **灯珠数对不上**：ARGB 是可寻址的，软件不知道你接了几个风扇、每个几颗灯

本仓库给出一套**跨厂商、可脚本化、能写进主板 flash 掉电保持**的方案。

---

## 快速开始（五步）

```
1. 装 OpenRGB 1.1
2. 确认主板灯控被识别（微星 1462:7D90 / 华硕 0B05:19AF）
3. Zone Initialization 里手工填每路 ARGB 灯珠数（必须真实键盘输入！）
4. 选一个硬件效果模式（Static / Breathing / Rainbow…），不要用 Direct
5. 点「保存到设备」→ 关掉 OpenRGB → 断电重启 → 灯效仍在 = 成功
```

做完第 5 步，**OpenRGB 可以卸载或永不启动**，灯效由主板固件负责。

详细步骤见下方目录，或直接读 [完整文档](docs/guide.md)。

---

## 目录

| 章节 | 内容 |
|---|---|
| [1. 硬件勘察](docs/guide.md#1-先勘察硬件别急着装软件) | 查主板型号、ARGB 接口额定电流、两个必踩的供电坑 |
| [2. 工具选型](docs/guide.md#2-工具怎么选) | OpenRGB vs SignalRGB vs 原厂软件；为什么奥创中心不行 |
| [3. 安装](docs/guide.md#3-安装-openrgb) | 1601 错误、崩溃退出码的成因 |
| [4. 首次配置](docs/guide.md#4-首次配置灯珠数量必须手工填) | **QSpinBox 自动化填值无效的坑**（本文最有价值的一条） |
| [5. 灯珠标定](docs/guide.md#5-标定每扇几颗灯珠并联还是串联) | 三轮颜色实验反推并联拓扑与每扇灯珠数 |
| [6. 写 flash](docs/guide.md#6-核心怎么把灯效写进主板-flash) | 为什么 Direct 模式永远存不进；SAVEMODE 包格式 |
| [7. 华硕差异](docs/guide.md#7-华硕平台有什么不同) | 独立 COMMIT 命令、官方 `@save` 标注、奥创覆盖问题 |
| [8. 自启 vs flash](docs/guide.md#8-开机自启-vs-写-flash该选哪个) | 两种方案对比；OpenRGB 会删你自启快捷方式的坑 |
| [9. 实测数据](docs/guide.md#9-附实测数据速查) | 设备参数、SDK 协议要点、22 个可写模式 |
| [10. 踩坑清单](docs/guide.md#10-踩坑清单按踩到的顺序) | 12 条，按踩到的顺序排列 |

---

## 配套脚本

`scripts/` 下是配套实现，**只在微星 B760M BOMBER DDR4 上实测通过**：

| 脚本 | 作用 |
|---|---|
| `openrgb_sdk.py` | OpenRGB SDK 协议客户端（手写，纯标准库，protocol 6） |
| `openrgb_ctl.py` | 命令行控制：设色、切模式、查状态 |
| `flash_effect.py` | 把硬件效果模式写进主板 flash |
| `flash_precheck.py` | 写 flash 前的只读安全体检 |
| `rgb.py` | 按需启动器：临时起 OpenRGB → 设灯效 → 写 flash → 关掉 |
| `kill_openrgb.py` | 关闭 OpenRGB（处理 Session 隔离的进程） |
| `calib_leds.py` | 灯珠标定：每 N 颗刷一色，反推每扇几颗 |

用法见 [scripts/SCRIPTS.md](scripts/SCRIPTS.md)。

---

## 核心结论（如果只读一段）

### Direct 模式写不进 flash

这是全文最关键的发现。看微星驱动源码：

```cpp
// MSIMotherboard185Controller::Update(bool save)
if (direct_mode) {
    // 只发 per-LED 数据包，save 参数被完全忽略
} else {
    ReadSettings();
    data.save_data = save;   // ← 只有这里置 1 才会让固件写 flash
    hid_send_feature_report(dev, &data, sizeof(data));
}
```

**逐灯珠自定义图案无法持久化**，只有预设效果（Static / Breathing / Rainbow…）能写进主板。

### 自动化填灯珠数会失败

`QSpinBox` 的 UIA `set_value()` 只改显示文本，不触发 Qt 内部 `value` 变更，所以 `ResizeZone()` 从未被调用，配置文件里存的还是 0。**必须用真实键盘输入。**

验证方法：看 `%APPDATA%\OpenRGB\Configuration.json` 里 `controllers[0].leds` 的**条目总数**，成功时应该等于 `1 + 各路灯珠数之和`。

---

## 适用范围

- ✅ 微星主板（Mystic Light 私有 HID 协议，185 字节报文）
- ✅ 华硕主板（Aura USB 控制器，需先卸载奥创中心）
- ⚠️ 其他厂商（华擎/技嘉/华硕旧世代）OpenRGB 也有支持，但本文未实测
- ❌ 12V RGB（4-pin）接口只能整条同色，无法逐灯珠控制

---

## 贡献

如果你在其他主板上验证过，欢迎提 PR 补充实测数据。特别需要：

- 华硕 B650 系列的实际 PID 与灯区数量
- 技嘉/华擎平台的 flash 写入行为
- 串联式 ARGB 集线器的型号推荐（能解决并联同色问题）

---

## License

[MIT](LICENSE)

---

*本文基于 2026-11 的一次真实部署整理。*
