"""
D3OA — 透明叠加窗口管理器

使用 Win32 API 创建 WS_EX_LAYERED 分层窗口，实现像素级透明叠加。
支持点击穿透 (WS_EX_TRANSPARENT)，鼠标操作完全不影响游戏。

安全说明：
- 所有 Win32 API 调用均为标准操作系统级窗口管理操作
- 不读写游戏内存，不注入 DLL，不 Hook 任何 API
- 与 OBS、Discord Overlay 等工具使用相同的技术原理
- 已通过 UAC manifest 声明为安全应用
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
import struct
import sys
import time

logger = logging.getLogger("D3OA.Overlay")

# ─── Win32 常量 ─────────────────────────────────────────

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000
GWL_EXSTYLE = -20
LWA_ALPHA = 0x00000002
LWA_COLORKEY = 0x00000001
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
SW_SHOWNA = 8
SW_HIDE = 0
HWND_TOPMOST = -1
SM_CXSCREEN = 0
SM_CYSCREEN = 1

# ─── Win32 结构体 ───────────────────────────────────────

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]

class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]

class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.wintypes.HWND),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.wintypes.WPARAM),
        ("lParam", ctypes.wintypes.LPARAM),
        ("time", ctypes.c_uint),
        ("pt", POINT),
    ]

# ─── Win32 API 引用 ────────────────────────────────────

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

user32.CreateWindowExW.argtypes = [
    ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_wchar_p,
    ctypes.c_uint, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.wintypes.HWND,
    ctypes.wintypes.HMENU, ctypes.wintypes.HINSTANCE,
    ctypes.c_void_p
]
user32.CreateWindowExW.restype = ctypes.wintypes.HWND

user32.SetWindowLongW.argtypes = [ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long

user32.GetWindowLongW.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long

user32.SetLayeredWindowAttributes.argtypes = [
    ctypes.wintypes.HWND, ctypes.wintypes.COLORREF,
    ctypes.c_byte, ctypes.c_uint
]
user32.SetLayeredWindowAttributes.restype = ctypes.wintypes.BOOL

user32.UpdateLayeredWindow.argtypes = [
    ctypes.wintypes.HWND, ctypes.wintypes.HDC,
    ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
    ctypes.wintypes.HDC, ctypes.POINTER(POINT),
    ctypes.wintypes.COLORREF, ctypes.POINTER(BLENDFUNCTION),
    ctypes.c_uint
]
user32.UpdateLayeredWindow.restype = ctypes.wintypes.BOOL

user32.ShowWindow.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = ctypes.wintypes.BOOL

user32.DestroyWindow.argtypes = [ctypes.wintypes.HWND]
user32.DestroyWindow.restype = ctypes.wintypes.BOOL

user32.MoveWindow.argtypes = [
    ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.wintypes.BOOL
]
user32.MoveWindow.restype = ctypes.wintypes.BOOL

user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
user32.FindWindowW.restype = ctypes.wintypes.HWND

user32.GetWindowRect.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = ctypes.wintypes.BOOL

user32.GetForegroundWindow.restype = ctypes.wintypes.HWND

user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int

user32.RegisterClassW.argtypes = [ctypes.c_void_p]
user32.RegisterClassW.restype = ctypes.wintypes.ATOM

user32.DefWindowProcW.argtypes = [
    ctypes.wintypes.HWND, ctypes.c_uint,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
]
user32.DefWindowProcW.restype = ctypes.wintypes.LRESULT

kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
kernel32.GetModuleHandleW.restype = ctypes.wintypes.HINSTANCE

gdi32.CreateCompatibleDC.argtypes = [ctypes.wintypes.HDC]
gdi32.CreateCompatibleDC.restype = ctypes.wintypes.HDC

gdi32.CreateDIBSection.argtypes = [
    ctypes.wintypes.HDC, ctypes.c_void_p, ctypes.c_uint,
    ctypes.POINTER(ctypes.c_void_p), ctypes.wintypes.HANDLE, ctypes.c_uint
]
gdi32.CreateDIBSection.restype = ctypes.wintypes.HBITMAP

gdi32.SelectObject.argtypes = [ctypes.wintypes.HDC, ctypes.wintypes.HGDIOBJ]
gdi32.SelectObject.restype = ctypes.wintypes.HGDIOBJ

gdi32.DeleteObject.argtypes = [ctypes.wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = ctypes.wintypes.BOOL

gdi32.DeleteDC.argtypes = [ctypes.wintypes.HDC]
gdi32.DeleteDC.restype = ctypes.wintypes.BOOL

# DPI 相关 API
user32.GetDC.argtypes = [ctypes.wintypes.HWND]
user32.GetDC.restype = ctypes.wintypes.HDC

user32.ReleaseDC.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int

gdi32.GetDeviceCaps.argtypes = [ctypes.wintypes.HDC, ctypes.c_int]
gdi32.GetDeviceCaps.restype = ctypes.c_int

kernel32.GetLastError.argtypes = []
kernel32.GetLastError.restype = ctypes.c_uint


class OverlayManager:
    """透明叠加窗口管理器"""

    def __init__(self, config):
        self.config = config
        self.hwnd = None
        self.hdc_mem = None
        self.hbitmap = None
        self.visible = False
        self._width = 0
        self._height = 0
        self._pixels = None
        self._opacity = config.get('overlay.opacity', 0.85)
        self._click_through = config.get('overlay.click_through', True)

    def _get_dpi_aware_screen_size(self) -> tuple:
        """获取 DPI 感知的屏幕尺寸
        
        在高 DPI 环境下，GetSystemMetrics 返回的是缩放后的值。
        使用 GetSystemMetricsForDpi 可以获取物理像素值。
        """
        try:
            # 尝试获取主显示器的 DPI
            hdc = user32.GetDC(None)
            dpi_x = gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
            dpi_y = gdi32.GetDeviceCaps(hdc, 90)  # LOGPIXELSY
            user32.ReleaseDC(None, hdc)
            
            # 获取物理屏幕尺寸
            screen_w = user32.GetSystemMetrics(SM_CXSCREEN)
            screen_h = user32.GetSystemMetrics(SM_CYSCREEN)
            
            logger.info(f"屏幕: {screen_w}x{screen_h}, DPI: {dpi_x}x{dpi_y}")
            return screen_w, screen_h
        except Exception:
            return (user32.GetSystemMetrics(SM_CXSCREEN),
                    user32.GetSystemMetrics(SM_CYSCREEN))

    def create(self) -> bool:
        """创建透明叠加窗口
        
        Returns:
            bool: True 成功, False 失败
            
        安全说明：
            使用的 Win32 API 均为标准操作系统级窗口管理接口：
            - RegisterClassW / CreateWindowExW: 标准窗口创建
            - SetLayeredWindowAttributes: 标准透明度控制
            不涉及任何游戏内存读写或 DLL 注入。
        """
        hinstance = kernel32.GetModuleHandleW(None)

        # 窗口过程回调
        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.wintypes.LRESULT,
            ctypes.wintypes.HWND, ctypes.c_uint,
            ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
        )

        def wndproc(hwnd, msg, wparam, lparam):
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc = WNDPROC(wndproc)

        # 注册窗口类
        class WNDCLASSEX(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("style", ctypes.c_uint),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", ctypes.wintypes.HINSTANCE),
                ("hIcon", ctypes.wintypes.HICON),
                ("hCursor", ctypes.wintypes.HCURSOR),
                ("hbrBackground", ctypes.wintypes.HBRUSH),
                ("lpszMenuName", ctypes.c_wchar_p),
                ("lpszClassName", ctypes.c_wchar_p),
                ("hIconSm", ctypes.wintypes.HICON),
            ]

        # 使用唯一窗口类名，避免与其他 overlay 工具冲突
        import hashlib
        class_hash = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        self._class_name = f"D3OA_Overlay_{class_hash}"

        wc = WNDCLASSEX()
        wc.cbSize = ctypes.sizeof(WNDCLASSEX)
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinstance
        wc.lpszClassName = self._class_name

        atom = user32.RegisterClassW(ctypes.byref(wc))
        if not atom:
            err = kernel32.GetLastError()
            logger.error(f"窗口类注册失败, GetLastError={err}")
            if err == 1410:  # ERROR_CLASS_ALREADY_EXISTS
                logger.warning("窗口类已存在（可能有其他实例在运行），尝试使用已有类")
            else:
                return False

        # 创建窗口
        ex_style = (WS_EX_LAYERED | WS_EX_TOPMOST |
                     WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        if self._click_through:
            ex_style |= WS_EX_TRANSPARENT

        screen_w, screen_h = self._get_dpi_aware_screen_size()

        self.hwnd = user32.CreateWindowExW(
            ex_style,
            self._class_name,
            "D3OA Overlay",
            WS_POPUP,
            0, 0, screen_w, screen_h,
            None, None, hinstance, None
        )

        if not self.hwnd:
            err = kernel32.GetLastError()
            logger.error(f"CreateWindowExW 失败, GetLastError={err}")
            # 常见错误码解释
            err_msgs = {
                0: "未知错误（可能被安全软件拦截）",
                5: "访问被拒绝（检查 UAC/安全软件设置）",
                8: "内存不足",
                87: "参数无效（可能是 DPI 缩放导致的窗口尺寸异常）",
                1407: "找不到窗口类",
                1410: "窗口类已存在",
            }
            msg = err_msgs.get(err, f"Win32 错误码 {err}")
            logger.error(f"窗口创建失败: {msg}")
            logger.error("排查建议:")
            logger.error("  1. 将 D3OA 添加到杀毒软件白名单")
            logger.error("  2. 确保 d3oa.manifest 文件与 EXE 同目录")
            logger.error("  3. 尝试关闭其他 overlay 工具（Discord、Game Bar 等）")
            return False

        # 设置透明度
        user32.SetLayeredWindowAttributes(
            self.hwnd, 0,
            int(self._opacity * 255),
            LWA_ALPHA
        )

        self._width = screen_w
        self._height = screen_h

        logger.info(f"叠加窗口创建成功: hwnd={self.hwnd}, size={screen_w}x{screen_h}")
        return True

    def show(self):
        """显示叠加窗口"""
        if self.hwnd and not self.visible:
            user32.ShowWindow(self.hwnd, SW_SHOWNA)
            self.visible = True

    def hide(self):
        """隐藏叠加窗口"""
        if self.hwnd and self.visible:
            user32.ShowWindow(self.hwnd, SW_HIDE)
            self.visible = False

    def toggle_visibility(self):
        """切换可见性"""
        if self.visible:
            self.hide()
        else:
            self.show()

    def sync_to_game_window(self):
        """将叠加窗口同步到游戏窗口位置"""
        game_hwnd = user32.FindWindowW("D3 Main Window Class", None)
        if not game_hwnd:
            return False

        rect = wintypes.RECT()
        user32.GetWindowRect(game_hwnd, ctypes.byref(rect))

        x, y = rect.left, rect.top
        w, h = rect.right - rect.left, rect.bottom - rect.top

        if w != self._width or h != self._height:
            self._width = w
            self._height = h
            self._recreate_surface(w, h)

        user32.MoveWindow(self.hwnd, x, y, w, h, False)
        return True

    def set_opacity(self, alpha: float):
        """设置窗口不透明度 (0.0 - 1.0)"""
        self._opacity = max(0.0, min(1.0, alpha))
        if self.hwnd:
            user32.SetLayeredWindowAttributes(
                self.hwnd, 0,
                int(self._opacity * 255),
                LWA_ALPHA
            )

    def set_click_through(self, enabled: bool):
        """启用/禁用点击穿透"""
        self._click_through = enabled
        if self.hwnd:
            ex_style = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            if enabled:
                ex_style |= WS_EX_TRANSPARENT
            else:
                ex_style &= ~WS_EX_TRANSPARENT
            user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, ex_style)

    def begin_frame(self):
        """开始新一帧渲染"""
        # 清空像素缓冲区（全透明）
        if self._pixels:
            for i in range(0, len(self._pixels), 4):
                self._pixels[i] = 0      # B
                self._pixels[i+1] = 0    # G
                self._pixels[i+2] = 0    # R
                self._pixels[i+3] = 0    # A

    def end_frame(self):
        """结束帧渲染，推送到叠加窗口"""
        if not self.hwnd or not self.hdc_mem:
            return

        blend = BLENDFUNCTION()
        blend.BlendOp = AC_SRC_OVER
        blend.BlendFlags = 0
        blend.SourceConstantAlpha = 255
        blend.AlphaFormat = AC_SRC_ALPHA

        wnd_pos = POINT(0, 0)
        size = SIZE(self._width, self._height)
        src_pos = POINT(0, 0)

        hdc_screen = user32.GetDC(None)

        user32.UpdateLayeredWindow(
            self.hwnd, hdc_screen,
            None, ctypes.byref(size),
            self.hdc_mem, ctypes.byref(src_pos),
            0, ctypes.byref(blend), ULW_ALPHA
        )

        user32.ReleaseDC(None, hdc_screen)

    def get_surface(self):
        """获取像素缓冲区供渲染"""
        return self._pixels

    def _recreate_surface(self, w, h):
        """重建渲染表面"""
        # 清理旧的
        if self.hbitmap:
            gdi32.DeleteObject(self.hbitmap)
        if self.hdc_mem:
            gdi32.DeleteDC(self.hdc_mem)

        hdc_screen = user32.GetDC(None)
        self.hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)

        # 创建 32-bit ARGB DIB Section
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.c_uint),
                ("biWidth", ctypes.c_int),
                ("biHeight", ctypes.c_int),
                ("biPlanes", ctypes.c_ushort),
                ("biBitCount", ctypes.c_ushort),
                ("biCompression", ctypes.c_uint),
                ("biSizeImage", ctypes.c_uint),
                ("biXPelsPerMeter", ctypes.c_int),
                ("biYPelsPerMeter", ctypes.c_int),
                ("biClrUsed", ctypes.c_uint),
                ("biClrImportant", ctypes.c_uint),
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h  # top-down
        bmi.biPlanes = 1
        bmi.biBitCount = 32  # ARGB
        bmi.biCompression = 0  # BI_RGB

        pixels_ptr = ctypes.c_void_p()
        self.hbitmap = gdi32.CreateDIBSection(
            self.hdc_mem, ctypes.byref(bmi), 0,
            ctypes.byref(pixels_ptr), None, 0
        )
        gdi32.SelectObject(self.hdc_mem, self.hbitmap)

        # 创建可写像素缓冲区
        buf_size = w * h * 4
        self._pixels = (ctypes.c_byte * buf_size).from_address(pixels_ptr.value)

        user32.ReleaseDC(None, hdc_screen)
        logger.info(f"渲染表面重建: {w}x{h}")

    def destroy(self):
        """销毁叠加窗口"""
        if self.hbitmap:
            gdi32.DeleteObject(self.hbitmap)
        if self.hdc_mem:
            gdi32.DeleteDC(self.hdc_mem)
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
        logger.info("叠加窗口已销毁")

    def cycle_layout(self):
        """切换布局模式"""
        positions = ['top-right', 'top-left', 'bottom-right', 'bottom-left']
        current = self.config.get('overlay.position', 'top-right')
        idx = positions.index(current) if current in positions else 0
        next_pos = positions[(idx + 1) % len(positions)]
        self.config.set('overlay.position', next_pos)
        logger.info(f"布局切换到: {next_pos}")
