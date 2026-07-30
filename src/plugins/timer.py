"""
D3OA 插件 — 秘境计时器

记录秘境通关时间，支持分段计时和历史最佳记录。
"""

import time
import json
import os
import logging
from plugin_manager import PluginBase

logger = logging.getLogger("D3OA.Plugin.Timer")


class Timer:
    """高精度计时器"""

    def __init__(self):
        self._start_time = None
        self._paused = False
        self._paused_at = 0
        self._elapsed = 0.0
        self._splits = []

    def start(self, label: str = ""):
        self._start_time = time.time()
        self._paused = False
        self._paused_at = 0
        self._elapsed = 0.0
        self._splits.clear()

    def stop(self):
        if self._start_time and not self._paused:
            self._elapsed = time.time() - self._start_time
        self._start_time = None

    def pause(self):
        if self._start_time and not self._paused:
            self._paused_at = time.time()
            self._paused = True

    def resume(self):
        if self._paused:
            paused_duration = time.time() - self._paused_at
            self._start_time += paused_duration
            self._paused = False

    def split(self, label: str = ""):
        """记录分段时间"""
        elapsed = self.get_elapsed()
        self._splits.append({'label': label, 'time': elapsed})

    def reset(self):
        self._start_time = None
        self._paused = False
        self._elapsed = 0.0
        self._splits.clear()

    def get_elapsed(self) -> float:
        if self._start_time and not self._paused:
            return time.time() - self._start_time
        return self._elapsed

    def is_running(self) -> bool:
        return self._start_time is not None and not self._paused

    def format_time(self, seconds: float = None) -> str:
        if seconds is None:
            seconds = self.get_elapsed()
        mins, secs = divmod(seconds, 60)
        hours, mins = divmod(int(mins), 60)
        if hours > 0:
            return f"{hours}:{mins:02d}:{secs:05.2f}"
        return f"{mins}:{secs:05.2f}"


class RecordManager:
    """历史记录管理"""

    def __init__(self, config):
        self.config = config
        self.records_file = os.path.expanduser("~/.d3oa/timer_records.json")
        self.records = self._load_records()

    def _load_records(self) -> dict:
        if os.path.exists(self.records_file):
            try:
                with open(self.records_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {'best_time': None, 'history': []}

    def save_record(self, elapsed: float, splits: list):
        record = {
            'time': elapsed,
            'splits': splits,
            'timestamp': time.time(),
            'date': time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        self.records['history'].append(record)

        if self.records['best_time'] is None or elapsed < self.records['best_time']:
            self.records['best_time'] = elapsed

        # 只保留最近 50 条
        self.records['history'] = self.records['history'][-50:]

        try:
            os.makedirs(os.path.dirname(self.records_file), exist_ok=True)
            with open(self.records_file, 'w') as f:
                json.dump(self.records, f, indent=2)
        except Exception as e:
            logger.error(f"保存记录失败: {e}")

    def get_best_time(self) -> float:
        return self.records.get('best_time')


class Plugin(PluginBase):
    """秘境计时器插件"""

    @property
    def name(self) -> str:
        return "Timer"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "秘境计时器 — 记录通关时间"

    def on_init(self, context: dict):
        self.config = context['config']
        self.overlay = context.get('overlay')
        self.timer = Timer()
        self.record_mgr = RecordManager(self.config)
        self._enabled = True
        self._auto_detect = True
        self._bus_instance = None
        logger.info("Timer 插件初始化完成")

    def on_update(self, delta_time: float, game_data: dict):
        """根据游戏事件自动启停计时器"""
        if not self._auto_detect:
            return

        # Typed EventBus wiring (Phase 3 Task 8)
        event_bus = game_data.get('event_bus')
        if event_bus is not None and getattr(self, '_bus_instance', None) is not event_bus:
            event_bus.subscribe('rift_event', self.on_rift_event)
            event_bus.subscribe('leave_game', self.on_leave_game)
            self._bus_instance = event_bus

        events = game_data.get('log_events', [])
        for event in events[-5:]:  # 只检查最近5个事件
            event_type = event.get('type')
            if event_type == 'new_game' and not self.timer.is_running():
                self.timer.start(label="Game")
                logger.info("检测到新游戏，计时器启动")
            elif event_type == 'rift_event' and not self.timer.is_running():
                self.timer.start()
                logger.info("检测到秘境事件，计时器启动")
            elif event_type == 'leave_game' and self.timer.is_running():
                elapsed = self.timer.get_elapsed()
                self.timer.stop()
                self.record_mgr.save_record(elapsed, self.timer._splits.copy())
                logger.info(f"游戏离开，计时器停止: {elapsed:.2f}s")

    def on_rift_event(self, event: dict):
        """EventBus 回调：秘境事件"""
        if not self.timer.is_running():
            self.timer.start()
            logger.info("检测到秘境事件（via EventBus），计时器启动")

    def on_leave_game(self, event: dict):
        """EventBus 回调：离开游戏"""
        if self.timer.is_running():
            elapsed = self.timer.get_elapsed()
            self.timer.stop()
            self.record_mgr.save_record(elapsed, self.timer._splits.copy())
            logger.info(f"游戏离开（via EventBus），计时器停止: {elapsed:.2f}s")

    def on_render(self, surface):
        """渲染计时器面板"""
        try:
            import pygame
        except ImportError:
            return

        # 面板位置
        pos = self.config.get('plugins.timer.position', [20, 20])
        x, y = pos
        if self.overlay and hasattr(self.overlay, 'place'):
            x, y = self.overlay.place(x, y)

        # 背景：高对比度棕金暗底，避免在 D3 暗场景中看不见
        panel_w, panel_h = 220, 90
        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((140, 100, 20, 210))
        surface.blit(bg, (x, y))

        # 虚线描边
        for i in range(0, panel_w, 8):
            pygame.draw.line(surface, (255, 200, 60, 220), (x + i, y), (x + i + 4, y))
            pygame.draw.line(surface, (255, 200, 60, 220), (x + i, y + panel_h - 1), (x + i + 4, y + panel_h - 1))
        for i in range(0, panel_h, 8):
            pygame.draw.line(surface, (255, 200, 60, 220), (x, y + i), (x, y + i + 4))
            pygame.draw.line(surface, (255, 200, 60, 220), (x + panel_w - 1, y + i), (x + panel_w - 1, y + i + 4))

        # 标题
        try:
            if self.overlay and hasattr(self.overlay, 'get_font'):
                font_title = self.overlay.get_font(None, 12)
                font_time = self.overlay.get_font(None, 24)
                font_small = self.overlay.get_font(None, 11)
            else:
                font_title = pygame.font.Font(None, 12)
                font_time = pygame.font.Font(None, 24)
                font_small = pygame.font.Font(None, 11)

            # 标题行
            title = font_title.render("⏱ 秘境计时器", True, (255, 165, 0))
            surface.blit(title, (x + 8, y + 6))

            # 计时显示
            time_str = self.timer.format_time()
            time_color = (255, 200, 50) if self.timer.is_running() else (180, 180, 180)
            time_surf = font_time.render(time_str, True, time_color)
            surface.blit(time_surf, (x + 8, y + 28))

            # 状态
            status = "计时中" if self.timer.is_running() else "已停止"
            status_surf = font_small.render(status, True, (100, 200, 100) if self.timer.is_running() else (150, 150, 150))
            surface.blit(status_surf, (x + 8, y + 58))

            # 最佳记录
            best = self.record_mgr.get_best_time()
            if best:
                best_str = f"最佳: {self.timer.format_time(best)}"
                best_surf = font_small.render(best_str, True, (255, 215, 0))
                surface.blit(best_surf, (x + 8, y + 74))

        except Exception as e:
            logger.error(f"Timer 渲染失败: {e}")
        if self.overlay and hasattr(self.overlay, 'register_panel_rect'):
            self.overlay.register_panel_rect(self.name, pygame.Rect(x, y, panel_w, panel_h))

    def on_destroy(self):
        if self.timer.is_running():
            self.timer.stop()

    def toggle(self):
        """切换计时器状态"""
        if self.timer.is_running():
            self.timer.stop()
        else:
            self.timer.start()

    def reset(self):
        """重置计时器"""
        self.timer.reset()
