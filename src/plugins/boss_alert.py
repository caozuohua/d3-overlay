"""
D3OA 插件 — Boss 出现提醒

基于本地日志事件监测秘境 Boss 出现。
"""

import logging
import time
from plugin_manager import PluginBase

logger = logging.getLogger("D3OA.Plugin.BossAlert")


class Plugin(PluginBase):
    """Boss 出现提醒插件"""

    @property
    def name(self) -> str:
        return "BossAlert"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Boss 出现提醒"

    def on_init(self, context: dict):
        self.config = context['config']
        self.overlay = context.get('overlay')
        self._enabled = True
        self._boss_active = False
        self._boss_timestamp = None
        self._game_active = False
        self._last_event_count = 0
        logger.info("BossAlert 插件初始化完成")

    def on_update(self, delta_time: float, game_data: dict):
        """根据增量日志事件更新 Boss 状态"""
        events = game_data.get('log_events', [])
        new_events = events[self._last_event_count:]
        self._last_event_count = len(events)

        for event in new_events:
            event_type = event.get('type', '')
            raw = event.get('raw', '')

            if event_type in ('new_game', 'rift_event'):
                self._game_active = True

            if event_type == 'leave_game':
                self._game_active = False
                self._boss_active = False
                continue

            if not self._game_active:
                continue

            if event_type == 'rift_progress' and event.get('progress', 0.0) >= 1.0:
                self._boss_active = True
                self._boss_timestamp = time.time()
                logger.info("检测到秘境进度 100%，Boss 出现")
            elif event_type == 'rift_event':
                raw_lower = raw.lower()
                if any(kw in raw_lower for kw in ('complete', 'finish', 'boss')):
                    self._boss_active = True
                    self._boss_timestamp = time.time()
                    logger.info("检测到秘境完成事件，Boss 出现")

    def on_render(self, surface):
        """渲染 Boss 提醒面板"""
        try:
            import pygame
            if not pygame.font.get_init():
                pygame.font.init()
        except ImportError:
            return

        pos = self.config.get('plugins.boss_alert.position', [20, 500])
        x, y = pos
        if self.overlay and hasattr(self.overlay, 'place'):
            x, y = self.overlay.place(x, y)

        panel_w, panel_h = 220, 60
        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((110, 25, 25, 220))
        surface.blit(bg, (x, y))

        dash_color = (255, 60, 60, 240)
        for i in range(0, panel_w, 8):
            pygame.draw.line(surface, dash_color, (x + i, y), (x + i + 4, y))
            pygame.draw.line(surface, dash_color, (x + i, y + panel_h - 1), (x + i + 4, y + panel_h - 1))
        for i in range(0, panel_h, 8):
            pygame.draw.line(surface, dash_color, (x, y + i), (x, y + i + 4))
            pygame.draw.line(surface, dash_color, (x + panel_w - 1, y + i), (x + panel_w - 1, y + i + 4))

        try:
            font = pygame.font.SysFont("Microsoft YaHei", 16, bold=True)
        except Exception:
            font = pygame.font.Font(None, 18)

        if self._boss_active:
            text = "⚠️ Boss 已出现！"
            color = (255, 60, 60)
        elif self._game_active:
            text = "Boss 未出现"
            color = (200, 200, 200)
        else:
            text = "未在秘境中"
            color = (150, 150, 150)

        text_surf = font.render(text, True, color)
        text_x = x + (panel_w - text_surf.get_width()) // 2
        text_y = y + (panel_h - text_surf.get_height()) // 2
        surface.blit(text_surf, (text_x, text_y))
        if self.overlay and hasattr(self.overlay, 'register_panel_rect'):
            self.overlay.register_panel_rect(self.name, pygame.Rect(x, y, panel_w, panel_h))
