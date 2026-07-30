"""
D3OA 插件 — 练级出装/技能天赋推荐助手

提供练级路径、装备搭配及技能天赋组合推荐。
"""

import json
import logging
import os
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
        self._data = {}
        self._classes = []
        self._samples = []
        self._load_data()
        logger.info("BuildAssistant 插件初始化完成")

    def _load_data(self):
        """Load offline data file produced by build_data_pipeline.py."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(base_dir)  # plugins/ -> src/
        base_dir = os.path.dirname(base_dir)  # src/ -> repo root
        data_path = os.path.join(base_dir, "data", "d3-data.json")
        try:
            with open(data_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            self._data = payload.get("skills", {}) if isinstance(payload, dict) else {}
            self._classes = sorted(self._data.keys())
            samples = payload.get("leveling_guide_samples", []) if isinstance(payload, dict) else []
            self._samples = samples[:5]
            self._data_loaded = bool(self._classes)
        except Exception as exc:
            logger.warning("BuildAssistant data load failed: %s", exc)
            self._data_loaded = False

    def on_update(self, delta_time: float, game_data: dict):
        """Optional hot-reload when data file changes."""
        # Future hook: for now data is static per launch.
        pass

    def on_render(self, surface):
        """Render skill/leveling data panel."""
        try:
            import pygame
        except ImportError:
            return

        pos = self.config.get('plugins.build_assistant.position', [20, 660])
        x, y = pos
        if self.overlay and hasattr(self.overlay, 'place'):
            x, y = self.overlay.place(x, y)

        panel_w, panel_h = 220, 90
        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((20, 80, 40, 220))
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
                small_font = self.overlay.get_font(None, 12)
            else:
                font = pygame.font.Font(None, 14)
                small_font = pygame.font.Font(None, 12)
        except Exception:
            font = pygame.font.Font(None, 14)
            small_font = pygame.font.Font(None, 12)

        if not self._data_loaded:
            text = "BuildAssistant: 等待数据"
            text_surf = font.render(text, True, (180, 255, 200))
            surface.blit(text_surf, (x + 8, y + 8))
        else:
            title = f"BuildAssistant: {len(self._classes)} classes"
            title_surf = font.render(title, True, (180, 255, 200))
            surface.blit(title_surf, (x + 8, y + 8))

            class_text = ", ".join(self._classes) if self._classes else "-"
            class_surf = small_font.render(class_text, True, (200, 240, 210))
            surface.blit(class_surf, (x + 8, y + 28))

            sample_text = "sample: " + ", ".join(
                item.get("name", "") for item in self._samples if item.get("name")
            )
            sample_surf = small_font.render(sample_text, True, (200, 240, 210))
            surface.blit(sample_surf, (x + 8, y + 46))

            first_cls = self._classes[0] if self._classes else None
            if first_cls:
                skills = list(self._data.get(first_cls, {}).keys())[:6]
                skills_text = f"{first_cls}: " + ", ".join(skills)
                skills_surf = small_font.render(skills_text, True, (220, 250, 230))
                surface.blit(skills_surf, (x + 8, y + 64))

        if self.overlay and hasattr(self.overlay, 'register_panel_rect'):
            self.overlay.register_panel_rect(self.name, pygame.Rect(x, y, panel_w, panel_h))
