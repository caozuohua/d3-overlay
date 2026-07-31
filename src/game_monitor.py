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
kernel32 = ctypes.windll.kernel32

# ─── Win32 API 类型声明 ─────────────────────────────────

# EnumWindows / EnumWindowsProc
EnumWindowsProc = ctypes.WINFUNCTYPE(
    ctypes.wintypes.BOOL,
    ctypes.wintypes.HWND,
    ctypes.wintypes.LPARAM
)

user32.EnumWindows.argtypes = [EnumWindowsProc, ctypes.wintypes.LPARAM]
user32.EnumWindows.restype = ctypes.wintypes.BOOL

user32.GetWindowThreadProcessId.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.POINTER(ctypes.c_ulong)
]
user32.GetWindowThreadProcessId.restype = ctypes.c_ulong

user32.IsWindowVisible.argtypes = [ctypes.wintypes.HWND]
user32.IsWindowVisible.restype = ctypes.wintypes.BOOL

user32.IsIconic.argtypes = [ctypes.wintypes.HWND]
user32.IsIconic.restype = ctypes.wintypes.BOOL

user32.GetForegroundWindow.restype = ctypes.wintypes.HWND

user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
user32.FindWindowW.restype = ctypes.wintypes.HWND

user32.GetWindowRect.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = ctypes.wintypes.BOOL

# ─── Toolhelp32 API (原生进程枚举，不依赖 psutil) ────────

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_ulong),
        ("cntUsage", ctypes.c_ulong),
        ("th32ProcessID", ctypes.c_ulong),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", ctypes.c_ulong),
        ("cntThreads", ctypes.c_ulong),
        ("th32ParentProcessID", ctypes.c_ulong),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_ulong),
        ("szExeFile", ctypes.c_wchar * 260),
    ]

try:
    kernel32.CreateToolhelp32Snapshot.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = ctypes.wintypes.BOOL
    kernel32.Process32NextW.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = ctypes.wintypes.BOOL
    kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
    kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
    TOOLHELP_AVAILABLE = True
except AttributeError:
    TOOLHELP_AVAILABLE = False

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
        # 方法 1: 通过窗口类名查找（最快），但必须二次校验 pid，避免把
        # 历史残留/同名类窗口误判为“D3 仍在运行”。
        hwnd = user32.FindWindowW(D3_WINDOW_CLASS, None)
        if hwnd and self._is_d3_window(hwnd):
            return hwnd

        # 方法 2: 通过进程名查找窗口（需要进程枚举）
        pids = self._find_game_pids()
        if not pids:
            return None

        # 枚举所有可见窗口，找到属于游戏进程的窗口
        found_hwnd = [None]

        def enum_cb(hwnd, lParam):
            if found_hwnd[0] is not None:
                return False  # 已找到，停止枚举
            if not user32.IsWindowVisible(hwnd):
                return True
            if not self._is_d3_window(hwnd):
                return True
            found_hwnd[0] = hwnd
            return False

        callback = EnumWindowsProc(enum_cb)
        user32.EnumWindows(callback, 0)
        return found_hwnd[0]

    def _is_d3_window(self, hwnd) -> bool:
        """校验窗口是否真属于 D3 进程。"""
        if not hwnd:
            return False
        try:
            dw_pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(dw_pid))
            if not dw_pid.value:
                return False
            return self._is_d3_process(dw_pid.value)
        except Exception:
            return False

    def _is_d3_process(self, pid: int) -> bool:
        """按 pid 回查进程名，判断是否 D3。"""
        try:
            import psutil
            try:
                proc = psutil.Process(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return False
            name = (proc.name() or '').lower()
            return name in {n.lower() for n in D3_PROCESS_NAMES}
        except ImportError:
            pass

        # 无 psutil 时回退 Toolhelp32 全量枚举
        if not TOOLHELP_AVAILABLE:
            return False
        try:
            pids = self._find_game_pids()
            return pid in pids
        except Exception:
            return False

    def _find_game_pids(self) -> set:
        """查找游戏进程 PID 集合"""
        pids = set()

        # 优先使用 psutil（如果可用）
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] in D3_PROCESS_NAMES:
                    pids.add(proc.info['pid'])
            if pids:
                return pids
        except ImportError:
            pass

        # 回退: 使用 Win32 Toolhelp32 API（原生，不需要 psutil）
        if TOOLHELP_AVAILABLE:
            pids = self._find_pids_native()
        
        return pids

    def _find_pids_native(self) -> set:
        """使用 Win32 Toolhelp32 API 查找进程 PID（不依赖 psutil）"""
        pids = set()
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)

        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == INVALID_HANDLE_VALUE:
            return pids

        try:
            if kernel32.Process32FirstW(snapshot, ctypes.byref(pe)):
                while True:
                    if pe.szExeFile in D3_PROCESS_NAMES:
                        pids.add(pe.th32ProcessID)
                    if not kernel32.Process32NextW(snapshot, ctypes.byref(pe)):
                        break
        finally:
            kernel32.CloseHandle(snapshot)

        return pids

    def _monitor_loop(self):
        """后台监控循环"""
        was_running = False

        while self._running:
            try:
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
            except Exception as e:
                logger.error(f"游戏监控异常: {e}")

            time.sleep(2)  # 每 2 秒检测一次

    def stop(self):
        """停止监控"""
        self._running = False
