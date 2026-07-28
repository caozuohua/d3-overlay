"""
D3OA — 透明叠加窗口管理器

使用 Win32 API 创建 WS_EX_LAYERED 分层窗口，实现像素级透明叠加。
支持点击穿透 (WS_EX_TRANSPARENT)，鼠标操作完全不影响游戏。
"""

import logging
import ctypes
import ctypes.wintypes as wintypes

logger = logging.getLogger("D3OA.Overlay")

# ─── Py3.14 ctypes 64 位截断修复 ───────────────────────────────────────────
# Python 3.14 对 ctypes 的默认参数类型做了更严格的检查：未声明 argtypes 时，
# HANDLE/HWND/HDC/HBITMAP 等 64 位句柄会被当成 32 位有符号值传入/返回，
# 高位丢失 → CreateDIBSection/UpdateLayeredWindow 等返回/接收无效句柄，
# 表现为 UpdateLayeredWindow 报 87(ERROR_INVALID_PARAMETER)、叠加层恒空白。
# 这里统一声明整套 GDI/User32 API 的 argtypes/restype。
def _setup_win32_argtypes():
    u = ctypes.windll.user32
    g = ctypes.windll.gdi32
    try:
        u.GetDC.argtypes = [wintypes.HWND]
        u.GetDC.restype = wintypes.HDC
        u.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        u.ReleaseDC.restype = ctypes.c_int
        u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        u.ShowWindow.restype = ctypes.c_int
        u.DestroyWindow.argtypes = [wintypes.HWND]
        u.DestroyWindow.restype = ctypes.c_int
        u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        u.GetWindowLongW.restype = ctypes.c_long
        u.DefWindowProcW.argtypes = [
            wintypes.HWND, wintypes.UINT,
            ctypes.c_ulonglong, ctypes.c_ulonglong,
        ]
        u.DefWindowProcW.restype = ctypes.c_ulonglong
        u.RegisterClassW.argtypes = [ctypes.c_void_p]
        u.RegisterClassW.restype = ctypes.c_ushort
        u.CreateWindowExW.argtypes = [
            wintypes.DWORD, ctypes.c_wchar_p, ctypes.c_wchar_p,
            wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HWND, wintypes.HANDLE, ctypes.c_void_p,
        ]
        u.CreateWindowExW.restype = wintypes.HWND
        u.SetLayeredWindowAttributes.argtypes = [
            wintypes.HWND, wintypes.COLORREF, ctypes.c_byte, wintypes.DWORD,
        ]
        u.SetLayeredWindowAttributes.restype = ctypes.c_int

        # UpdateLayeredWindow：hwnd/hdc 为 64 位句柄，未声明会被截断 → 87
        class BLENDFUNCTION(ctypes.Structure):
            _fields_ = [
                ("BlendOp", ctypes.c_byte),
                ("BlendFlags", ctypes.c_byte),
                ("SourceConstantAlpha", ctypes.c_byte),
                ("AlphaFormat", ctypes.c_byte),
            ]
        u.UpdateLayeredWindow.argtypes = [
            wintypes.HWND, wintypes.HDC,
            ctypes.POINTER(wintypes.POINT), ctypes.POINTER(wintypes.SIZE),
            wintypes.HDC, ctypes.POINTER(wintypes.POINT),
            wintypes.COLORREF, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD,
        ]
        u.UpdateLayeredWindow.restype = wintypes.BOOL

        # 关键：CreateDIBSection 返回 HBITMAP（>2^31），必须声明 restype
        g.CreateCompatibleDC.argtypes = [wintypes.HDC]
        g.CreateCompatibleDC.restype = wintypes.HDC
        g.DeleteDC.argtypes = [wintypes.HDC]
        g.DeleteDC.restype = ctypes.c_int
        g.DeleteObject.argtypes = [ctypes.c_void_p]
        g.DeleteObject.restype = ctypes.c_int
        g.SelectObject.argtypes = [wintypes.HDC, ctypes.c_void_p]
        g.SelectObject.restype = ctypes.c_void_p
        g.CreateDIBSection.argtypes = [
            wintypes.HDC, ctypes.c_void_p, ctypes.c_uint,
            ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_uint,
        ]
        g.CreateDIBSection.restype = wintypes.HBITMAP
    except Exception as e:  # pragma: no cover - 防御性
        logger.warning(f"设置 Win32 argtypes 失败（忽略）: {e}")


_setup_win32_argtypes()

# 尝试使用 pywin32
use_pywin32 = False
try:
    import win32gui
    import win32api
    import win32con
    import win32ui
    use_pywin32 = True
    logger.info("使用 pywin32 库")
except ImportError:
    logger.warning("pywin32 未安装，尝试使用 ctypes")
    import ctypes
    import ctypes.wintypes as wintypes

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
        # F1 修复：内部维护 pygame.Surface 作为插件渲染目标（见 get_surface）
        self._pygame_surface = None
        self._opacity = config.get('overlay.opacity', 0.85)
        self._click_through = config.get('overlay.click_through', True)

        # 探测 pygame 是否可用（不可用则退化为纯像素缓冲）
        self._pygame_ok = False
        try:
            import pygame
            self._pygame_ok = True
        except ImportError:
            logger.warning("pygame 不可用，叠加层将无内容渲染（插件依赖 pygame.Surface）")

    def create(self) -> bool:
        """创建透明叠加窗口"""
        if use_pywin32:
            return self._create_with_pywin32()
        else:
            return self._create_with_ctypes()

    def _create_with_pywin32(self) -> bool:
        """使用 pywin32 创建透明叠加窗口"""
        try:
            # 注册窗口类
            wc = win32gui.WNDCLASS()
            wc.lpszClassName = "D3OAOverlayClass"
            wc.style = win32con.CS_HREDRAW | win32con.CS_VREDRAW
            wc.hInstance = win32api.GetModuleHandle(None)
            wc.lpfnWndProc = win32gui.DefWindowProc
            wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
            wc.hbrBackground = win32con.COLOR_WINDOW
            class_atom = win32gui.RegisterClass(wc)

            # 计算屏幕大小
            screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

            # 创建窗口
            ex_style = (win32con.WS_EX_LAYERED | win32con.WS_EX_TOPMOST |
                        win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_NOACTIVATE)
            if self._click_through:
                ex_style |= win32con.WS_EX_TRANSPARENT

            self.hwnd = win32gui.CreateWindowEx(
                ex_style,
                class_atom,
                "D3OA Overlay",
                win32con.WS_POPUP,
                0, 0, screen_w, screen_h,
                None, None, wc.hInstance, None
            )

            if not self.hwnd:
                logger.error("窗口创建失败")
                return False

            # 设置窗口为分层窗口
            win32gui.SetLayeredWindowAttributes(self.hwnd, 0, int(self._opacity * 255), win32con.LWA_ALPHA)

            # 显示窗口
            win32gui.ShowWindow(self.hwnd, win32con.SW_SHOWNA)
            self.visible = True

            # 初始化表面
            self._width = screen_w
            self._height = screen_h
            self._recreate_surface(screen_w, screen_h)

            logger.info(f"叠加窗口创建成功 (pywin32): hwnd={self.hwnd}, size={screen_w}x{screen_h}")
            return True
        except Exception as e:
            logger.error(f"使用 pywin32 创建窗口失败: {e}")
            return False

    def _create_with_ctypes(self) -> bool:
        """使用 ctypes 创建透明叠加窗口"""
        try:
            # ─── Win32 常量 ─────────────────────────────────────────
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_TOPMOST = 0x00000008
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_NOACTIVATE = 0x08000000
            WS_POPUP = 0x80000000
            GWL_EXSTYLE = -20
            LWA_ALPHA = 0x00000002
            SW_SHOWNA = 8
            SM_CXSCREEN = 0
            SM_CYSCREEN = 1

            # Define LRESULT if not available in ctypes.wintypes
            try:
                LRESULT = wintypes.LRESULT
            except AttributeError:
                LRESULT = ctypes.c_long

            # ─── Win32 API 引用 ────────────────────────────────────
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # 定义 WNDCLASSEX 结构体
            class WNDCLASSEX(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_uint),
                    ("style", ctypes.c_uint),
                    ("lpfnWndProc", ctypes.CFUNCTYPE(LRESULT, ctypes.wintypes.HWND, ctypes.c_uint, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM)),
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

            # 定义窗口过程
            # Python 3.14 下，DefWindowProcW 默认 argtypes 为 32 位有符号，
            # 而 WM_* 消息的 wparam/lparam 高位（如指针）会超过 2^31 导致 OverflowError。
            # 显式将其 argtypes 设为 64 位无符号，避免溢出。
            user32.DefWindowProcW.argtypes = [
                ctypes.wintypes.HWND, ctypes.wintypes.UINT,
                ctypes.c_ulonglong, ctypes.c_ulonglong,
            ]
            user32.DefWindowProcW.restype = ctypes.c_ulonglong

            def wndproc(hwnd, msg, wparam, lparam):
                # 回调参数已是无符号 64 位，直接透传
                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

            # 注册窗口类
            hinstance = kernel32.GetModuleHandleW(None)
            wc = WNDCLASSEX()
            wc.cbSize = ctypes.sizeof(WNDCLASSEX)
            wc.style = 0
            wc.lpfnWndProc = ctypes.CFUNCTYPE(LRESULT, ctypes.wintypes.HWND, ctypes.c_uint, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM)(wndproc)
            wc.cbClsExtra = 0
            wc.cbWndExtra = 0
            wc.hInstance = hinstance
            wc.hIcon = None
            wc.hCursor = None
            wc.hbrBackground = None
            wc.lpszMenuName = None
            wc.lpszClassName = "D3OAOverlayClass"
            wc.hIconSm = None

            if not user32.RegisterClassW(ctypes.byref(wc)):
                error = ctypes.GetLastError()
                logger.error(f"窗口类注册失败，错误代码: {error}")
                return False

            # 创建窗口
            ex_style = (WS_EX_LAYERED | WS_EX_TOPMOST |
                        WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
            if self._click_through:
                ex_style |= WS_EX_TRANSPARENT

            screen_w = user32.GetSystemMetrics(SM_CXSCREEN)
            screen_h = user32.GetSystemMetrics(SM_CYSCREEN)

            self.hwnd = user32.CreateWindowExW(
                ex_style,
                "D3OAOverlayClass",
                "D3OA Overlay",
                WS_POPUP,
                0, 0, screen_w, screen_h,
                None, None, hinstance, None
            )

            if not self.hwnd:
                logger.error("窗口创建失败")
                return False

            # 设置透明度
            user32.SetLayeredWindowAttributes(
                self.hwnd, 0,
                int(self._opacity * 255),
                LWA_ALPHA
            )

            # 显示窗口
            user32.ShowWindow(self.hwnd, SW_SHOWNA)
            self.visible = True

            self._width = screen_w
            self._height = screen_h
            self._recreate_surface(screen_w, screen_h)

            logger.info(f"叠加窗口创建成功 (ctypes): hwnd={self.hwnd}, size={screen_w}x{screen_h}")
            return True
        except Exception as e:
            logger.error(f"使用 ctypes 创建窗口失败: {e}")
            return False

    def show(self):
        """显示叠加窗口"""
        if self.hwnd and not self.visible:
            if use_pywin32:
                win32gui.ShowWindow(self.hwnd, win32con.SW_SHOWNA)
            else:
                user32 = ctypes.windll.user32
                user32.ShowWindow(self.hwnd, 8)  # SW_SHOWNA
            self.visible = True

    def hide(self):
        """隐藏叠加窗口"""
        if self.hwnd and self.visible:
            if use_pywin32:
                win32gui.ShowWindow(self.hwnd, win32con.SW_HIDE)
            else:
                user32 = ctypes.windll.user32
                user32.ShowWindow(self.hwnd, 0)  # SW_HIDE
            self.visible = False

    def toggle_visibility(self):
        """切换可见性"""
        if self.visible:
            self.hide()
        else:
            self.show()

    def sync_to_game_window(self):
        """将叠加窗口同步到游戏窗口位置"""
        if use_pywin32:
            game_hwnd = win32gui.FindWindow("D3 Main Window Class", None)
            if not game_hwnd:
                return False

            rect = win32gui.GetWindowRect(game_hwnd)
            x, y, right, bottom = rect
            w, h = right - x, bottom - y

            if w != self._width or h != self._height:
                self._width = w
                self._height = h
                self._recreate_surface(w, h)

            win32gui.MoveWindow(self.hwnd, x, y, w, h, False)
            return True
        else:
            user32 = ctypes.windll.user32
            game_hwnd = user32.FindWindowW("D3 Main Window Class", None)
            if not game_hwnd:
                return False

            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            rect = RECT()
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
            if use_pywin32:
                win32gui.SetLayeredWindowAttributes(self.hwnd, 0, int(self._opacity * 255), win32con.LWA_ALPHA)
            else:
                user32 = ctypes.windll.user32
                LWA_ALPHA = 0x00000002
                user32.SetLayeredWindowAttributes(
                    self.hwnd, 0,
                    int(self._opacity * 255),
                    LWA_ALPHA
                )

    def set_click_through(self, enabled: bool):
        """启用/禁用点击穿透"""
        self._click_through = enabled
        if self.hwnd:
            if use_pywin32:
                ex_style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
                if enabled:
                    ex_style |= win32con.WS_EX_TRANSPARENT
                else:
                    ex_style &= ~win32con.WS_EX_TRANSPARENT
                win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, ex_style)
            else:
                user32 = ctypes.windll.user32
                GWL_EXSTYLE = -20
                WS_EX_TRANSPARENT = 0x00000020
                ex_style = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
                if enabled:
                    ex_style |= WS_EX_TRANSPARENT
                else:
                    ex_style &= ~WS_EX_TRANSPARENT
                user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, ex_style)

    def begin_frame(self):
        """开始新一帧渲染：清空内部 pygame.Surface（全透明）"""
        if self._pygame_surface is not None:
            self._pygame_surface.fill((0, 0, 0, 0))  # F4: 用 fill 替代逐像素循环
        elif self._pixels:
            # 退化路径：直接清空 DIB 缓冲
            try:
                import ctypes
                ctypes.memset(self._pixels, 0, len(self._pixels))
            except Exception:
                for i in range(0, len(self._pixels), 4):
                    self._pixels[i] = self._pixels[i+1] = self._pixels[i+2] = self._pixels[i+3] = 0

    def _sync_pygame_to_dib(self):
        """将内部 pygame.Surface 的像素写回 DIB 缓冲 (self._pixels)。

        F1 修复关键：插件渲染到 pygame.Surface，必须把其 BGRA 字节拷进
        self._pixels（DIB 内存），窗口才能显示。
        """
        if self._pygame_surface is None or self._pixels is None:
            return
        try:
            import pygame
            buf = pygame.image.tostring(self._pygame_surface, 'BGRA')
            n = min(len(buf), len(self._pixels))
            # self._pixels 是 ctypes 数组，用 memoryview 切片赋值最快
            self._pixels[:n] = buf[:n]
        except Exception as e:
            logger.error(f"pygame 像素写回 DIB 失败: {e}")

    def end_frame(self):
        """结束帧渲染，推送到叠加窗口。

        统一用 ctypes UpdateLayeredWindow 推屏（与 _recreate_surface 的
        DIBSection 像素缓冲一致），无论窗口由 pywin32 还是 ctypes 创建。
        """
        if not self.hwnd:
            return

        # 先把 pygame 渲染结果同步进 DIB 缓冲
        self._sync_pygame_to_dib()

        try:
            user32 = ctypes.windll.user32

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

            AC_SRC_OVER = 0x00
            AC_SRC_ALPHA = 0x01
            ULW_ALPHA = 0x00000002

            blend = BLENDFUNCTION()
            blend.BlendOp = AC_SRC_OVER
            blend.BlendFlags = 0
            blend.SourceConstantAlpha = 255
            blend.AlphaFormat = AC_SRC_ALPHA

            wnd_pos = POINT(0, 0)
            size = SIZE(self._width, self._height)
            src_pos = POINT(0, 0)

            hdc_screen = user32.GetDC(None)

            ret = user32.UpdateLayeredWindow(
                self.hwnd, hdc_screen,
                None, ctypes.byref(size),
                self.hdc_mem, ctypes.byref(src_pos),
                0, ctypes.byref(blend), ULW_ALPHA
            )
            if not ret:
                logger.error(f"更新窗口失败: UpdateLayeredWindow 返回 0, GetLastError={ctypes.windll.kernel32.GetLastError()}")

            user32.ReleaseDC(None, hdc_screen)
        except Exception as e:
            logger.error(f"更新窗口失败: {e}")

    def get_surface(self):
        """返回插件渲染目标（pygame.Surface）。

        F1 修复：main 循环把此 surface 交给插件 .blit()，end_frame 再写回 _pixels。
        若 pygame 不可用则返回 None（叠加层无内容，但不崩溃）。
        """
        return self._pygame_surface

    def _recreate_surface(self, w, h):
        """重建渲染表面。

        设计（F1 修复）：窗口由 pywin32 或 ctypes 创建（仅 hwnd），
        但像素缓冲统一用 ctypes CreateDIBSection —— 这样：
          1) 内部 pygame.Surface 渲染后能可靠写回 _pixels；
          2) end_frame 用 UpdateLayeredWindow 推屏，两个窗口分支都能用。
        """
        # 清理旧的
        if self.hbitmap:
            try:
                gdi32 = ctypes.windll.gdi32
                gdi32.DeleteObject(self.hbitmap)
            except Exception:
                pass
        if self.hdc_mem:
            try:
                gdi32 = ctypes.windll.gdi32
                gdi32.DeleteDC(self.hdc_mem)
            except Exception:
                pass
        self.hbitmap = None
        self.hdc_mem = None

        # 统一创建内部 pygame.Surface（插件渲染目标）
        if self._pygame_ok:
            try:
                import pygame
                pygame.font.init()  # 确保字体模块可用（插件用 pygame.font.Font）
                self._pygame_surface = pygame.Surface((w, h), pygame.SRCALPHA)
                logger.info(f"pygame 渲染表面重建: {w}x{h}")
            except Exception as e:
                logger.error(f"创建 pygame 渲染表面失败: {e}")
                self._pygame_surface = None

        # 统一用 ctypes DIBSection 作为像素缓冲（与窗口分支解耦）
        try:
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32

            hdc_screen = user32.GetDC(None)
            self.hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)

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

            buf_size = w * h * 4
            self._pixels = (ctypes.c_byte * buf_size).from_address(pixels_ptr.value)

            user32.ReleaseDC(None, hdc_screen)
            logger.info(f"渲染缓冲(DIBSection)重建: {w}x{h}")
        except Exception as e:
            logger.error(f"创建 DIBSection 失败: {e}")
            self._pixels = None

    def destroy(self):
        """销毁叠加窗口"""
        if self.hbitmap:
            try:
                if use_pywin32:
                    # 检查是否是有效的 PyHANDLE 对象
                    if hasattr(self.hbitmap, 'Detach') or hasattr(self.hbitmap, '__int__'):
                        win32gui.DeleteObject(self.hbitmap)
                else:
                    gdi32 = ctypes.windll.gdi32
                    gdi32.DeleteObject(self.hbitmap)
            except Exception as e:
                logger.error(f"销毁 hbitmap 失败: {e}")
        if self.hdc_mem:
            try:
                if use_pywin32:
                    # 检查是否是有效的 DC 对象
                    if hasattr(self.hdc_mem, 'DeleteDC'):
                        self.hdc_mem.DeleteDC()
                else:
                    gdi32 = ctypes.windll.gdi32
                    gdi32.DeleteDC(self.hdc_mem)
            except Exception as e:
                logger.error(f"销毁 hdc_mem 失败: {e}")
        if self.hwnd:
            try:
                if use_pywin32:
                    win32gui.DestroyWindow(self.hwnd)
                else:
                    user32 = ctypes.windll.user32
                    user32.DestroyWindow(self.hwnd)
                self.hwnd = None
            except Exception as e:
                logger.error(f"销毁窗口失败: {e}")
        logger.info("叠加窗口已销毁")

    def cycle_layout(self):
        """切换布局模式（F5 修复：实际重定位面板，而非仅改无效配置键）"""
        positions = ['top-right', 'top-left', 'bottom-right', 'bottom-left']
        current = self.config.get('overlay.position', 'top-right')
        idx = positions.index(current) if current in positions else 0
        next_pos = positions[(idx + 1) % len(positions)]
        self.config.set('overlay.position', next_pos)
        self._layout = next_pos
        logger.info(f"布局切换到: {next_pos}")

    def place(self, x: int, y: int) -> tuple:
        """F5 修复：把插件的基坐标（以 top-left 为原点）映射到当前布局角落。

        画布尺寸为 self._width/self._height；面板以 20px 边距对齐到所选角落。
        """
        margin = 20
        w, h = self._width, self._height
        corner = getattr(self, '_layout', self.config.get('overlay.position', 'top-right'))
        if corner == 'top-left':
            return (margin, margin)
        if corner == 'top-right':
            return (max(margin, w - x - 260), margin) if w else (margin, margin)
        if corner == 'bottom-left':
            return (margin, max(margin, h - y - 200)) if h else (margin, margin)
        if corner == 'bottom-right':
            return (max(margin, w - x - 260), max(margin, h - y - 200)) if (w and h) else (margin, margin)
        return (x, y)