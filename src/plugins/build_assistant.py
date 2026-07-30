"""
D3OA 插件 — 练级出装/技能天赋推荐助手

提供练级路径、装备搭配及技能天赋组合推荐。
"""

import logging
from plugin_manager import PluginBase

logger = logging.getLogger("D3OA.Plugin.BuildAssistant")


class Plugin(PluginBase):
    """练级出装/技能天赋推荐助手"""

    @property
    def name(self) -> str:
        return "BuildAssistant"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def description(self) -> str:
        return "练级出装/技能天赋推荐助手"

    def on_init(self, context: dict):
        self.config = context['config']
        self.overlay = context.get('overlay')
        self.data_provider = context.get('data_provider')
        self._data_loaded = False
        logger.info("BuildAssistant 插件初始化完成")

    def on_update(self, delta_time: float, game_data: dict):
        """占位：未来扩展解析 build / skill / paragon 推荐数据。"""
        pass

    def on_render(self, surface):
        """渲染推荐助手占位面板"""
        try:
            import pygame
        except ImportError:
            return

        pos = self.config.get('plugins.build_assistant.position', [20, 660])
        x, y = pos
        if self.overlay and hasattr(self.overlay, 'place'):
            x, y = self.overlay.place(x, y)

        panel_w, panel_h = 200, 40
        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((20, 80, 40, 210))
        surface.blit(bg, (x, y))

        dash_color = (100, 255, 150, 240)
        for i in range(0, panel_w, 8):
            pygame.draw.line(surface, dash_color, (x + i, y), (x + i + 4, y))
            pygame.draw.line(surface, dash_color, (x + i, y + panel_h - 1), (x + i + 4, y + panel_h - 1))
        for i in range(0, panel_h, 8):
            pygame.draw.line(surface, dash_color, (x, y + i), (x, y + i + 4))
            pygame.draw.line(surface, dash_color, (x + panel_w - 1, y + i), (x + panel_w - 1, y + i + 4))

        try:
            if self.overlay and hasattr(self.overlay, 'get_font'):
                font = self.overlay.get_font(None, 14)
            else:
                font = pygame.font.Font(None, 14)
        except Exception:
            font = pygame.font.Font(None, 14)

        text = "BuildAssistant: 数据已加载" if self._data_loaded else "BuildAssistant: 等待数据"
        text_surf = font.render(text, True, (180, 255, 200))
        text_x = x + (panel_w - text_surf.get_width()) // 2
        text_y = y + (panel_h - text_surf.get_height()) // 2
        surface.blit(text_surf, (text_x, text_y))

        if self.overlay and hasattr(self.overlay, 'register_panel_rect'):
            self.overlay.register_panel_rect(self.name, pygame.Rect(x, y, panel_w, panel_h))
