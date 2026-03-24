"""
D3OA — 全局热键管理器

使用 Win32 RegisterHotKey API 注册系统级热键。
不需要注入或 Hook，标准 Windows API 调用。

热键处理方式：
- 仅通过主线程的 poll() 方法处理热键消息
- 使用 PeekMessageW 非阻塞轮询
- MOD_NOREPEAT 防止单次按键触发多次
- 不启动后台线程，避免重复处理
"""

import ctypes
import ctypes.wintypes as wintypes
import logging

logger = logging.getLogger("D3OA.Hotkey")

user32 = ctypes.windll.user32

# ─── Win32 常量 ─────────────────────────────────────────

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# 虚拟键码映射
VK_MAP = {
    'F1': 0x70, 'F2': 0x71, 'F3': 0x72, 'F4': 0x73,
    'F5': 0x74, 'F6': 0x75, 'F7': 0x76, 'F8': 0x77,
    'F9': 0x78, 'F10': 0x79, 'F11': 0x7A, 'F12': 0x7B,
    '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
    '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
    'A': 0x41, 'B': 0x42, 'C': 0x43, 'D': 0x44, 'E': 0x45,
    'F': 0x46, 'G': 0x47, 'H': 0x48, 'I': 0x49, 'J': 0x4A,
    'K': 0x4B, 'L': 0x4C, 'M': 0x4D, 'N': 0x4E, 'O': 0x4F,
    'P': 0x50, 'Q': 0x51, 'R': 0x52, 'S': 0x53, 'T': 0x54,
    'U': 0x55, 'V': 0x56, 'W': 0x57, 'X': 0x58, 'Y': 0x59,
    'Z': 0x5A,
    'SPACE': 0x20, 'TAB': 0x09, 'ENTER': 0x0D, 'ESC': 0x1B,
    'INSERT': 0x2D, 'DELETE': 0x2E, 'HOME': 0x24, 'END': 0x23,
    'PAGEUP': 0x21, 'PAGEDOWN': 0x22,
    'UP': 0x26, 'DOWN': 0x28, 'LEFT': 0x25, 'RIGHT': 0x27,
}


def parse_hotkey(hotkey_str: str) -> tuple:
    """解析热键字符串，返回 (modifiers, vk_code)

    支持格式:
      - 'F8' -> (0, VK_F8)
      - 'Ctrl+F9' -> (MOD_CONTROL, VK_F9)
      - 'Ctrl+Shift+H' -> (MOD_CONTROL|MOD_SHIFT, VK_H)
      - 'Alt+F4' -> (MOD_ALT, VK_F4)
    """
    parts = hotkey_str.upper().split('+')
    modifiers = 0
    key = parts[-1].strip()

    for mod in parts[:-1]:
        mod = mod.strip()
        if mod in ('CTRL', 'CONTROL'):
            modifiers |= MOD_CONTROL
        elif mod == 'ALT':
            modifiers |= MOD_ALT
        elif mod == 'SHIFT':
            modifiers |= MOD_SHIFT
        elif mod == 'WIN':
            modifiers |= MOD_WIN

    vk = VK_MAP.get(key, 0)
    if vk == 0 and len(key) == 1:
        vk = ord(key)

    return modifiers, vk


class HotkeyManager:
    """全局热键管理器

    仅使用主线程 poll() 处理热键，避免后台线程竞争导致重复触发。
    """

    def __init__(self, config):
        self.config = config
        self._hotkeys = {}  # id -> (hotkey_str, callback)
        self._next_id = 1

    def register(self, hotkey_str: str, callback) -> int:
        """注册全局热键"""
        modifiers, vk = parse_hotkey(hotkey_str)
        if vk == 0:
            logger.error(f"无效的热键: {hotkey_str}")
            return -1

        hotkey_id = self._next_id
        self._next_id += 1

        # 添加 NOREPEAT 防止单次按键触发多次
        mod = modifiers | MOD_NOREPEAT

        if user32.RegisterHotKey(None, hotkey_id, mod, vk):
            self._hotkeys[hotkey_id] = (hotkey_str, callback)
            logger.info(f"热键已注册: {hotkey_str} (id={hotkey_id})")
        else:
            import ctypes
            err = ctypes.windll.kernel32.GetLastError()
            logger.error(f"热键注册失败: {hotkey_str} (GetLastError={err}, 可能被其他程序占用)")
            hotkey_id = -1

        return hotkey_id

    def unregister(self, hotkey_id: int):
        """注销热键"""
        if hotkey_id in self._hotkeys:
            user32.UnregisterHotKey(None, hotkey_id)
            hotkey_str = self._hotkeys[hotkey_id][0]
            del self._hotkeys[hotkey_id]
            logger.info(f"热键已注销: {hotkey_str}")

    def unregister_all(self):
        """注销所有热键"""
        for hotkey_id in list(self._hotkeys.keys()):
            user32.UnregisterHotKey(None, hotkey_id)
        self._hotkeys.clear()
        logger.info("所有热键已注销")

    def poll(self):
        """轮询热键消息（非阻塞，从主线程调用）

        使用 PeekMessageW + PM_REMOVE 提取消息。
        每次 poll 最多处理 10 条热键消息，防止热键风暴阻塞主线程。
        """
        msg = wintypes.MSG()
        count = 0
        while count < 10 and user32.PeekMessageW(
            ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, 1  # PM_REMOVE
        ):
            count += 1
            hotkey_id = msg.wParam
            if hotkey_id in self._hotkeys:
                hotkey_str, callback = self._hotkeys[hotkey_id]
                try:
                    callback()
                except Exception as e:
                    logger.error(f"热键回调执行失败 [{hotkey_str}]: {e}")
