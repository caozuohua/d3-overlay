"""
D3OA 插件 — 构筑信息展示

通过 Blizzard API 获取角色装备和技能信息，在叠加层中显示。
"""

import logging
import time
from plugin_manager import PluginBase

logger = logging.getLogger("D3OA.Plugin.BuildInfo")

# D3 职业颜色
CLASS_COLORS = {
    'barbarian':    (198, 150, 72),    # 野蛮人 - 金色
    'crusader':    (198, 150, 72),     # 圣教军
    'demon-hunter':(100, 180, 220),    # 猎魔人 - 蓝色
    'monk':        (200, 160, 80),     # 武僧
    'witch-doctor':(120, 180, 80),     # 巫医 - 绿色
    'wizard':      (100, 140, 220),    # 秘术师 - 蓝紫色
    'necromancer': (100, 200, 100),    # 死灵法师
}

# 职业中文名
CLASS_NAMES = {
    'barbarian': '野蛮人',
    'crusader': '圣教军',
    'demon-hunter': '猎魔人',
    'monk': '武僧',
    'witch-doctor': '巫医',
    'wizard': '秘术师',
    'necromancer': '死灵法师',
}


class Plugin(PluginBase):
    """构筑信息展示插件"""

    @property
    def name(self) -> str:
        return "BuildInfo"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "角色构筑信息展示"

    def on_init(self, context: dict):
        self.config = context['config']
        self.overlay = context.get('overlay')
        self.data_provider = context.get('data_provider')
        self._profile_data = None
        self._hero_data = None
        self._last_fetch = 0
        self._fetch_interval = 300  # 5 分钟刷新一次
        self._error_msg = None
        logger.info("BuildInfo 插件初始化完成")

    def on_update(self, delta_time: float, game_data: dict):
        """定期从 API 获取角色数据"""
        now = time.time()
        if now - self._last_fetch < self._fetch_interval:
            return

        battle_tag = self.config.get('data.battle_tag', '')
        if not battle_tag:
            self._error_msg = "未设置 BattleTag"
            return

        # 需要 Blizzard API 凭证才能拉取数据（client_id/client_secret 或 access_token）
        has_creds = (self.config.get('data.client_id') and self.config.get('data.client_secret')) \
                    or self.config.get('data.access_token')
        if not has_creds:
            self._error_msg = "缺少 Blizzard API 凭证"
            return

        try:
            if self.data_provider:
                self._profile_data = self.data_provider.get_profile(battle_tag)
                if self._profile_data and self._profile_data.get('heroes'):
                    # 获取第一个英雄（可扩展为选择）
                    hero = self._profile_data['heroes'][0]
                    hero_id = hero['id']
                    self._hero_data = self.data_provider.get_hero_data(battle_tag, hero_id)
                    self._error_msg = None
                elif self._profile_data and 'code' in self._profile_data:
                    self._error_msg = f"API 错误: {self._profile_data.get('reason', '未知')}"
        except Exception as e:
            self._error_msg = f"数据获取失败: {e}"
            logger.error(f"BuildInfo 数据获取失败: {e}")

        self._last_fetch = now

    def on_render(self, surface):
        """渲染构筑信息面板"""
        try:
            import pygame
        except ImportError:
            return

        pos = self.config.get('plugins.build_info.position', [20, 120])
        x, y = pos
        if self.overlay and hasattr(self.overlay, 'place'):
            x, y = self.overlay.place(x, y)
        panel_w, panel_h = 260, 160
        # 背景：高对比度蓝金暗底
        panel_w, panel_h = 260, 160
        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((30, 50, 100, 220))
        surface.blit(bg, (x, y))

        # 虚线描边
        for i in range(0, panel_w, 8):
            pygame.draw.line(surface, (100, 180, 255, 230), (x + i, y), (x + i + 4, y))
            pygame.draw.line(surface, (100, 180, 255, 230), (x + i, y + panel_h - 1), (x + i + 4, y + panel_h - 1))
        for i in range(0, panel_h, 8):
            pygame.draw.line(surface, (100, 180, 255, 230), (x, y + i), (x, y + i + 4))
            pygame.draw.line(surface, (100, 180, 255, 230), (x + panel_w - 1, y + i), (x + panel_w - 1, y + i + 4))

        try:
            font_title = pygame.font.Font(None, 12)
            font_text = pygame.font.Font(None, 11)
            font_skill = pygame.font.Font(None, 10)

            # 标题
            title = font_title.render("📋 构筑信息", True, (255, 165, 0))
            surface.blit(title, (x + 8, y + 6))

            battle_tag = self.config.get('data.battle_tag', '')
            if not battle_tag:
                placeholder = font_text.render("本地数据模式 / 等待日志事件", True, (150, 150, 150))
                surface.blit(placeholder, (x + 8, y + 30))
                return

            if self._error_msg:
                err = font_text.render(self._error_msg, True, (200, 100, 100))
                surface.blit(err, (x + 8, y + 30))
                if self._error_msg == "缺少 Blizzard API 凭证":
                    hint = font_skill.render("在 config.json 填 client_id/client_secret", True, (150, 150, 150))
                else:
                    hint = font_skill.render("在 config.json 填 data.battle_tag", True, (150, 150, 150))
                surface.blit(hint, (x + 8, y + 48))
                return

            if not self._hero_data:
                loading = font_text.render("加载中...", True, (180, 180, 180))
                surface.blit(loading, (x + 8, y + 30))
                return

            hero = self._hero_data
            hero_class = hero.get('class', '')
            class_name = CLASS_NAMES.get(hero_class, hero_class)
            class_color = CLASS_COLORS.get(hero_class, (255, 255, 255))

            # 角色名和职业
            name_str = f"{hero.get('name', '未知')} · {class_name}"
            name_surf = font_text.render(name_str, True, class_color)
            surface.blit(name_surf, (x + 8, y + 28))

            # 巅峰等级
            para = hero.get('paragonLevel', 0)
            para_str = f"巅峰: {para}"
            para_surf = font_text.render(para_str, True, (255, 215, 0))
            surface.blit(para_surf, (x + 8, y + 48))

            # 技能
            skills = hero.get('skills', {})
            y_offset = y + 70

            if 'active' in skills:
                act_label = font_skill.render("主动技能:", True, (200, 200, 200))
                surface.blit(act_label, (x + 8, y_offset))
                y_offset += 16

                for skill in skills['active'][:4]:
                    skill_name = skill.get('skill', {}).get('name', '—')
                    rune_name = skill.get('rune', {}).get('name', '')
                    if rune_name:
                        text = f"  • {skill_name} [{rune_name}]"
                    else:
                        text = f"  • {skill_name}"
                    skill_surf = font_skill.render(text, True, (180, 220, 255))
                    surface.blit(skill_surf, (x + 8, y_offset))
                    y_offset += 14

        except Exception as e:
            logger.error(f"BuildInfo 渲染失败: {e}")
        if self.overlay and hasattr(self.overlay, 'register_panel_rect'):
            self.overlay.register_panel_rect(self.name, pygame.Rect(x, y, panel_w, panel_h))
