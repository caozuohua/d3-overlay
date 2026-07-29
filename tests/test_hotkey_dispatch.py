"""
F7 (TDD): 热键单消费者派发
RED: HotkeyManager 不应启动会与主线程争夺消息的后台 GetMessageW 线程；
     主线程 poll() 应是唯一消费者（RegisterHotKey 把 WM_HOTKEY 投递到注册线程，
     即主线程）。
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_no_background_message_thread():
    """F7 修复：register 不应再启动后台 GetMessageW 线程（避免与主线程 poll 争夺）。"""
    from hotkey import HotkeyManager

    class FakeConfig:
        def get(self, path, default=None):
            return default

    hm = HotkeyManager(FakeConfig())
    assert hm._thread is None, "register 前不应有后台线程"
    hm.register("F9", lambda: None)
    assert hm._thread is None, "register 不应启动后台消息循环线程"
    hm.stop()


def test_poll_dispatches_to_registered_callback():
    """主线程 poll() 收到 WM_HOTKEY 时应派发到对应回调（单消费者模型）。"""
    import ctypes
    import ctypes.wintypes as w
    from hotkey import HotkeyManager, WM_HOTKEY

    class FakeConfig:
        def get(self, path, default=None):
            return default

    hm = HotkeyManager(FakeConfig())
    fired = []
    hm.register("F9", lambda: fired.append(1))
    # 模拟 OS 把 WM_HOTKEY 投递到注册线程队列（真实环境由物理按键触发）
    tid = ctypes.windll.kernel32.GetCurrentThreadId()
    ctypes.windll.user32.PostThreadMessageW(tid, WM_HOTKEY, 1, 0)
    time.sleep(0.05)
    hm.poll()
    assert fired, "poll() 未派发到注册的 F9 回调"
    hm.stop()


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
