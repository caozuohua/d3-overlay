"""
D3OA — 渲染引擎

基于 Pygame 的 UI 渲染，输出 ARGB 像素传给 Win32 叠加窗口。
"""

import logging
from typing import Optional

logger = logging.getLogger("D3OA.Renderer")

# 尝试导入 Pygame，不可用则降级到纯 Python 渲染
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    logger.warning("Pygame 不可用，使用基础渲染模式")


class Theme:
    """渲染主题"""

    THEMES = {
        'dark': {
            'bg': (20, 20, 20, 180),
            'text': (220, 220, 220, 255),
            'accent': (255, 165, 0, 255),
            'border': (80, 80, 80, 200),
            'highlight': (255, 200, 50, 255),
            'success': (80, 200, 80, 255),
            'warning': (255, 200, 0, 255),
            'danger': (255, 60, 60, 255),
        },
        'light': {
            'bg': (240, 240, 240, 200),
            'text': (40, 40, 40, 255),
            'accent': (0, 120, 215, 255),
            'border': (180, 180, 180, 200),
            'highlight': (0, 120, 215, 255),
            'success': (40, 160, 40, 255),
            'warning': (200, 150, 0, 255),
            'danger': (200, 40, 40, 255),
        },
        'd3': {
            'bg': (10, 8, 5, 200),
            'text': (210, 180, 120, 255),
            'accent': (255, 140, 0, 255),
            'border': (120, 90, 40, 200),
            'highlight': (255, 200, 50, 255),
            'success': (80, 200, 80, 255),
            'warning': (255, 200, 0, 255),
            'danger': (200, 40, 40, 255),
        }
    }

    def __init__(self, name='dark'):
        self.name = name
        self.colors = self.THEMES.get(name, self.THEMES['dark'])

    def get(self, key: str) -> tuple:
        return self.colors.get(key, (255, 255, 255, 255))


class TextRenderer:
    """文字渲染器"""

    def __init__(self, font_name="Microsoft YaHei", font_size=14):
        self.font_name = font_name
        self.font_size = font_size
        self._font = None

        if PYGAME_AVAILABLE:
            try:
                pygame.font.init()
                self._font = pygame.font.SysFont(font_name, font_size)
                if not self._font:
                    self._font = pygame.font.SysFont(None, font_size)
            except Exception as e:
                logger.warning(f"字体初始化失败: {e}")

    def render(self, text: str, color: tuple = (255, 255, 255, 255)) -> Optional['pygame.Surface']:
        """渲染文字为 Surface"""
        if not PYGAME_AVAILABLE or not self._font:
            return None
        try:
            surface = self._font.render(text, True, color[:3])
            return surface
        except Exception:
            return None

    def get_size(self, text: str) -> tuple:
        """获取文字渲染尺寸"""
        if self._font:
            return self._font.size(text)
        return (len(text) * self.font_size // 2, self.font_size)


class Panel:
    """UI 面板 — 一个可渲染的矩形区域"""

    def __init__(self, x: int, y: int, width: int, height: int, theme: Theme):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.theme = theme
        self.visible = True
        self.lines = []  # (text, color_key)

    def add_line(self, text: str, color_key: str = 'text'):
        """添加一行文字"""
        self.lines.append((text, color_key))

    def clear(self):
        """清空内容"""
        self.lines.clear()

    def render(self, text_renderer: TextRenderer, surface):
        """渲染到目标 Surface"""
        if not self.visible or not PYGAME_AVAILABLE:
            return

        # 背景
        bg_color = self.theme.get('bg')
        bg_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        bg_surface.fill(bg_color)
        surface.blit(bg_surface, (self.x, self.y))

        # 边框
        border_color = self.theme.get('border')
        pygame.draw.rect(surface, border_color,
                         (self.x, self.y, self.width, self.height), 1, border_radius=4)

        # 文字行
        y_offset = self.y + 8
        for text, color_key in self.lines:
            color = self.theme.get(color_key)
            text_surf = text_renderer.render(text, color)
            if text_surf:
                surface.blit(text_surf, (self.x + 8, y_offset))
                y_offset += text_surf.get_height() + 4


class Renderer:
    """主渲染器"""

    def __init__(self, config):
        self.config = config
        self.theme = Theme(config.get('ui.theme', 'dark'))
        self.text_renderer = TextRenderer(
            font_name=config.get('ui.font_name', 'Microsoft YaHei'),
            font_size=config.get('overlay.font_size', 14)
        )
        self.panels = {}
        self._surface = None

    def create_surface(self, width: int, height: int):
        """创建渲染表面"""
        if PYGAME_AVAILABLE:
            self._surface = pygame.Surface((width, height), pygame.SRCALPHA)

    def add_panel(self, name: str, panel: Panel):
        """添加面板"""
        self.panels[name] = panel

    def remove_panel(self, name: str):
        """移除面板"""
        self.panels.pop(name, None)

    def render_frame(self):
        """渲染完整帧"""
        if not PYGAME_AVAILABLE or not self._surface:
            return None

        # 清空
        self._surface.fill((0, 0, 0, 0))

        # 渲染所有面板
        for panel in self.panels.values():
            panel.render(self.text_renderer, self._surface)

        return self._surface

    def get_pixel_buffer(self) -> Optional[bytes]:
        """获取像素缓冲区 (BGRA 格式)"""
        if self._surface:
            return pygame.image.tostring(self._surface, 'BGRA')
        return None
