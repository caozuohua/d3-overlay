# D3OA — Diablo 3 Overlay Assistant

> 🛡️ 暗黑破坏神3 透明叠加增强助手 — 零内存注入，安全合法

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2B-lightgrey.svg)]()

---

## ✨ 项目简介

D3OA 是一款基于 **透明窗口叠加技术** 的 Diablo 3 游戏辅助工具。通过 Win32 API 创建位于游戏窗口上方的透明图层，在 **不修改游戏内存、不注入 DLL、不 hook 游戏进程** 的前提下，为玩家提供实时信息增强。

### 核心特性

| 特性 | 说明 |
|------|------|
| 🛡️ **零注入安全** | 不读写游戏内存，不注入 DLL，不修改游戏文件 |
| 👻 **透明叠加** | 使用 `WS_EX_LAYERED` 实现像素级透明窗口 |
| 🖱️ **点击穿透** | 鼠标操作完全穿透叠加层，不影响游戏操作 |
| 📊 **合法数据源** | Blizzard 公开 API + 游戏日志文件 + 截图 OCR |
| 🔌 **插件架构** | 模块化插件系统，社区可轻松扩展 |
| 🐍 **Python + C** | Python 逻辑层 + C 性能层，兼顾效率与性能 |

---

## 📸 界面预览

```
┌──────────────────────────────────────────────────┐
│                  Diablo 3 游戏画面                  │
│                                                    │
│                          ┌────────────────────┐   │
│                          │  ⏱ 秘境计时器        │   │
│                          │  03:42.15            │   │
│                          ├────────────────────┤   │
│                          │  📋 构筑信息          │   │
│                          │  野蛮人 · 旋风斩     │   │
│                          │  巅峰: 847           │   │
│                          ├────────────────────┤   │
│                          │  👹 复仇怪追踪        │   │
│                          │  无复仇怪在追踪中     │   │
│                          ├────────────────────┤   │
│                          │  📊 秘境进度          │   │
│                          │  ████████░░ 78%      │   │
│                          │  Boss 预估: 1:32     │   │
│                          └────────────────────┘   │
└──────────────────────────────────────────────────┘
```

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────┐
│                  D3OA 主进程                      │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ GameMon  │  │  Config   │  │  PluginMgr    │  │
│  │ 游戏监控  │  │  配置管理  │  │  插件管理器    │  │
│  └────┬─────┘  └────┬─────┘  └──────┬────────┘  │
│       │              │               │            │
│  ┌────▼──────────────▼───────────────▼────────┐  │
│  │            Overlay Manager                  │  │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ │  │
│  │  │计时器│ │构筑表│ │进度条│ │复仇怪│ │热键 │ │  │
│  │  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ │  │
│  └────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────┐  │
│  │        C Extension (overlay_core)           │  │
│  │  Win32 API · 透明窗口 · 截图捕获 · 像素处理   │  │
│  └────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.10+ | 主逻辑、UI 渲染、数据处理 |
| 性能层 | C (CPython 扩展) | Win32 API 调用、截图捕获、像素处理 |
| 窗口管理 | Win32 API | `SetWindowLong`, `SetLayeredWindowAttributes` |
| 渲染 | Pygame | 叠加层 UI 渲染 |
| 数据源 | Blizzard D3 API | 角色信息、排行榜（公开接口） |
| 配置 | JSON | 用户配置与插件配置 |

---

## 📁 项目结构

```
d3-overlay/
├── README.md                    # 项目文档
├── LICENSE                      # MIT 许可证
├── requirements.txt             # Python 依赖
├── config/
│   └── default.json             # 默认配置
├── docs/
│   ├── TECHNICAL.md             # 技术文档 — 架构、API、扩展指南
│   └── USER_GUIDE.md            # 用户手册 — 安装、配置、故障排除
└── src/
    ├── main.py                  # 主入口 + 主循环
    ├── overlay.py               # 透明叠加窗口管理 (Win32 ctypes)
    ├── overlay_core.c           # C 扩展 — 高性能 Win32 窗口操作
    ├── game_monitor.py          # D3 进程监控
    ├── data_provider.py         # 数据聚合 (API + 日志 + 缓存)
    ├── renderer.py              # 渲染引擎 (Pygame ARGB)
    ├── plugin_manager.py        # 插件系统
    ├── config.py                # 配置管理
    ├── hotkey.py                # 全局热键
    ├── setup.py                 # C 扩展编译脚本
    └── plugins/
        ├── timer.py             # ⏱ 秘境计时器
        ├── build_info.py        # 📋 构筑信息展示
        ├── nemesis.py           # 👹 复仇怪追踪
        └── rift_info.py         # 📊 秘境进度信息
```

---

## 🚀 快速开始

### 系统要求

- Windows 10 64-bit 或更高
- Python 3.10+
- Diablo 3 使用 **无边框窗口化** 模式

### 安装

```bash
# 克隆项目
git clone https://github.com/yourname/d3-overlay.git
cd d3-overlay

# 安装依赖
pip install -r requirements.txt

# 编译 C 扩展（可选，纯 Python 也能运行基础功能）
cd src && python setup.py build_ext --inplace && cd ..

# 启动
python src/main.py
```

### 首次配置

1. 运行后在设置中填写你的 **BattleTag**（格式：名字#数字）
2. 选择游戏 **区域**（us / eu / kr / cn）
3. 启动 Diablo 3，使用 **无边框窗口化** 模式
4. 叠加层会自动出现在游戏窗口上方

---

## 🎮 插件说明

### ⏱ 秘境计时器 (Timer)
- 记录大/小秘境通关时间
- 自动检测秘境开始/结束
- 历史最佳记录

### 📋 构筑信息 (BuildInfo)
- 通过 Blizzard API 获取角色装备和技能
- 显示巅峰等级、主动技能与符文
- 支持所有 7 个职业

### 👹 复仇怪追踪 (Nemesis)
- 追踪复仇怪物状态
- 击杀计数统计

### 📊 秘境进度 (RiftInfo)
- 实时进度条显示
- Boss 出现时间预估
- 分段时间记录

---

## ⌨️ 快捷键

| 快捷键 | 功能 |
|--------|------|
| `F8` | 显示/隐藏叠加层 |
| `F9` | 开始/停止计时器 |
| `Shift+F9` | 重置计时器 |
| `F10` | 切换布局位置 |
| `F11` | 打开设置 |
| `Ctrl+Shift+H` | 老板键（立即隐藏） |

所有快捷键可在 `config.json` 中自定义。

---

## 🛡️ 安全说明

### ✅ D3OA 不会做的

- ❌ 不读取游戏内存
- ❌ 不注入任何 DLL
- ❌ 不修改游戏文件
- ❌ 不 Hook 任何 API
- ❌ 不自动化任何游戏操作

### ✅ D3OA 使用的合法技术

- 透明窗口叠加 — 与 OBS、Discord Overlay 原理相同
- 公开 API 查询 — 使用暴雪公开的 Web API
- 日志文件读取 — 只读取游戏自动生成的日志
- 窗口截图捕获 — 与 Windows 截图工具原理一致

> D3OA 对游戏进程完全 **"只读"**，使用的是操作系统级别的标准窗口管理机制。

---

## 🔌 开发插件

创建自定义插件只需 3 步：

```python
# src/plugins/my_plugin.py

from plugin_manager import PluginBase

class Plugin(PluginBase):
    @property
    def name(self) -> str:
        return "MyPlugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    def on_init(self, context: dict):
        self.config = context['config']
        # 初始化逻辑

    def on_update(self, delta_time: float, game_data: dict):
        # 每帧更新逻辑
        pass

    def on_render(self, surface):
        # 渲染到叠加层
        try:
            import pygame
            # 绘制逻辑
        except ImportError:
            pass
```

将文件放入 `src/plugins/` 目录，重启 D3OA 即自动加载。

详见 [技术文档](docs/TECHNICAL.md)。

---

## 📚 文档

- [技术文档](docs/TECHNICAL.md) — 架构设计、API 参考、扩展路线图
- [用户手册](docs/USER_GUIDE.md) — 安装指南、配置说明、故障排除

---

## 🗺️ 路线图

- [x] 基础框架 (透明窗口 + 插件系统)
- [x] 核心插件 (计时器/构筑/进度/复仇怪)
- [ ] 截图 OCR 识别
- [ ] 语音播报
- [ ] 数据统计与图表
- [ ] 多语言支持
- [ ] 插件市场
- [ ] 云端配置同步

---

## 📄 许可证

[MIT License](LICENSE) — 仅供学习和社区交流使用。

---

## ⚠️ 免责声明

本工具仅供个人学习和游戏体验增强使用。请遵守暴雪《最终用户许可协议》(EULA)。使用本工具所产生的任何后果由使用者自行承担。
