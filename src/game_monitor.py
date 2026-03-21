"""
D3OA — 游戏进程监控器

监控 Diablo 3 进程状态，获取窗口位置信息。
纯 Win32 API 操作，不读写游戏内存。
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
import threading
import time

logger = logging.getLogger("D3OA.GameMonitor")

user32 = ctypes.windll.user32

# D3 窗口类名 — 通过 Spy++ 工具获取
D3_WINDOW_CLASS = "D3 Main Window Class"
D3_PROCESS_NAMES = ["Diablo III64.exe", "Diablo III.exe"]


class GameMonitor:
    """Diablo 3 游戏进程监控器"""

    def __init__(self, process_name="Diablo III64.exe"):
        self.process_name = process_name
        self._game_hwnd = None
        self._callbacks = []
        self._running = True
        self._lock = threading.Lock()

        # 启动监控线程
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="GameMonitor"
        )
        self._monitor_thread.start()
        logger.info(f"游戏监控启动: 目标进程={process_name}")

    def is_game_running(self) -> bool:
        """检查游戏是否正在运行"""
        hwnd = self._find_game_window()
        return hwnd is not None

    def get_game_hwnd(self) -> int:
        """获取游戏窗口句柄"""
        return self._find_game_window()

    def get_window_rect(self) -> tuple:
        """获取游戏窗口矩形 (left, top, right, bottom)"""
        hwnd = self._find_game_window()
        if not hwnd:
            return None

        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return (rect.left, rect.top, rect.right, rect.bottom)

    def get_window_size(self) -> tuple:
        """获取游戏窗口尺寸 (width, height)"""
        rect = self.get_window_rect()
        if rect:
            return (rect[2] - rect[0], rect[3] - rect[1])
        return None

    def is_foreground(self) -> bool:
        """检查游戏窗口是否在前台"""
        hwnd = self._find_game_window()
        if not hwnd:
            return False
        fg_hwnd = user32.GetForegroundWindow()
        return fg_hwnd == hwnd

    def is_minimized(self) -> bool:
        """检查游戏窗口是否最小化"""
        hwnd = self._find_game_window()
        if not hwnd:
            return True
        return user32.IsIconic(hwnd)

    def on_game_state_changed(self, callback):
        """注册游戏状态变更回调"""
        with self._lock:
            self._callbacks.append(callback)

    def _find_game_window(self):
        """查找游戏窗口"""
        hwnd = user32.FindWindowW(D3_WINDOW_CLASS, None)
        if hwnd:
            return hwnd

        # 备用：通过进程名查找
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] in D3_PROCESS_NAMES:
                    # 尝试枚举该进程的窗口
                    pid = proc.info['pid']
                    EnumWindowsProc = ctypes.WINFUNCTYPE(
                        ctypes.wintypes.BOOL,
                        ctypes.wintypes.HWND,
                        ctypes.wintypes.LPARAM
                    )

                    found_hwnd = [None]

                    def enum_cb(hwnd, lParam):
                        dw_pid = ctypes.c_ulong()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(dw_pid))
                        if dw_pid.value == pid:
                            # 检查是否可见
                            if user32.IsWindowVisible(hwnd):
                                found_hwnd[0] = hwnd
                                return False
                        return True

                    user32.EnumWindows(EnumWindowsProc(enum_cb), 0)
                    if found_hwnd[0]:
                        return found_hwnd[0]
        except ImportError:
            pass

        return None

    def _monitor_loop(self):
        """后台监控循环"""
        was_running = False

        while self._running:
            running = self.is_game_running()

            if running != was_running:
                if running:
                    logger.info("游戏窗口检测到")
                else:
                    logger.info("游戏窗口已关闭")

                with self._lock:
                    for cb in self._callbacks:
                        try:
                            cb(running)
                        except Exception as e:
                            logger.error(f"回调执行失败: {e}")

                was_running = running

            time.sleep(2)  # 每 2 秒检测一次

    def stop(self):
        """停止监控"""
        self._running = False
