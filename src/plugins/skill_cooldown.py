"""
D3OA 插件 — 技能冷却（占位）

追踪技能冷却状态，供后续扩展。
"""

import logging
from plugin_manager import PluginBase

logger = logging.getLogger("D3OA.Plugin.SkillCooldown")


class Plugin(PluginBase):
    """技能冷却（占位）"""

    @property
    def name(self) -> str:
        return "SkillCooldown"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def description(self) -> str:
        return "技能冷却（占位）"

    def on_init(self, context: dict):
        self.config = context['config']
        self.overlay = context.get('overlay')
        self.data_provider = context.get('data_provider')
        self._skills = {}
        logger.info("SkillCooldown 插件初始化完成")

    def on_update(self, delta_time: float, game_data: dict):
        """占位：未来扩展解析技能冷却事件并更新 _skills"""
        pass

    def on_render(self, surface):
        """渲染技能冷却面板"""
        try:
            import pygame
        except ImportError:
            return

        pos = self.config.get('plugins.skill_cooldown.position', [20, 700])
        x, y = pos
        if self.overlay and hasattr(self.overlay, 'place'):
            x, y = self.overlay.place(x, y)

        panel_w, panel_h = 200, 40
        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((20, 50, 100, 210))
        surface.blit(bg, (x, y))

        dash_color = (100, 150, 255, 240)
        for i in range(0, panel_w, 8):
            pygame.draw.line(surface, dash_color, (x + i, y), (x + i + 4, y))
            pygame.draw.line(surface, dash_color, (x + i, y + panel_h - 1), (x + i + 4, y + panel_h - 1))
        for i in range(0, panel_h, 8):
            pygame.draw.line(surface, dash_color, (x, y + i), (x, y + i + 4))
            pygame.draw.line(surface, dash_color, (x + panel_w - 1, y + i), (x + panel_w - 1, y + i + 4))

        try:
            font = pygame.font.Font(None, 14)
        except Exception:
            font = pygame.font.Font(None, 16)

        text = "SkillCooldown: 等待技能事件..."
        text_surf = font.render(text, True, (200, 220, 255))
        text_x = x + (panel_w - text_surf.get_width()) // 2
        text_y = y + (panel_h - text_surf.get_height()) // 2
        surface.blit(text_surf, (text_x, text_y))

        if self.overlay and hasattr(self.overlay, 'register_panel_rect'):
            self.overlay.register_panel_rect(self.name, pygame.Rect(x, y, panel_w, panel_h))
