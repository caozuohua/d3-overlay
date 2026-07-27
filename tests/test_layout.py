"""
F5 (TDD): 布局切换真正重定位面板
RED: OverlayManager.place() 应把基坐标映射到所选角落；cycle_layout 改变角落。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _ov():
    from overlay import OverlayManager
    from config import Config
    cfg = Config(config_path=os.path.join(os.path.dirname(__file__), "_tmp_f5_cfg.json"))
    cfg.load()
    ov = OverlayManager(cfg)
    ov._width, ov._height = 1920, 1080
    ov._layout = "top-right"
    return ov


def test_place_maps_to_corner():
    """place() 把 top-left 基坐标映射到 top-right 角落。"""
    ov = _ov()
    # 基坐标 (20,20) 在 1920x1080 上应靠右对齐
    x, y = ov.place(20, 20)
    assert x > 1920 // 2, f"top-right 应靠右，x={x}"
    assert y == 20, f"top-right 顶部 y={y}"


def test_cycle_layout_changes_corner():
    """cycle_layout() 切换到下一个角落，place() 随之改变位置。"""
    ov = _ov()
    x0, _ = ov.place(20, 20)
    ov.cycle_layout()  # -> top-left
    x1, y1 = ov.place(20, 20)
    assert x1 == 20 and y1 == 20, f"top-left 应为 (20,20)，实际 ({x1},{y1})"
    assert x1 != x0, "切换布局后水平位置应改变"


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
