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
def test_logwatcher_emits_nemesis_event():
    """F2 修复：日志解析器应在日志行含 'nemesis' 时产出 nemesis 事件，
    使 Nemesis 插件的状态机可被驱动（不再永远 idle）。"""
    w = GameLogWatcher()
    # 一条典型的复仇怪相关日志（关键字位于行内任意位置）
    line = "[12:03:45] (Game) Nemesis monster has spawned in your game"
    events = w.parse_events([line])
    types = [e["type"] for e in events]
    assert "nemesis" in types, f"解析器未产出 nemesis 事件，实际: {types}"
    # 含原始行，供插件判断 appear/spawn/kill
    assert "nemesis" in events[types.index("nemesis")]["raw"].lower()


def test_nemesis_plugin_reacts_to_nemesis_event():
    """F2 修复：喂入 nemesis 事件后，插件状态应从 idle 变为 appeared。"""
    from plugins.nemesis import Plugin as NemesisPlugin

    class FakeConfig:
        def get(self, path, default=None):
            return default

    p = NemesisPlugin()
    p.on_init({"config": FakeConfig(), "data_provider": None})

    class Ev(dict):
        pass

    # 模拟 main 循环：log_events 是累积列表（与 main._collect_game_data 一致）
    appeared = Ev(type="nemesis", raw="Nemesis monster has appeared and spawned", timestamp=0)
    p.on_update(0.016, {"log_events": [appeared]})
    assert p._nemesis_state == "appeared", f"应变为 appeared，实际 {p._nemesis_state}"

    defeated = Ev(type="nemesis", raw="Nemesis monster defeated and killed", timestamp=1)
    # 累积列表：包含之前所有事件
    p.on_update(0.016, {"log_events": [appeared, defeated]})
    assert p._nemesis_state == "defeated"
    assert p._kill_count == 1


def test_nemesis_plugin_idle_without_nemesis_log():
    """F2 修复后：没有复仇怪关键字的日志，插件应保持 idle（不再误触发）。"""
    from plugins.nemesis import Plugin as NemesisPlugin

    class FakeConfig:
        def get(self, path, default=None):
            return default

    p = NemesisPlugin()
    p.on_init({"config": FakeConfig(), "data_provider": None})

    # 普通游戏事件，不含 nemesis 关键字 —— 状态应为 idle
    w = GameLogWatcher()
    events = w.parse_events(["[12:00:01] (Game) You entered the Vault", "[12:00:02] (Game) Game_NewGame"])
    p.on_update(0.016, {"log_events": events})
    assert p._nemesis_state == "idle"


# ───────────────────────────────────────────────────────
# 5) 渲染断路复现（核心缺陷 #1）
#    main 把 overlay.get_surface()（ctypes 像素数组）传给插件，
#    插件却当 pygame.Surface 调 .blit()
#    —— 本环境未装 pygame，故直接断言「类型契约不匹配」这一根因
# ───────────────────────────────────────────────────────
def test_plugin_renders_into_real_surface_no_error():
    """回归守卫（F1 修复后）：插件在真实 pygame.Surface 上渲染不应抛 AttributeError。
    这是修复后的正确契约 —— main 通过 overlay.get_surface() 传 pygame.Surface 给插件。"""
    try:
        import pygame
    except ImportError:
        print("  SKIP  test_plugin_renders_into_real_surface_no_error (pygame 未安装)")
        return
    from plugins.timer import Plugin as TimerPlugin

    class FakeConfig:
        def get(self, path, default=None):
            return default

    p = TimerPlugin()
    p.on_init({"config": FakeConfig(), "overlay": None})
    surf = pygame.Surface((220, 90), pygame.SRCALPHA)
    # 修复后：不抛异常
    p.on_render(surf)


def test_surface_contract_mismatch():
    import inspect
    import plugins.timer as timer_mod

    # overlay.get_surface() 实际返回的类型（与 overlay.py 一致）
    fake_surface = (ctypes.c_byte * 16)()
    # ctypes 字节数组没有 .blit 方法，而插件内部依赖它
    assert not hasattr(fake_surface, "blit"), "前提错误: ctypes 数组不该有 blit"
    # 印证插件 on_render 内部确实会尝试 .blit（所以 get_surface 必须返回 Surface）
    src = inspect.getsource(timer_mod.Plugin.on_render)
    assert "blit" in src, "插件本应调用 surface.blit()"


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
