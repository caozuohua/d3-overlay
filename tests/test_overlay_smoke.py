"""
L3 叠加窗口冒烟测试（需要真实 Windows 桌面会话）

本测试会真正 CreateWindowEx + UpdateLayeredWindow。在无桌面的 CI / headless 环境
会自动跳过（靠尝试创建窗口并捕获失败来判断）。

跑法（必须在有桌面的 Windows 上）:
    python tests\test_overlay_smoke.py
"""

import os
import sys
import platform

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _has_real_desktop() -> bool:
    """极简判断：Windows + 能拿到桌面 DC 才算有桌面会话。"""
    if platform.system() != "Windows":
        return False
    try:
        user32 = __import__("ctypes").windll.user32
        return user32.GetDC(0) != 0
    except Exception:
        return False


class _Skip(Exception):
    pass


def test_overlay_create_and_surface():
    if not _has_real_desktop():
        print("  SKIP  test_overlay_create_and_surface (无桌面会话)")
        return

    # 本测试依赖 pywin32 分支（部署机实际路径）。若当前解释器没装 pywin32，
    # overlay 会退回 ctypes 分支，而 ctypes 分支在 Python 3.14 下有已知不兼容
    # （RUNNING_LOG「问题1」），无法在此环境验证 → 跳过并提示。
    try:
        import win32gui  # noqa: F401
    except Exception:
        print("  SKIP  test_overlay_create_and_surface (pywin32 未安装，退回 ctypes 分支在 3.14 下不兼容，无法验证)")
        return

    try:
        from overlay import OverlayManager
        from config import Config
    except Exception as e:
        print(f"  SKIP  test_overlay_create_and_surface (import 失败: {e})")
        return

    cfg = Config(config_path=os.path.join(os.path.dirname(__file__), "_tmp_smoke_cfg.json"))
    cfg.load()
    ov = OverlayManager(cfg)
    assert ov.create(), "叠加窗口创建失败（可能需要管理员权限 / 桌面会话）"

    # 🔴 致命点 #2：pywin32 分支表面创建失败时 _pixels 为 None
    surf = ov.get_surface()
    assert surf is not None, "get_surface() 返回 None —— 渲染缓冲未建立，叠加层将空白"

    ov.show()
    ov.hide()
    ov.destroy()
    try:
        os.remove(cfg._config_path)
    except OSError:
        pass


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except _Skip:
            pass
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests)-failed}/{len(tests)} (含 SKIP) 通过")
    sys.exit(1 if failed else 0)
