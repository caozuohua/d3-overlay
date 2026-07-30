"""
D3OA — 数据提供器

聚合多个数据源：Blizzard 公开 API、游戏日志文件、截图 OCR。
所有数据来源合法，不读写游戏内存。
"""

import json
import os
import re
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

    def __init__(self, region='us', access_token=None, client_id=None, client_secret=None):
        self.region = region
        self.base_url = self.REGIONS.get(region, self.REGIONS['us'])
        self.locale = self.LOCALE.get(region, 'en_US')
        self.access_token = access_token
        self.client_id = client_id
        self.client_secret = client_secret
        self._session = None

    def _get_session(self):
        if self._session is None:
            import requests
            self._session = requests.Session()
        return self._session

    def _ensure_token(self):
        """Blizzard D3 API 强制需要 access_token。

        F3 修复：若无手动 token，则通过 OAuth2 client-credentials 流程换取
        （POST https://{region}.battle.net/oauth/token, grant_type=client_credentials,
         Basic Auth = client_id:client_secret）。文档曾称“无需认证”，不实。
        返回 True 表示已有可用 token。
        """
        if self.access_token:
            return True
        if not self.client_id or not self.client_secret:
            logger.warning("未配置 access_token 或 client_id/client_secret，无法获取 Blizzard API token")
            return False
        try:
            session = self._get_session()
            token_url = f"https://{self.region}.battle.net/oauth/token"
            resp = session.post(
                token_url,
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
                timeout=10,
            )
            resp.raise_for_status()
            self.access_token = resp.json().get("access_token")
            if not self.access_token:
                logger.error("Blizzard OAuth 返回为空 token")
                return False
            logger.info("已通过 client-credentials 获取 Blizzard API token")
            return True
        except Exception as e:
            logger.error(f"获取 Blizzard API token 失败: {e}")
            return False

    def _request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """发送 API 请求（自动确保 token）"""
        if not self._ensure_token():
            logger.warning("无可用 API access_token，跳过 API 请求")
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

    def get_hero_skills(self, class_slug: str) -> Optional[dict]:
        """获取职业技能数据"""
        return self._request(f"/d3/data/hero/{class_slug}")

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
        """自动定位 D3 日志文件
        
        支持以下路径：
        - 标准 Documents 文件夹
        - OneDrive 同步的 Documents 文件夹
        - 中文系统文档文件夹
        - 游戏安装目录
        """
        # 构建候选路径列表
        user_profile = os.path.expanduser("~")
        
        candidates = [
            # 标准 Documents (英文系统)
            os.path.join(user_profile, "Documents", "Diablo III", "Logs", "D3Debug.txt"),
            # OneDrive Documents (Windows 10/11 常见)
            os.path.join(user_profile, "OneDrive", "Documents", "Diablo III", "Logs", "D3Debug.txt"),
            os.path.join(user_profile, "OneDrive - Personal", "Documents", "Diablo III", "Logs", "D3Debug.txt"),
            # 中文系统
            os.path.join(user_profile, "我的文档", "Diablo III", "Logs", "D3Debug.txt"),
            os.path.join(user_profile, "文档", "Diablo III", "Logs", "D3Debug.txt"),
            # 游戏安装目录
            "C:/Program Files (x86)/Diablo III/Logs/D3Debug.txt",
            "C:/Program Files/Diablo III/Logs/D3Debug.txt",
        ]

        # 使用 Win32 API 获取实际 Documents 文件夹路径（最可靠）
        try:
            import ctypes
            from ctypes import wintypes
            
            # SHGetKnownFolderPath 获取已知文件夹路径
            FOLDERID_Documents = "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}"
            
            ole32 = ctypes.windll.ole32
            shell32 = ctypes.windll.shell32
            
            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", ctypes.c_ulong),
                    ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort),
                    ("Data4", ctypes.c_byte * 8),
                ]
            
            guid = GUID()
            ole32.CLSIDFromString(FOLDERID_Documents, ctypes.byref(guid))
            
            path_ptr = ctypes.c_wchar_p()
            hr = shell32.SHGetKnownFolderPath(
                ctypes.byref(guid), 0, None, ctypes.byref(path_ptr)
            )
            if hr == 0 and path_ptr.value:
                docs_path = path_ptr.value
                d3_log = os.path.join(docs_path, "Diablo III", "Logs", "D3Debug.txt")
                candidates.insert(0, d3_log)  # 优先检查
                ole32.CoTaskMemFree(path_ptr)
        except Exception:
            pass

        # 检查所有候选路径
        for path in candidates:
            if path and os.path.exists(path):
                logger.info(f"找到 D3 日志文件: {path}")
                return path

        logger.warning("未找到 D3 日志文件，日志监控功能将不可用")
        return None

    def poll_new_lines(self) -> list:
        """读取新增的日志行
        
        安全处理：
        - 文件不存在时不报错
        - D3 写入时遇到文件锁则跳过本次
        - 编码错误的字符用 ? 替代
        """
        if not self.log_path or not os.path.exists(self.log_path):
            return []

        try:
            # 检查文件大小是否变化（避免重复读取）
            try:
                current_size = os.path.getsize(self.log_path)
            except OSError:
                return []

            if current_size < self._last_pos:
                # 文件被截断/轮转，重置位置
                logger.info("日志文件已重置，重新开始读取")
                self._last_pos = 0

            if current_size == self._last_pos:
                return []  # 没有新内容

            with open(self.log_path, 'r', encoding='utf-8', errors='replace') as f:
                f.seek(self._last_pos)
                lines = f.readlines()
                self._last_pos = f.tell()
            return [l.strip() for l in lines if l.strip()]
        except PermissionError:
            # D3 正在写入文件，文件被锁定
            # 下次轮询时再试
            return []
        except OSError as e:
            logger.warning(f"读取日志文件时出错: {e}")
            return []
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
        """解析单行日志（支持 typed event + 向后兼容 raw string）"""
        lower = line.lower()
        ts = time.time()

        # 游戏开始/结束
        if 'game_new' in lower or 'game_newgame' in lower:
            return {'type': 'new_game', 'raw': line, 'timestamp': ts}
        if 'game_leave' in lower or 'game_destroyed' in lower:
            return {'type': 'leave_game', 'raw': line, 'timestamp': ts}

        # 秘境相关：匹配 nepalemrift / greater_rift 及其宽松变体（空格而不是下划线）
        rift_match = False
        rift_type = None
        if 'nephalemrift' in lower:
            rift_match = True
            rift_type = 'nephalemrift'
        elif 'greater_rift' in lower:
            rift_match = True
            rift_type = 'greater_rift'
        elif 'nephalem rift' in lower or 'greater rift' in lower:
            rift_match = True
            rift_type = 'nephalemrift' if 'nephalem rift' in lower else 'greater_rift'
        elif 'rift' in lower and any(k in lower for k in ('progress', 'opened', 'open', 'start', 'enter')):
            rift_match = True
            if 'nephalem' in lower:
                rift_type = 'nephalemrift'
            elif 'greater' in lower:
                rift_type = 'greater_rift'
            else:
                rift_type = 'unknown'

        if rift_match:
            if 'progress' in lower:
                # rift_progress with float progress
                m = re.search(r'progress[:\s]+(\d+(?:\.\d+)?)', lower)
                progress = float(m.group(1)) / 100.0 if m else 0.0
                return {
                    'type': 'rift_progress',
                    'raw': line,
                    'timestamp': ts,
                    'rift_type': rift_type,
                    'progress': progress,
                }
            else:
                # rift_event with rift_type/rift_id
                m = re.search(r'\bid[:\s_]*([a-z0-9_-]+)', lower)
                rift_id = m.group(1) if m else None
                return {
                    'type': 'rift_event',
                    'raw': line,
                    'timestamp': ts,
                    'rift_type': rift_type,
                    'rift_id': rift_id,
                }

        # 复仇怪 (Nemesis)
        if 'nemesis' in lower or 'revenge' in lower:
            if 'appear' in lower or 'spawn' in lower:
                return {'type': 'nemesis', 'raw': line, 'timestamp': ts, 'status': 'appeared'}
            elif 'defeat' in lower or 'kill' in lower or 'die' in lower:
                return {'type': 'nemesis', 'raw': line, 'timestamp': ts, 'status': 'defeated'}
            else:
                return {'type': 'nemesis', 'raw': line, 'timestamp': ts}

        # 传送点
        if 'waypoint' in lower:
            return {'type': 'waypoint', 'raw': line, 'timestamp': ts}

        # 组队
        if 'party' in lower or 'join' in lower:
            return {'type': 'party_event', 'raw': line, 'timestamp': ts}

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
        client_id = config.get('data.client_id', None)
        client_secret = config.get('data.client_secret', None)
        self.api = D3APIClient(region=region, access_token=token,
                               client_id=client_id, client_secret=client_secret)

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
