"""
D3OA — 数据提供器

聚合多个数据源：Blizzard 公开 API、游戏日志文件、截图 OCR。
所有数据来源合法，不读写游戏内存。
"""

import json
import os
import time
import logging
from pathlib import Path
from typing import Any, Optional
from collections import OrderedDict

logger = logging.getLogger("D3OA.DataProvider")

# ─── 缓存管理 ────────────────────────────────────────────

class TTLCache:
    """带过期时间的缓存"""

    def __init__(self, max_size=128):
        self._cache = OrderedDict()
        self._max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            value, expire_at = self._cache[key]
            if time.time() < expire_at:
                self._cache.move_to_end(key)
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int = 300):
        if len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)
        self._cache[key] = (value, time.time() + ttl)

    def invalidate(self, key: str):
        self._cache.pop(key, None)

    def clear(self):
        self._cache.clear()


# ─── Blizzard D3 API 客户端 ──────────────────────────────

class D3APIClient:
    """Blizzard Diablo 3 公开 API 客户端"""

    REGIONS = {
        'us': 'https://us.api.blizzard.com',
        'eu': 'https://eu.api.blizzard.com',
        'kr': 'https://kr.api.blizzard.com',
        'tw': 'https://tw.api.blizzard.com',
        'cn': 'https://gateway.battlenet.com.cn',
    }

    LOCALE = {
        'us': 'en_US',
        'eu': 'en_GB',
        'kr': 'ko_KR',
        'tw': 'zh_TW',
        'cn': 'zh_CN',
    }

    def __init__(self, region='us', access_token=None):
        self.region = region
        self.base_url = self.REGIONS.get(region, self.REGIONS['us'])
        self.locale = self.LOCALE.get(region, 'en_US')
        self.access_token = access_token
        self._session = None

    def _get_session(self):
        if self._session is None:
            import requests
            self._session = requests.Session()
        return self._session

    def _request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """发送 API 请求"""
        if not self.access_token:
            logger.warning("未设置 API access_token，跳过 API 请求")
            return None

        url = f"{self.base_url}{endpoint}"
        p = params or {}
        p['locale'] = self.locale
        p['access_token'] = self.access_token

        try:
            session = self._get_session()
            resp = session.get(url, params=p, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"API 请求失败: {url} — {e}")
            return None

    def get_profile(self, battle_tag: str) -> Optional[dict]:
        """获取玩家档案（生涯数据）"""
        tag = battle_tag.replace('#', '-')
        return self._request(f"/d3/profile/{tag}/")

    def get_hero(self, battle_tag: str, hero_id: int) -> Optional[dict]:
        """获取英雄详情（装备、技能）"""
        tag = battle_tag.replace('#', '-')
        return self._request(f"/d3/profile/{tag}/hero/{hero_id}")

    def get_hero_items(self, battle_tag: str, hero_id: int) -> Optional[dict]:
        """获取英雄装备详情"""
        tag = battle_tag.replace('#', '-')
        return self._request(f"/d3/profile/{tag}/hero/{hero_id}/items")

    def get_item_data(self, item_slug: str) -> Optional[dict]:
        """获取物品数据"""
        return self._request(f"/d3/data/item/{item_slug}")

    def get_era_leaderboard(self, era_id: int, leaderboard: str = "rift-team-2") -> Optional[dict]:
        """获取赛季/时代排行榜"""
        return self._request(f"/d3/era/{era_id}/leaderboard/{leaderboard}")

    def get_season_leaderboard(self, season_id: int, leaderboard: str = "rift-team-2") -> Optional[dict]:
        """获取赛季排行榜"""
        return self._request(f"/d3/season/{season_id}/leaderboard/{leaderboard}")


# ─── 游戏日志监控器 ─────────────────────────────────────

class GameLogWatcher:
    """监控 D3 日志文件变化"""

    def __init__(self, log_path=None):
        self.log_path = log_path or self._find_log_path()
        self._last_pos = 0
        logger.info(f"日志监控: {self.log_path}")

    def _find_log_path(self) -> Optional[str]:
        """自动定位 D3 日志文件"""
        candidates = [
            os.path.expanduser("~/Documents/Diablo III/Logs/D3Debug.txt"),
            os.path.expanduser("~/我的文档/Diablo III/Logs/D3Debug.txt"),
            "C:/Program Files (x86)/Diablo III/Logs/D3Debug.txt",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def poll_new_lines(self) -> list:
        """读取新增的日志行"""
        if not self.log_path or not os.path.exists(self.log_path):
            return []

        try:
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(self._last_pos)
                lines = f.readlines()
                self._last_pos = f.tell()
            return [l.strip() for l in lines if l.strip()]
        except Exception as e:
            logger.error(f"读取日志失败: {e}")
            return []

    def parse_events(self, lines: list) -> list:
        """从日志行中提取结构化事件"""
        events = []
        for line in lines:
            event = self._parse_line(line)
            if event:
                events.append(event)
        return events

    def _parse_line(self, line: str) -> Optional[dict]:
        """解析单行日志"""
        lower = line.lower()

        # 游戏开始/结束
        if 'game_new' in lower or 'game_newgame' in lower:
            return {'type': 'new_game', 'raw': line, 'timestamp': time.time()}
        if 'game_leave' in lower or 'game_destroyed' in lower:
            return {'type': 'leave_game', 'raw': line, 'timestamp': time.time()}

        # 秘境相关
        if 'nephalemrift' in lower or 'greater_rift' in lower:
            return {'type': 'rift_event', 'raw': line, 'timestamp': time.time()}

        # 传送点
        if 'waypoint' in lower:
            return {'type': 'waypoint', 'raw': line, 'timestamp': time.time()}

        # 组队
        if 'party' in lower or 'join' in lower:
            return {'type': 'party_event', 'raw': line, 'timestamp': time.time()}

        return None


# ─── 数据提供器主类 ─────────────────────────────────────

class DataProvider:
    """数据聚合提供器"""

    def __init__(self, config):
        self.config = config
        self.cache = TTLCache(max_size=256)

        # API 客户端
        region = config.get('data.region', 'us')
        token = config.get('data.access_token', None)
        self.api = D3APIClient(region=region, access_token=token)

        # 日志监控
        log_path = config.get('data.log_path', 'auto')
        if log_path == 'auto':
            log_path = None
        self.log_watcher = GameLogWatcher(log_path)

        # 最近的事件
        self._recent_events = []
        self._max_events = 100

    def get_hero_data(self, battle_tag: str, hero_id: int) -> Optional[dict]:
        """获取英雄数据（带缓存）"""
        cache_key = f"hero:{battle_tag}:{hero_id}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        data = self.api.get_hero(battle_tag, hero_id)
        if data:
            ttl = self.config.get('data.api_cache_ttl', 300)
            self.cache.set(cache_key, data, ttl)
        return data

    def get_profile(self, battle_tag: str) -> Optional[dict]:
        """获取玩家档案（带缓存）"""
        cache_key = f"profile:{battle_tag}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        data = self.api.get_profile(battle_tag)
        if data:
            ttl = self.config.get('data.api_cache_ttl', 300)
            self.cache.set(cache_key, data, ttl)
        return data

    def get_log_events(self) -> list:
        """获取最新的日志事件"""
        new_lines = self.log_watcher.poll_new_lines()
        if new_lines:
            events = self.log_watcher.parse_events(new_lines)
            self._recent_events.extend(events)
            # 保持事件列表大小
            if len(self._recent_events) > self._max_events:
                self._recent_events = self._recent_events[-self._max_events:]
        return self._recent_events

    def get_recent_events(self, event_type: str = None, count: int = 10) -> list:
        """获取最近的指定类型事件"""
        events = self._recent_events
        if event_type:
            events = [e for e in events if e.get('type') == event_type]
        return events[-count:]

    def refresh_cache(self):
        """强制刷新缓存"""
        self.cache.clear()
        logger.info("数据缓存已清空")
