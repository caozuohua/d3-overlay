# D3OA 代码校阅报告

> 校阅范围：`src/*.py`、`src/plugins/*.py`、`src/overlay_core.c`、`config`、`docs`、`README` 等全部 16 个 .py 文件。
> 语法检查：16/16 通过（py_compile，无 SyntaxError）。

## 一、严重（会让功能完全失效）

### 1. 渲染管线断路 —— 叠加层恒为空白
- 位置：`main.py` run() 中 `plugin_manager.render_all(self.overlay.get_surface())`
- `OverlayManager.get_surface()` 返回 `self._pixels`，它是
  `(ctypes.c_byte * buf_size).from_address(pixels_ptr.value)` —— 即 DIB 像素内存的 **ctypes 字节数组**。
- 但每个插件的 `on_render(surface)` 都 `import pygame` 后执行 `surface.blit(...)`、
  `pygame.draw.rect(surface, ...)` —— 这是把 `surface` 当 **pygame.Surface** 用。
- ctypes 字节数组没有 `.blit` 方法 → 抛 `AttributeError` → 被 `plugin_manager.render_all`
  的 try/except 捕获并记日志“渲染失败”。结果：屏幕上什么都不显示。
- 预期设计（renderer.py / overlay_core.c）应为：插件画到 pygame.Surface，再 `get_pixel_buffer()`
  转 BGRA 写进 DIB。该路径**从未接线**。

### 2. pywin32 表面创建失败导致 `_pixels=None`
- RUNNING_LOG 证实：`使用 pywin32 创建表面失败: Select bitmap object failed`。
- 在 pywin32 分支 `_recreate_surface()` 中，`_pixels` 仅在 ctypes 分支赋值；
  pywin32 分支 SelectObject 抛错后 `_pixels` 仍为 `None` → `get_surface()` 返回 `None`
  → 插件 `None.blit(...)` 再次报错。
- 即便切到 ctypes 分支，问题 #1 仍存在（类型不匹配）。

## 二、较重（功能不符预期 / 文档与代码矛盾）

### 3. Nemesis 插件逻辑不可达
- `nemesis.py` 依赖 `game_data['log_events']` 中出现含 `'nemesis'/'revenge'` 的事件。
- 但 `GameLogWatcher._parse_line` 只产出 `new_game / leave_game / rift_event / waypoint / party_event`，
  根本不会生成 nemesis 类事件 → `if 'nemesis' in raw` 永假 → 复仇怪永远显示“无追踪中”。

### 4. API 认证矛盾
- TECHNICAL.md §3.1 写“无需认证即可查询公开角色信息”。
- `data_provider.py` 的 `D3APIClient._request` 若 `access_token` 为空则直接跳过并返回 None，且**没有**
  OAuth client-credentials 换取流程（Blizzard API 实际需 token）。BuildInfo 会一直拿不到数据。
- 文档与代码不一致，且缺 token 申请/刷新实现。

### 5. 渲染性能：每帧 Python 循环清零整屏
- `overlay.py begin_frame()` 用 `for i in range(0, len(self._pixels), 4)` 逐像素清零。
- 全屏 1920×1080 ≈ 830 万次/帧 × 30fps，纯 Python 循环，CPU 占用高。应改用 `memset`/C 扩展
  （`overlay_core.clear_pixels` 已实现却没用上）。

## 三、中等（文档过度宣称 / 资源清理）

### 6. 文档描述了未实现的功能
- USER_GUIDE 的“首次配置向导”“系统托盘右键菜单”在代码里不存在（`open_settings_ui` 只是 `notepad` 打开 json）。
- README 路线图把“OCR / 语音播报 / 多语言 / 插件市场 / 云端同步”列为未做，但 USER_GUIDE §6.1 又把 OCR 写成可操作步骤。
- “多显示器支持 / follow_game_window / monitor”配置项未读取。
- `performance.render_quality / cache_size_mb / log_poll_interval`、`ui.*` 均未被读取。

### 7. 线程未正确退出
- `GameMonitor` 后台线程没有在 `shutdown()` 调用 `stop()`。
- `HotkeyManager.unregister_all()` 置 `_running=False`，但后台 `GetMessageW` 线程阻塞在无 WM_QUIT，
  不会真正退出（线程泄漏）。此外该后台线程其实抢不到热键消息（消息投递到注册线程=主线程），
  实际由主线程 `poll()` 派发，后台线程属于冗余。

### 8. F10 布局切换无效果
- `cycle_layout()` 改 `overlay.position` 为 top-right/left/bottom-right/left，但面板位置由
  `plugins.*.position`（插件 hardcode [20,20] 等，top-left 原点）决定，`overlay.position` 无下游消费。

## 四、轻（冗余 / 潜在维护风险）

### 9. 死代码
- `overlay_core.c` 编译但未 import（整模块无用）。
- `renderer.py` 未被 import（Theme/TextRenderer/Panel/Renderer 全无用）。
- `PluginBase.on_config_changed`、`DataProvider.refresh_cache`、`get_recent_events`、
  `get_hero_items/get_item_data/get_*_leaderboard`、`GameMonitor.on_game_state_changed` 定义但未调用。
- `overlay.py` 顶部 `import struct` 未使用。

### 10. 两套窗口实现并存
- `overlay.py` 同时含 pywin32 与 ctypes 两套窗口/表面逻辑；README 又宣称有 C 扩展。
  三套并存且互相独立，未来易分歧。建议二选一并把像素清零/提交交给 C 扩展。

### 11. 日志解析依赖未经验证的关键字
- `GameLogWatcher` 与插件的事件识别基于 `'nephalemrift'/'greater_rift'/'game_newgame'` 等假设关键字，
  未对照真实 `D3Debug.txt` 验证。Timer/RiftInfo 的自动启停同样依赖这些假设，实际可能不触发。

### 12. 修复状态（截至本会话）

| 缺陷 | 状态 | 修复方式 |
|------|------|----------|
| #1 渲染断路 | ✅ 已修 | `OverlayManager` 内部维护 pygame.Surface，end_frame 用 tostring 写回 DIB；窗口统一用 UpdateLayeredWindow 推屏 |
| #2 pywin32 表面失败→_pixels=None | ✅ 已修（随 #1） | 像素缓冲统一用 ctypes DIBSection，与窗口分支解耦 |
| #3 Nemesis 永远 idle | ✅ 已修 | `GameLogWatcher` 新增 nemesis 事件；插件状态机可驱动 |
| #4 API 认证矛盾 | ✅ 已修 | `D3APIClient._ensure_token()` 实现 client-credentials 换取；config 加 client_id/client_secret |
| #5 begin_frame 逐像素清零 | ✅ 已修（随 #1） | 改用 pygame.Surface.fill |
| #6 线程未退出 | ✅ 已修 | `main.shutdown()` 调 game_monitor.stop() 与 hotkey.stop()(PostQuitMessage) |
| #7 F10 布局无效 | ✅ 已修 | `OverlayManager.place()` 真正重定位面板 |
| #8 死代码 renderer.py/overlay_core.c | ⚠️ 保留（未删，避免破坏编译产物）；文档已更正说明其未接线 |
| #9 未调用接口 | ⚠️ 保留 | 属扩展性接口，未删 |
| #10 三套窗口实现 | ⚠️ 仍并存 | 窗口创建保留 pywin32/ctypes 双分支，像素缓冲已统一 |

回归测试：`tests/` 下 test_core / test_render_pipeline / test_api_auth / test_thread_cleanup / test_layout / test_overlay_smoke，均在 `C:\Users\Cao Zuohua (Be)\AppData\Local\Python\bin\python.exe`(pygame-ce+pywin32) 下通过。
