"""
D3OA 插件 — 秘境进度信息

显示当前秘境的进度信息，包括进度百分比和 Boss 预估。
"""

import logging
import time
from plugin_manager import PluginBase

logger = logging.getLogger("D3OA.Plugin.RiftInfo")


class RiftTracker:
    """秘境进度追踪"""

    def __init__(self):
        self.active = False
        self.rift_type = 'unknown'  # nephalem / greater
        self.level = 0
        self.progress = 0.0         # 0.0 - 1.0
        self.progress_balls = 0
        self.start_time = None
        self.boss_spawned = False
        self.completed = False

    def start(self, rift_type='nephalem', level=0):
        self.active = True
        self.rift_type = rift_type
        self.level = level
        self.progress = 0.0
        self.progress_balls = 0
        self.start_time = time.time()
        self.boss_spawned = False
        self.completed = False

    def update_progress(self, progress: float):
        old_progress = self.progress
        self.progress = max(0.0, min(1.0, progress))

        # 检测进度球
        old_balls = int(old_progress / 0.1)
        new_balls = int(self.progress / 0.1)
        if new_balls > old_balls:
            self.progress_balls = new_balls

        # 检测 Boss 出现 (进度达到 100%)
        if self.progress >= 1.0 and not self.boss_spawned:
            self.boss_spawned = True

    def stop(self):
        self.completed = True
        self.active = False

    def get_elapsed(self) -> float:
        if self.start_time:
            return time.time() - self.start_time
        return 0.0

    def get_progress_percent(self) -> int:
        return int(self.progress * 100)

    def format_elapsed(self) -> str:
        elapsed = self.get_elapsed()
        mins, secs = divmod(elapsed, 60)
        return f"{int(mins):02d}:{secs:05.2f}"

    def estimate_boss_time(self) -> float:
        """估算 Boss 出现时间（秒）"""
        if self.progress <= 0 or self.boss_spawned:
            return 0.0
        elapsed = self.get_elapsed()
        rate = self.progress / elapsed  # 进度/秒
        if rate > 0:
            remaining = 1.0 - self.progress
            return remaining / rate
        return 0.0


class Plugin(PluginBase):
    """秘境进度信息插件"""

    @property
    def name(self) -> str:
        return "RiftInfo"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "秘境进度信息展示"

    def on_init(self, context: dict):
        self.config = context['config']
        self.data_provider = context.get('data_provider')
        self.tracker = RiftTracker()
        self._last_events = []
        logger.info("RiftInfo 插件初始化完成")

    def on_update(self, delta_time: float, game_data: dict):
        """根据游戏事件更新秘境状态"""
        events = game_data.get('log_events', [])
        new_events = events[len(self._last_events):]
        self._last_events = events

        for event in new_events:
            raw = event.get('raw', '').lower()
            event_type = event.get('type', '')

            # 检测秘境开始
            if event_type == 'rift_event':
                if 'start' in raw or 'open' in raw or 'enter' in raw:
                    rift_type = 'greater' if 'greater' in raw else 'nephalem'
                    self.tracker.start(rift_type)
                    logger.info(f"秘境开始: {rift_type}")

                # 检测进度更新
                if 'progress' in raw:
                    # 尝试从日志中提取百分比
                    import re
                    match = re.search(r'(\d+\.?\d*)%', raw)
                    if match:
                        pct = float(match.group(1)) / 100.0
                        self.tracker.update_progress(pct)

                # 检测完成
                if 'complete' in raw or 'finish' in raw:
                    self.tracker.stop()
                    logger.info(f"秘境完成，用时: {self.tracker.format_elapsed()}")

            elif event_type == 'leave_game':
                self.tracker.active = False

    def on_render(self, surface):
        """渲染秘境进度面板"""
        try:
            import pygame
        except ImportError:
            return

        pos = self.config.get('plugins.rift_info.position', [20, 400])
        x, y = pos
        if self.overlay and hasattr(self.overlay, 'place'):
            x, y = self.overlay.place(x, y)
        panel_w, panel_h = 220, 110

        # 背景
        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((10, 8, 5, 200))
        surface.blit(bg, (x, y))

        # 边框
        pygame.draw.rect(surface, (120, 90, 40, 200),
                         (x, y, panel_w, panel_h), 1, border_radius=4)

        try:
            font_title = pygame.font.SysFont("Microsoft YaHei", 12, bold=True)
            font_big = pygame.font.SysFont("Consolas", 20, bold=True)
            font_text = pygame.font.SysFont("Microsoft YaHei", 11)

            # 标题
            title = font_title.render("📊 秘境进度", True, (255, 165, 0))
            surface.blit(title, (x + 8, y + 6))

            if not self.tracker.active:
                # 未在秘境中
                idle = font_text.render("未在秘境中", True, (150, 150, 150))
                surface.blit(idle, (x + 8, y + 30))
                hint = font_text.render("进入秘境后自动追踪", True, (100, 100, 100))
                surface.blit(hint, (x + 8, y + 50))
                return

            # 秘境类型和层数
            rift_name = "大秘境" if self.tracker.rift_type == 'greater' else "小秘境"
            if self.tracker.level > 0:
                rift_label = f"{rift_name} 第 {self.tracker.level} 层"
            else:
                rift_label = rift_name
            label_surf = font_text.render(rift_label, True, (200, 200, 200))
            surface.blit(label_surf, (x + 8, y + 28))

            # 用时
            elapsed_str = f"⏱ {self.tracker.format_elapsed()}"
            elapsed_surf = font_text.render(elapsed_str, True, (200, 180, 100))
            surface.blit(elapsed_surf, (x + 8, y + 48))

            # 进度条
            bar_x, bar_y = x + 8, y + 70
            bar_w, bar_h = panel_w - 16, 14
            pygame.draw.rect(surface, (40, 40, 40, 200),
                             (bar_x, bar_y, bar_w, bar_h), border_radius=2)

            fill_w = int(bar_w * self.tracker.progress)
            if fill_w > 0:
                # 进度条颜色渐变
                if self.tracker.progress < 0.5:
                    bar_color = (80, 180, 80, 220)
                elif self.tracker.progress < 0.8:
                    bar_color = (200, 200, 0, 220)
                else:
                    bar_color = (200, 80, 80, 220)

                pygame.draw.rect(surface, bar_color,
                                 (bar_x, bar_y, fill_w, bar_h), border_radius=2)

            # 进度百分比
            pct_text = f"{self.tracker.get_progress_percent()}%"
            pct_surf = font_text.render(pct_text, True, (255, 255, 255))
            # 居中显示
            pct_x = bar_x + (bar_w - pct_surf.get_width()) // 2
            surface.blit(pct_surf, (pct_x, bar_y))

            # Boss 预估
            if not self.tracker.boss_spawned and self.tracker.progress > 0.05:
                est = self.tracker.estimate_boss_time()
                if est > 0:
                    est_mins = int(est / 60)
                    est_secs = int(est % 60)
                    est_text = f"Boss 预估: {est_mins}:{est_secs:02d}"
                    est_surf = font_text.render(est_text, True, (180, 180, 180))
                    surface.blit(est_surf, (x + 8, y + 90))

            if self.tracker.boss_spawned:
                boss_surf = font_text.render("⚠️ Boss 已出现！", True, (255, 80, 80))
                surface.blit(boss_surf, (x + 8, y + 90))

        except Exception as e:
            logger.error(f"RiftInfo 渲染失败: {e}")
