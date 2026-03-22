"""
D3OA — 自动点击模拟器 (AutoClicker)

使用 Win32 SendInput API 模拟鼠标点击。
SendInput 是硬件级输入注入，与物理鼠标点击完全等效。

安全说明：
- 使用标准 Win32 SendInput API，与游戏手柄/宏鼠标原理相同
- 不读写游戏内存，不注入 DLL，不 Hook 任何 API
- 仅在游戏窗口前台时生效（可配置）
- 提供快捷键随时停止

⚠️ 免责声明：
- 本功能仅用于减轻重复操作带来的疲劳
- 长时间无人值守的自动化可能违反游戏 EULA
- 使用本功能产生的后果由使用者自行承担
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
import time

logger = logging.getLogger("D3OA.AutoClick")

# ─── Win32 常量 ─────────────────────────────────────────

INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

# ─── Win32 结构体 ───────────────────────────────────────

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", _INPUT_UNION),
    ]

# ─── Win32 API ──────────────────────────────────────────

user32 = ctypes.windll.user32

user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = ctypes.c_uint

user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short

# 按钮配置映射
BUTTON_MAP = {
    'left':   (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    'right':  (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    'middle': (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}

# 键码映射（用于暂停键检测）
VK_KEY_MAP = {
    'SHIFT': 0x10,
    'CTRL': 0x11,
    'CONTROL': 0x11,
    'ALT': 0x12,
    'SPACE': 0x20,
    'LSHIFT': 0xA0,
    'RSHIFT': 0xA1,
    'LCTRL': 0xA2,
    'RCTRL': 0xA3,
}


class ClickSimulator:
    """自动点击模拟器

    使用 Win32 SendInput API 模拟鼠标点击。
    支持可配置的点击间隔、次数限制、前台检测。
    """

    def __init__(self, config, game_monitor=None):
        self.config = config
        self.game_monitor = game_monitor
        
        self._active = False
        self._paused = False
        self._click_count = 0
        self._last_click_time = 0
        
        # 从配置读取参数
        self._interval = config.get('autoclicker.interval_ms', 100) / 1000.0
        self._max_clicks = config.get('autoclicker.max_clicks', 0)  # 0 = 无限制
        self._foreground_only = config.get('autoclicker.foreground_only', True)
        self._button = config.get('autoclicker.click_button', 'left')
        self._pause_on_key = config.get('autoclicker.pause_on_key', True)
        self._pause_key = config.get('autoclicker.pause_key', 'SHIFT')
        
        self._button_flags = BUTTON_MAP.get(self._button, BUTTON_MAP['left'])
        self._pause_vk = VK_KEY_MAP.get(self._pause_key.upper(), 0x10)

    def start(self):
        """开始自动点击"""
        if self._active:
            return
        self._active = True
        self._paused = False
        self._click_count = 0
        self._last_click_time = 0
        logger.info(
            f"自动点击已启动: interval={self._interval*1000:.0f}ms, "
            f"button={self._button}, max={self._max_clicks or '∞'}"
        )

    def stop(self):
        """停止自动点击"""
        if not self._active:
            return
        self._active = False
        self._paused = False
        logger.info(f"自动点击已停止，共点击 {self._click_count} 次")

    def toggle(self):
        """切换自动点击状态"""
        if self._active:
            self.stop()
        else:
            self.start()

    def is_active(self) -> bool:
        """是否正在运行"""
        return self._active

    def is_paused(self) -> bool:
        """是否暂停中"""
        return self._paused

    def get_click_count(self) -> int:
        """获取已点击次数"""
        return self._click_count

    def update(self):
        """主循环调用，执行点击逻辑

        应在每帧调用，内部会判断是否到了点击时间。
        """
        if not self._active:
            return

        # 检查暂停键
        if self._pause_on_key:
            key_state = user32.GetAsyncKeyState(self._pause_vk)
            is_pressed = (key_state & 0x8000) != 0
            if is_pressed and not self._paused:
                self._paused = True
                logger.info("自动点击已暂停（暂停键按下）")
            elif not is_pressed and self._paused:
                self._paused = False
                logger.info("自动点击已恢复（暂停键释放）")

        if self._paused:
            return

        # 前台检查：仅在游戏窗口在前台时点击
        if self._foreground_only and self.game_monitor:
            if not self.game_monitor.is_foreground():
                return

        # 最大点击次数检查
        if self._max_clicks > 0 and self._click_count >= self._max_clicks:
            logger.info(f"已达到最大点击次数 ({self._max_clicks})，自动停止")
            self.stop()
            return

        # 时间间隔检查
        now = time.time()
        if now - self._last_click_time < self._interval:
            return

        # 执行点击
        self._do_click()
        self._click_count += 1
        self._last_click_time = now

    def _do_click(self):
        """执行一次鼠标点击（SendInput 硬件级注入）"""
        down_flag, up_flag = self._button_flags

        inputs = (INPUT * 2)()
        
        # 鼠标按下
        inputs[0].type = INPUT_MOUSE
        inputs[0].union.mi.dwFlags = down_flag
        inputs[0].union.mi.dx = 0
        inputs[0].union.mi.dy = 0

        # 鼠标释放
        inputs[1].type = INPUT_MOUSE
        inputs[1].union.mi.dwFlags = up_flag
        inputs[1].union.mi.dx = 0
        inputs[1].union.mi.dy = 0

        sent = user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
        if sent != 2:
            logger.warning(f"SendInput 发送失败: sent={sent}/2")

    def get_status_text(self) -> str:
        """获取状态文本（用于叠加层显示）"""
        if not self._active:
            return ""
        if self._paused:
            return f"⏸ 自动点击已暂停 ({self._click_count})"
        return f"🖱 自动点击中 ({self._click_count})"
