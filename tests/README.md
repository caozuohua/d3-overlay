# D3OA 测试说明

## 本机 Python 情况（重要）
本机有多个 Python，互不相通：

| 解释器 | 用途 | pygame / pywin32 |
|--------|------|------------------|
| `C:\Users\Cao Zuohua (Be)\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe` (3.11.15) | Hermes 终端默认 `python` | 无 pygame；pywin32 可用 |
| `C:\Users\Cao Zuohua (Be)\AppData\Local\Python\bin\python.exe` (3.14.5) | **已装 pygame-ce 2.5.7** | pygame-ce ✅；pywin32 ❌（缺 DLL） |
| `C:\Python314\python.exe` (3.14) | 系统 3.14 | 两者均缺 |

> 结论：跑带渲染的测试（test_render_break_raises_when_pygame_present）要用
> `C:\Users\Cao Zuohua (Be)\AppData\Local\Python\bin\python.exe`。
> 纯逻辑测试（config/cache/hotkey/log）任意解释器可跑。

## 运行
```bat
REM 纯逻辑（任意 python，零依赖）
python tests\test_core.py

REM 含渲染复现（必须 pygame-ce 解释器）
"C:\Users\Cao Zuohua (Be)\AppData\Local\Python\bin\python.exe" tests\test_core.py

REM 若装了 pytest
python -m pytest tests\ -q
```

## 测试分层
- L1 纯逻辑：config / TTLCache / 热键解析 / 日志解析 / 渲染契约 —— 无需 D3、无需窗口
- L2 渲染断路复现：需 pygame（断言 ctypes 缓冲上 .blit 抛 AttributeError）
- L3 窗口冒烟：overlay.create() 需真实 Windows 桌面会话（见 test_overlay_smoke.py，CI 跳过）
- L4 端到端：必须真有 Diablo 3 在跑，仅手工验收

## 关键发现（已被测试固化）
1. `test_render_break_raises_when_pygame_present` 复现 🔴 渲染断路：
   main 把 overlay.get_surface()（ctypes 字节数组）传给插件，插件当 pygame.Surface 调 .blit → AttributeError。
2. `test_logwatcher_never_emits_nemesis_event` / `test_nemesis_plugin_stays_idle_*` 复现 Nemesis 永远 idle。
3. `test_surface_contract_mismatch` 直接断言类型契约不匹配这一根因。
