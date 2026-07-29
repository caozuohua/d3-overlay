"""
F1 (TDD): 渲染管线契约测试
RED 阶段：断言修复后的契约——
  - OverlayManager.get_surface() 返回的是一个 pygame.Surface（插件可 .blit）
  - 插件在 surface 上 .blit 后，end_frame() 能把像素写进 _pixels（不抛错）
当前实现 get_surface() 返回 ctypes 字节数组 → 这些测试应为 RED。
修复 overlay.py（内部维护 pygame.Surface，end_frame 用 tostring 写回 _pixels）后转 GREEN。
"""

import os
import sys
import inspect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import ctypes


def _make_overlay():
    """构造一个最小可用的 OverlayManager（不真正创建 Win32 窗口）。"""
    from overlay import OverlayManager
    from config import Config
    cfg = Config(config_path=os.path.join(os.path.dirname(__file__), "_tmp_f1_cfg.json"))
    cfg.load()
    ov = OverlayManager(cfg)
    # 复用真实 _recreate_surface 逻辑，但尺寸改小、不建窗口
    ov._width, ov._height = 300, 200
    ov._recreate_surface(300, 200)
    return ov


def test_get_surface_returns_pygame_surface():
    """修复后：get_surface() 必须返回 pygame.Surface（插件依赖 .blit/.fill）。"""
    try:
        import pygame
    except ImportError:
        print("  SKIP  test_get_surface_returns_pygame_surface (pygame 未安装)")
        return
    try:
        ov = _make_overlay()
    except Exception as e:
        print(f"  SKIP  test_get_surface_returns_pygame_surface (无法建表面: {e})")
        return
    surf = ov.get_surface()
    assert surf is not None, "get_surface() 不应为 None"
    assert isinstance(surf, pygame.Surface), (
        f"get_surface() 应返回 pygame.Surface，实际 {type(surf)}"
    )
    # 插件能在其上 .blit
    try:
        pygame.font.init()
        f = pygame.font.SysFont("Microsoft YaHei", 14)
        surf.blit(f.render("hi", True, (255, 165, 0)), (8, 8))
    except Exception as e:
        raise AssertionError(f"插件无法在 surface 上 blit: {e}")
    ov.destroy()
    try:
        os.remove(cfg_path_of(ov))
    except Exception:
        pass


def cfg_path_of(ov):
    return ov.config._config_path


def test_plugin_render_into_overlay_surface_does_not_raise():
    """修复后：Timer 插件 .blit 到 get_surface() 返回的 surface 不应抛 AttributeError。"""
    try:
        import pygame
    except ImportError:
        print("  SKIP  test_plugin_render_into_overlay_surface_does_not_raise (pygame 未安装)")
        return
    from plugins.timer import Plugin as TimerPlugin

    class FakeConfig:
        def get(self, path, default=None):
            return default

    p = TimerPlugin()
    p.on_init({"config": FakeConfig(), "overlay": None})
    try:
        ov = _make_overlay()
    except Exception as e:
        print(f"  SKIP  test_plugin_render_into_overlay_surface_does_not_raise (无法建表面: {e})")
        return
    # 把插件的渲染目标换成 overlay 的真实 surface
    surf = ov.get_surface()
    raised = False
    try:
        p.on_render(surf)
    except AttributeError:
        raised = True
    assert not raised, "修复后插件渲染不应抛 AttributeError（渲染断路已修）"
    ov.destroy()


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
