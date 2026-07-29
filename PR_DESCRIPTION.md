# D3OA — Windows 兼容性修复 + 自动点击功能 PR

## 📋 变更概览

本次 PR 分两部分：
1. **修复 11 个 Windows 运行时问题**，确保工具在各种 Windows 环境下稳定运行
2. **新增自动点击功能**（AutoClicker），帮助玩家自动化简单重复操作

---

## 🔧 第一部分：Windows 兼容性修复

### Fix 1: game_monitor.py — 闭包变量捕获 bug
**问题**: `_find_game_window` 中 `enum_cb` 闭包捕获了循环变量 `pid`，在 Python 中所有闭包共享同一个变量引用，导致全部回调使用最后一个 pid。

**修复**: 将 pid 作为默认参数传入闭包，或使用局部变量捕获。

### Fix 2: game_monitor.py — 缺少 Win32 API 类型声明
**问题**: `EnumWindows` 和 `GetWindowThreadProcessId` 未声明 argtypes/restype，ctypes 可能推断错误的参数尺寸（尤其是在 64 位系统上）。

**修复**: 添加完整的 API 类型声明。

### Fix 3: game_monitor.py — psutil 依赖处理
**问题**: psutil 列为可选依赖，但 fallback 路径依赖它进行进程枚举。

**修复**: 添加原生 Win32 进程查找（使用 `CreateToolhelp32Snapshot`）作为 psutil 不可用时的 fallback。

### Fix 4: data_provider.py — OneDrive Documents 路径
**问题**: 中文 Windows 下 Documents 文件夹可能被重定向到 OneDrive。

**修复**: 添加 OneDrive 路径候选，使用 `ctypes` 获取已知文件夹路径。

### Fix 5: data_provider.py — 日志文件读取保护
**问题**: D3 写入日志时读取可能遇到文件锁或部分写入。

**修复**: 添加 try/except 和文件锁检测。

### Fix 6: overlay.py — 副屏游戏窗口支持
**问题**: `sync_to_game_window` 用 `GetSystemMetrics(SM_CXSCREEN)` 获取屏幕尺寸，这只覆盖主屏。游戏在副屏上时叠加窗口大小/位置不对。

**修复**: 使用游戏窗口自身尺寸而非屏幕尺寸。

### Fix 7: overlay.py — 像素缓冲区清空性能
**问题**: Python for 循环逐字节清空 `ctypes.c_byte` 数组，在 1920x1080 下需要 ~8M 次 Python 迭代，帧率暴跌。

**修复**: 使用 `ctypes.memset` 或 C 扩展的 `clear_pixels`。

### Fix 8: config.py — 配置文件备份
**问题**: JSON 损坏直接丢失所有用户设置。

**修复**: 保存前备份旧配置为 `.bak`。

### Fix 9: hotkey.py — 重复热键触发
**问题**: 后台消息循环线程 + 主线程 `poll()` 可能处理同一个热键消息。

**修复**: 只在后台线程处理热键（移除主线程 poll）。

### Fix 10: plugin_manager.py — 插件异常隔离
**问题**: 单个插件抛异常会中断所有后续插件的更新/渲染。

**修复**: 在 `update_all` 和 `render_all` 中添加 try/except。

### Fix 11: main.py — DPI 初始化时序
**问题**: DPI 感知设置必须在任何 Win32 API 调用之前。但 `from overlay import ...` 可能触发 `ctypes.windll.user32` 加载。

**修复**: 将 DPI 初始化移到所有 import 之前。

---

## 🖱️ 第二部分：自动点击功能 (AutoClicker)

### 设计目标

帮助玩家自动完成 Diablo 3 中的简单重复操作：
- **装备拾取**: 连续点击地面装备
- **装备鉴定**: 连续点击书架/凯恩
- **装备分解**: 连续点击分解NPC
- **血岩赌博**: 连续点击赌博商人

### 技术方案

使用 Win32 `SendInput` API 模拟鼠标输入：
- `SendInput` 是硬件级输入注入，与物理鼠标点击完全等效
- 不是 `SendMessage`/`PostMessage`（消息级，很多游戏忽略）
- 不是 `mouse_event`（已废弃）
- 不读写游戏内存，不注入 DLL

### 安全声明

```
⚠️ 请合理使用自动点击功能。
- 本功能仅用于减轻重复操作带来的疲劳
- 长时间无人值守的自动化可能违反游戏 EULA
- 建议仅在需要时开启，完成后立即关闭
- D3OA 对使用本功能产生的后果不承担责任
```

### 模块设计

#### 新文件: `src/click_simulator.py`

```python
class ClickSimulator:
    def __init__(self, config, game_monitor)
    def start()          # 开始自动点击
    def stop()           # 停止
    def toggle()         # 切换
    def is_active()      # 是否运行中
    def update()         # 主循环调用，执行点击逻辑
```

核心逻辑：
1. 检查游戏是否在前台（安全限制）
2. 检查是否超过最大点击次数
3. 检查间隔是否满足
4. 调用 `SendInput` 发送鼠标按下+释放

### 配置项

```json
{
  "autoclicker": {
    "enabled": true,
    "interval_ms": 100,
    "max_clicks": 0,
    "foreground_only": true,
    "click_button": "left",
    "pause_on_key": true,
    "pause_key": "SHIFT"
  },
  "hotkeys": {
    "toggle_autoclick": "F7"
  }
}
```

### UI 集成

- 叠加层右下角显示 AutoClicker 状态指示器
- 运行中: 绿色圆点 + 点击计数
- 已暂停: 黄色圆点
- 关闭: 不显示

### 文件修改清单

| 文件 | 变更 |
|------|------|
| `src/click_simulator.py` | **新增** — 核心点击模拟器 |
| `src/main.py` | 集成 ClickSimulator + 修复 DPI 时序 |
| `src/overlay.py` | 修复副屏支持 + 像素清空性能 |
| `src/game_monitor.py` | 修复闭包 bug + API 声明 + 进程查找 |
| `src/data_provider.py` | 修复 OneDrive 路径 + 日志读取保护 |
| `src/config.py` | 添加配置备份 |
| `src/hotkey.py` | 修复重复触发 |
| `src/plugin_manager.py` | 添加异常隔离 |
| `config/default.json` | 添加 autoclicker 默认配置 |
| `docs/USER_GUIDE.md` | 添加 AutoClicker 使用说明 |
| `README.md` | 更新功能列表 |
