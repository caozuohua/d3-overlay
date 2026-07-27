"""
D3OA 插件 — 复仇怪追踪器

追踪复仇怪物 (Nemesis) 的状态和击杀记录。
复仇怪是 Diablo 3 中玩家死亡后生成的特殊怪物，
会出现在好友的游戏世界中。
"""

import logging
import time
from plugin_manager import PluginBase

logger = logging.getLogger("D3OA.Plugin.Nemesis")


class Plugin(PluginBase):
    """复仇怪追踪插件"""

    @property
    def name(self) -> str:
        return "Nemesis"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "复仇怪物追踪器"

    def on_init(self, context: dict):
        self.config = context['config']
        self.data_provider = context.get('data_provider')
        self._nemesis_state = 'idle'  # idle / appeared / defeated
        self._appear_time = None
        self._defeat_time = None
        self._kill_count = 0
        self._last_events = []
        logger.info("Nemesis 插件初始化完成")

    def on_update(self, delta_time: float, game_data: dict):
        """根据游戏事件更新复仇怪状态"""
        events = game_data.get('log_events', [])
        new_events = events[len(self._last_events):]
        self._last_events = events

        for event in new_events:
            raw = event.get('raw', '').lower()
            event_type = event.get('type', '')

            # 从日志中检测复仇怪相关事件
            if 'nemesis' in raw or 'revenge' in raw:
                if 'appear' in raw or 'spawn' in raw:
                    self._nemesis_state = 'appeared'
                    self._appear_time = time.time()
                    logger.info("复仇怪出现！")
                elif 'defeat' in raw or 'kill' in raw or 'die' in raw:
                    self._nemesis_state = 'defeated'
                    self._defeat_time = time.time()
                    self._kill_count += 1
                    logger.info(f"复仇怪已击杀！总计: {self._kill_count}")

    def on_render(self, surface):
        """渲染复仇怪追踪面板"""
        try:
            import pygame
        except ImportError:
            return

        pos = self.config.get('plugins.nemesis.position', [20, 300])
        x, y = pos
        if self.overlay and hasattr(self.overlay, 'place'):
            x, y = self.overlay.place(x, y)
        panel_w, panel_h = 220, 80

        # 背景
        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((10, 8, 5, 200))
        surface.blit(bg, (x, y))

        # 边框
        border_color = (120, 90, 40, 200)
        if self._nemesis_state == 'appeared':
            border_color = (255, 60, 60, 220)  # 红色警告
        pygame.draw.rect(surface, border_color,
                         (x, y, panel_w, panel_h), 1, border_radius=4)

        try:
            font_title = pygame.font.SysFont("Microsoft YaHei", 12, bold=True)
            font_text = pygame.font.SysFont("Microsoft YaHei", 11)

            # 标题
            title = font_title.render("👹 复仇怪追踪", True, (255, 165, 0))
            surface.blit(title, (x + 8, y + 6))

            # 状态
            if self._nemesis_state == 'idle':
                state_text = "无复仇怪在追踪中"
                state_color = (150, 150, 150)
            elif self._nemesis_state == 'appeared':
                elapsed = time.time() - self._appear_time
                state_text = f"⚠️ 复仇怪已出现！ ({int(elapsed)}s)"
                state_color = (255, 80, 80)
            elif self._nemesis_state == 'defeated':
                state_text = f"✅ 已击杀 · 累计 {self._kill_count} 次"
                state_color = (80, 200, 80)
            else:
                state_text = "未知状态"
                state_color = (150, 150, 150)

            state_surf = font_text.render(state_text, True, state_color)
            surface.blit(state_surf, (x + 8, y + 30))

            # 击杀计数
            if self._kill_count > 0:
                kill_text = f"累计击杀: {self._kill_count}"
                kill_surf = font_text.render(kill_text, True, (200, 180, 100))
                surface.blit(kill_surf, (x + 8, y + 52))

        except Exception as e:
            logger.error(f"Nemesis 渲染失败: {e}")
