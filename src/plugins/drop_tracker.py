"""
D3OA 插件 — 掉落追踪（占位）

追踪掉落物品数量，供后续扩展。
"""

import logging
from plugin_manager import PluginBase

logger = logging.getLogger("D3OA.Plugin.DropTracker")


class Plugin(PluginBase):
    """掉落追踪（占位）"""

    @property
    def name(self) -> str:
        return "DropTracker"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def description(self) -> str:
        return "掉落追踪（占位）"

    def on_init(self, context: dict):
        self.config = context['config']
        self.overlay = context.get('overlay')
        self.data_provider = context.get('data_provider')
        self._drops = []
        logger.info("DropTracker 插件初始化完成")

    def on_update(self, delta_time: float, game_data: dict):
        """未来扩展：解析 item_drop 事件并 append 到 _drops"""
        events = game_data.get('log_events', [])
        for event in events:
            event_type = event.get('type', '')
            if event_type == 'item_drop':
                self._drops.append(event)

    def on_render(self, surface):
        """渲染掉落追踪面板"""
        try:
            import pygame
        except ImportError:
            return

        pos = self.config.get('plugins.drop_tracker.position', [20, 650])
        x, y = pos
        if self.overlay and hasattr(self.overlay, 'place'):
            x, y = self.overlay.place(x, y)

        panel_w, panel_h = 200, 40
        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((80, 20, 80, 210))
        surface.blit(bg, (x, y))

        dash_color = (255, 100, 255, 240)
        for i in range(0, panel_w, 8):
            pygame.draw.line(surface, dash_color, (x + i, y), (x + i + 4, y))
            pygame.draw.line(surface, dash_color, (x + i, y + panel_h - 1), (x + i + 4, y + panel_h - 1))
        for i in range(0, panel_h, 8):
            pygame.draw.line(surface, dash_color, (x, y + i), (x, y + i + 4))
            pygame.draw.line(surface, dash_color, (x + panel_w - 1, y + i), (x + panel_w - 1, y + i + 4))

        try:
            font = pygame.font.SysFont("Microsoft YaHei", 14, bold=True)
        except Exception:
            font = pygame.font.Font(None, 16)

        text = f"DropTracker: {len(self._drops)} items"
        text_surf = font.render(text, True, (255, 200, 255))
        text_x = x + (panel_w - text_surf.get_width()) // 2
        text_y = y + (panel_h - text_surf.get_height()) // 2
        surface.blit(text_surf, (text_x, text_y))

        if self.overlay and hasattr(self.overlay, 'register_panel_rect'):
            self.overlay.register_panel_rect(self.name, pygame.Rect(x, y, panel_w, panel_h))
