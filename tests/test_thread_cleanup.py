"""
F6 (TDD): 线程正确退出
RED: GameMonitor.stop() 应让监控线程真正结束；HotkeyManager 应有 stop() 释放后台线程。
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_game_monitor_stop_terminates_thread():
    """F6 修复：stop() 后监控线程应在短时间内退出（不再泄漏）。"""
    from game_monitor import GameMonitor
    gm = GameMonitor(process_name="Diablo III64.exe")  # 后台线程已启动
    assert gm._monitor_thread.is_alive(), "监控线程应已启动"
    gm.stop()
    gm._monitor_thread.join(timeout=3)
    assert not gm._monitor_thread.is_alive(), "stop() 后监控线程应已退出"


def test_hotkey_manager_has_stop():
    """F6 修复：HotkeyManager.stop() 存在且置 _running=False（后台线程可退出）。"""
    from hotkey import HotkeyManager

    class FakeConfig:
        def get(self, path, default=None):
            return default

    hm = HotkeyManager(FakeConfig())
    assert hasattr(hm, "stop"), "HotkeyManager 缺少 stop()"
    hm.stop()
    assert hm._running is False


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
