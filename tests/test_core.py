"""
D3OA 核心逻辑离线测试（无需 Diablo 3 / 无需 pygame / 无需真实窗口）

运行:
    python tests/test_core.py          # 直接跑
    python -m pytest tests/ -q         # 若装了 pytest

设计原则:
- 只测「不依赖 Win32 窗口创建 + 不依赖 pygame 渲染」的纯逻辑
- 用 fake 对象模拟 main 循环传给插件的 surface，复现渲染断路
"""

import os
import sys
import time

# 让 src 可被导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config import Config
from data_provider import TTLCache, GameLogWatcher
from hotkey import parse_hotkey

import ctypes


# ───────────────────────────────────────────────────────
# 1) 配置系统
# ───────────────────────────────────────────────────────
def test_config_get_set_defaults():
    cfg = Config(config_path=os.path.join(os.path.dirname(__file__), "_tmp_cfg.json"))
    cfg.load()
    assert cfg.get("overlay.opacity") == 0.85
    assert cfg.get("hotkeys.toggle_overlay") == "F8"
    assert cfg.get("data.region") == "us"
    # 深层 set
    cfg.set("data.battle_tag", "Foo#1234")
    assert cfg.get("data.battle_tag") == "Foo#1234"
    # 缺省回退
    assert cfg.get("nope.nope", "fallback") == "fallback"
    # 清理
    try:
        os.remove(cfg._config_path)
    except OSError:
        pass


# ───────────────────────────────────────────────────────
# 2) TTL 缓存
# ───────────────────────────────────────────────────────
def test_ttlcache_basic_and_expire():
    c = TTLCache(max_size=4)
    c.set("k", "v", ttl=1)
    assert c.get("k") == "v"
    time.sleep(1.1)
    assert c.get("k") is None  # 过期
    # LRU 淘汰
    for i in range(5):
        c.set(f"x{i}", i)
    assert c.get("x0") is None  # 最旧被挤出


# ───────────────────────────────────────────────────────
# 3) 热键解析
# ───────────────────────────────────────────────────────
def test_parse_hotkey():
    mod_c, vk_f9 = parse_hotkey("F9")
    assert vk_f9 == 0x78 and mod_c == 0
    mod_cs, vk_h = parse_hotkey("Ctrl+Shift+H")
    MOD_CONTROL, MOD_SHIFT = 0x0002, 0x0004
    assert vk_h == 0x48 and mod_cs == (MOD_CONTROL | MOD_SHIFT)
    # 无效
    assert parse_hotkey("NOT_A_KEY")[1] == 0


# ───────────────────────────────────────────────────────
# 4) 日志解析 + 复现 Nemesis 不可达缺陷
# ───────────────────────────────────────────────────────
def test_logwatcher_never_emits_nemesis_event():
    w = GameLogWatcher()
    # 一条“本应”被识别为复仇怪出现的日志行
    line = "[12:00:01] Nemesis monster spawned in your friend's game"
    events = w.parse_events([line])
    # 当前解析器只认 new_game/leave_game/rift_event/waypoint/party_event
    types = [e["type"] for e in events]
    assert "nemesis" not in types, "解析器意外产出了 nemesis 事件"
    assert events == []  # 实际会被整体丢弃


def test_nemesis_plugin_stays_idle_with_realistic_log():
    from plugins.nemesis import Plugin as NemesisPlugin

    class FakeConfig:
        def get(self, path, default=None):
            return default

    p = NemesisPlugin()
    p.on_init({"config": FakeConfig(), "data_provider": None})

    # main 循环实际给插件的 log_events 来源于 GameLogWatcher
    w = GameLogWatcher()
    events = w.parse_events(["Nemesis appeared and was defeated"])
    p.on_update(0.016, {"log_events": events})
    assert p._nemesis_state == "idle"  # 缺陷: 永远 idle


# ───────────────────────────────────────────────────────
# 5) 渲染断路复现（核心缺陷 #1）
#    main 把 overlay.get_surface()（ctypes 像素数组）传给插件，
#    插件却当 pygame.Surface 调 .blit()
#    —— 本环境未装 pygame，故直接断言「类型契约不匹配」这一根因
# ───────────────────────────────────────────────────────
def test_surface_contract_mismatch():
    import inspect
    import plugins.timer as timer_mod

    # overlay.get_surface() 实际返回的类型（与 overlay.py 一致）
    fake_surface = (ctypes.c_byte * 16)()
    # ctypes 字节数组没有 .blit 方法，而插件内部依赖它
    assert not hasattr(fake_surface, "blit"), "前提错误: ctypes 数组不该有 blit"
    # 印证插件 on_render 内部确实会尝试 .blit
    src = inspect.getsource(timer_mod.Plugin.on_render)
    assert "blit" in src, "插件本应调用 surface.blit()"


def test_render_break_raises_when_pygame_present():
    """若补装 pygame，插件会在 ctypes 缓冲上渲染时抛 AttributeError（缺陷复现）。"""
    try:
        import pygame
    except ImportError:
        print("  SKIP  test_render_break_raises_when_pygame_present (pygame 未安装)")
        return
    from plugins.timer import Plugin as TimerPlugin

    class FakeConfig:
        def get(self, path, default=None):
            return default

    p = TimerPlugin()
    p.on_init({"config": FakeConfig(), "overlay": None})
    fake_surface = (ctypes.c_byte * 16)()
    raised = False
    try:
        p.on_render(fake_surface)
    except AttributeError:
        raised = True
    assert raised, "预期插件在 ctypes 缓冲上渲染会抛 AttributeError（渲染断路）"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests)-failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
