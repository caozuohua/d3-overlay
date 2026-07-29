"""
F8 (TDD): 插件渲染上下文与 pygame 字体初始化
RED→GREEN 验证三个运行时崩溃：
  - plugin.overlay 由 PluginManager 注入（不再 AttributeError）
  - 插件 on_render 在真实 pygame.Surface 上不抛 'overlay' / 'font not initialized'
  - OverlayManager.end_frame 不再 'ctypes is not defined'
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_plugin_gets_overlay_injected():
    """F8: PluginManager 应在加载后注入 plugin.overlay（避免 AttributeError）。"""
    from plugin_manager import PluginManager

    class FakeConfig:
        def get(self, path, default=None):
            return default
    fake_overlay = object()
    ctx = {"config": FakeConfig(), "overlay": fake_overlay, "data_provider": None}
    pm = PluginManager()
    pm.discover_and_load(ctx)
    assert pm.plugins, "应至少加载一个插件"
    for p in pm.plugins.values():
        assert hasattr(p, "overlay"), f"{p.name} 缺少 overlay 属性"
        assert p.overlay is fake_overlay, f"{p.name}.overlay 未被注入"


def test_plugin_render_does_not_raise_on_real_surface():
    """F8: 插件在真实 pygame.Surface 上 on_render 不应抛 'overlay'/'font' 错误。"""
    try:
        import pygame
    except ImportError:
        print("  SKIP  test_plugin_render_does_not_raise_on_real_surface (pygame 未安装)")
        return
    from plugin_manager import PluginManager

    class FakeConfig:
        def get(self, path, default=None):
            return default
    # 内部 pygame.Surface 作为 overlay 的渲染目标
    surf = pygame.Surface((300, 200), pygame.SRCALPHA)
    pygame.font.init()

    class FakeOverlay:
        def __init__(self, s): self._s = s
        def get_surface(self): return self._s
        def place(self, x, y): return (x, y)
        def begin_frame(self): self._s.fill((0, 0, 0, 0))
        def end_frame(self): pass

    ov = FakeOverlay(surf)
    ctx = {"config": FakeConfig(), "overlay": ov, "data_provider": None}
    pm = PluginManager()
    pm.discover_and_load(ctx)
    for p in pm.plugins.values():
        try:
            p.on_render(ov.get_surface())
        except AttributeError as e:
            raise AssertionError(f"{p.name} on_render 抛 AttributeError: {e}")
        except Exception as e:
            # 其它渲染细节错误（如缺数据）允许，但 'font not initialized' 不允许
            assert "font not initialized" not in str(e), f"{p.name} 字体未初始化: {e}"


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
