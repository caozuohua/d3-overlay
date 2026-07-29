# D3OA 功能模块架构图（基于实际代码，非 README 示意）

> 本文档根据源码逐文件核对后绘制，反映**真实接线情况**。
> 与 README/TECHNICAL 的示意不同之处：
> 1. `overlay_core.c`（C 扩展）已编译但**从未被 import** —— 死代码。
> 2. `renderer.py`（Theme/TextRenderer/Panel/Renderer）**从未被 import** —— 死代码。
> 3. 渲染管线存在**致命断路**：main 把原始像素缓冲（ctypes byte 数组）传给插件，
>    插件却当 pygame.Surface 调用 `.blit()`，导致每帧 AttributeError、叠加层空白。

---

## 1. 进程内模块依赖（真实）

```
┌──────────────────────────────────────────────────────────────────────┐
│                         D3OverlayApp (main.py)                        │
│   initialize() → run() 主循环 (target_fps≈30)                         │
└───────┬───────────┬───────────┬───────────┬───────────┬──────────────┘
        │           │           │           │           │
        ▼           ▼           ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐
   │ Config  │ │GameMon  │ │DataProv │ │Overlay   │ │HotkeyMgr│
   │config.py│ │game_    │ │data_    │ │overlay.py│ │hotkey.py │
   │         │ │monitor  │ │provider │ │          │ │          │
   └─────────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬─────┘
                     │          │           │           │
                     │          │           │           │ 注册 RegisterHotKey
                     │          │           │           │ (F8/F9/F10/F11/Ctrl+Shift+H)
                     │          │           │           │ → 主线程 poll() 派发
                     │          │           │           │
                     │          ▼           │           │
                     │   ┌──────────────┐   │           │
                     │   │GameLogWatcher│   │           │
                     │   │D3APIClient   │   │           │
                     │   │TTLCache      │   │           │
                     │   └──────────────┘   │           │
                     │          │           │           │
                     ▼          ▼           ▼           ▼
            ┌──────────────── PluginManager (plugin_manager.py) ────────────────┐
            │  discover_and_load() 扫描 src/plugins/*.py，载入含 Plugin 类的模块 │
            │  update_all(delta, game_data)  每帧更新                             │
            │  render_all(surface)           每帧渲染  ← surface = overlay._pixels│
            └───────────────────────────┬────────────────────────────────────────┘
                                         │ 插件: Timer / BuildInfo / Nemesis / RiftInfo
                                         ▼
                              各自 on_render(surface) 内 `import pygame`
                              并对 surface 调用 .blit()/.fill()/pygame.draw.*

   ⚠️ 断路点: overlay.get_surface() 返回 self._pixels
            (ctypes.c_byte 数组，指向 DIB 像素内存，BGRA)
            并非 pygame.Surface → 插件调用 .blit() 抛 AttributeError
            → 被 plugin_manager.render_all 的 try/except 吞掉 → 叠加层空白
```

---

## 2. 每帧主循环（run()）

```
while running:
  if 时间到(100ms):
      game_running = game_monitor.is_game_running()
      if game_running: overlay.sync_to_game_window(); overlay.show()
      else:            overlay.hide()
  game_data = {
      'game_running', 'game_foreground',
      'log_events' = data_provider.get_log_events(),   # 读 D3Debug.txt 增量
      'timestamp'
  }
  plugin_manager.update_all(frame_time, game_data)     # 插件按日志事件自动逻辑
  overlay.begin_frame()                                # Python 逐像素清零(慢)
  plugin_manager.render_all(overlay.get_surface())     # ⚠️ 见断路点
  overlay.end_frame()                                  # UpdateLayeredWindow/BitBlt 推屏
  hotkey_manager.poll()                                # PeekMessageW 派发热键
  sleep(frame_time - elapsed)
```

---

## 3. 渲染目标接线（两种互相冲突的模型，均未完整实现）

| 模型 | 设计意图 | 实际状态 |
|------|----------|----------|
| A（renderer.py + overlay_core.c） | 插件画到 pygame.Surface → `get_pixel_buffer()` 转 BGRA → 写 DIB | **renderer.py、overlay_core.c 均未被 import，整套未接线** |
| B（main 直连） | 把 DIB 原始像素缓冲交给插件，插件直接写像素 | main 确实传了 `_pixels`，但插件用的是 pygame API 而非裸像素写入 → **类型不匹配，渲染失败** |

**结论**：当前代码两个模型都只完成了一半，且互相冲突；叠加层不会显示任何面板内容。

---

## 4. 数据源真实接线

- `data_provider.py`
  - `D3APIClient`：需 `data.access_token` 才发请求；无 OAuth 换取流程（用户须手动填 token）。
    仅 `BuildInfo` 调用 `get_profile()` + `get_hero_data()`。其余 `get_hero_items/get_item_data/
    get_*_leaderboard` 未被调用。
  - `GameLogWatcher`：轮询 `~/Documents/Diablo III/Logs/D3Debug.txt`，按关键字解析事件。
    仅识别 `new_game / leave_game / rift_event / waypoint / party_event` 五类。
  - `TTLCache`：英雄/档案缓存，ttl=300s。
- `game_monitor.py`：用 `FindWindowW("D3 Main Window Class", None)` 找游戏窗口；
  找不到时（psutil 安装情况下）回退到按进程名 EnumWindows。后台线程每 2s 检测状态变化。
- OCR：需求含 pytesseract/Pillow，但**无任何 OCR 代码**，`data.ocr_enabled` 未被读取。

---

## 5. 配置项真实可用性

| 配置键 | 代码中是否真正生效 |
|--------|--------------------|
| overlay.opacity | 部分：仅影响窗口创建时的 LWA_ALPHA；end_frame 用 SourceConstantAlpha=255 覆盖 |
| overlay.position | ❌ 未用于定位/偏移面板（F10 改它但无可见效果） |
| overlay.font_size | ✅ renderer/插件读取（但 renderer 未接线） |
| overlay.theme | ✅（仅 renderer 内；renderer 未接线） |
| overlay.click_through | ✅ |
| overlay.follow_game_window | ❌ 未读取 |
| hotkeys.* | ✅ |
| data.battle_tag / region / access_token | ✅（region/token 进 D3APIClient；tag 进 BuildInfo） |
| data.log_path | ✅（'auto' 则交给 GameLogWatcher 自动定位） |
| data.api_cache_ttl | ✅ |
| data.ocr_enabled | ❌ 未读取 |
| plugins.*.enabled | ✅（禁用则跳过加载） |
| plugins.*.position | ✅（插件渲染坐标，top-left 原点） |
| performance.target_fps | ✅ |
| performance.render_quality / cache_size_mb / log_poll_interval | ❌ 未读取 |
| ui.* | ❌ 未读取（renderer 未接线） |

---

## 6. 死代码 / 未接线清单

- `src/overlay_core.c` —— 编译产出 `.pyd` 但全仓无 `import overlay_core`。
- `src/renderer.py` —— 全仓无 `import renderer` / `Renderer` 实例化。
- `PluginBase.on_config_changed` —— 定义但未调用。
- `DataProvider.refresh_cache` —— 未调用。
- `main.py` 的 `cycle_layout` 链（F10）→ 改 `overlay.position`，无下游消费。
- `GameMonitor.on_game_state_changed` 回调 —— 注册接口存在，但无任何调用方注册。
- `DataProvider.get_recent_events`、`get_hero_items`、`get_item_data`、`get_*_leaderboard` —— 未调用。
- `overlay.py` 顶部 `import struct` —— 未使用。
- `test_window.py` / `check_wintypes.py` —— 一次性调试脚本，非运行所需。
- `hotkey.py` 后台 `GetMessageW` 线程 —— 热键消息由主线程 `poll()` 派发，后台线程基本空转。

---

## 7. 关键缺陷（详见 CODE_REVIEW.md）

| 严重度 | 问题 |
|--------|------|
| 🔴 严重 | 渲染断路：插件收到 ctypes 像素缓冲却按 pygame.Surface 操作 → 叠加层恒空白 |
| 🔴 严重 | pywin32 表面创建失败时 `_pixels=None`，`get_surface()` 返回 None，雪上加霜 |
| 🟠 较重 | Nemesis 永远 idle：日志解析器不产生 'nemesis'/'revenge' 事件，插件分支不可达 |
| 🟠 较重 | 文档宣称“无需认证 API”，代码却强制需要 access_token，且缺 OAuth 换取流程 |
| 🟡 中等 | README/USER_GUIDE 描述“设置向导 / 系统托盘 / OCR / 多显示器”均未实现 |
| 🟡 中等 | `begin_frame` Python 循环逐像素清零整屏（1920×1080≈830万次/帧），性能差 |
| 🟡 中等 | GameMonitor 线程、Hotkey 后台线程在 shutdown 时未正确退出（无 WM_QUIT / stop()） |
| 🟢 轻 | overlay_core.c 与 overlay.py 的 ctypes 分支重复实现窗口逻辑，维护分歧风险 |
