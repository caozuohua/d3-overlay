"""
D3OA — 配置管理器

支持 JSON 配置文件，提供点分路径访问和默认值。
"""

import json
import os
import sys
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("D3OA.Config")

DEFAULT_CONFIG = {
    "overlay": {
        "opacity": 0.85,
        "position": "top-right",
        "font_size": 14,
        "theme": "dark",
        "click_through": True,
        "follow_game_window": True
    },
    "hotkeys": {
        "toggle_overlay": "Ctrl+Shift+O",
        "toggle_timer": "F9",
        "cycle_layout": "F10",
        "settings": "F11",
        "toggle_autoclick": "F7"
    },
    "data": {
        "battle_tag": "",
        "region": "us",
        "access_token": "",
        "client_id": "",
        "client_secret": "",
        "log_path": "auto",
        "api_cache_ttl": 300,
        "ocr_enabled": False
    },
    "plugins": {
        "timer": {"enabled": True, "position": [20, 20]},
        "build_info": {"enabled": True, "position": [20, 120]},
        "nemesis": {"enabled": True, "position": [20, 300]},
        "rift_info": {"enabled": True, "position": [20, 400]}
    },
    "autoclicker": {
        "enabled": True,
        "interval_ms": 100,
        "max_clicks": 0,
        "foreground_only": True,
        "click_button": "left",
        "pause_on_key": True,
        "pause_key": "SHIFT"
    },
    "performance": {
        "target_fps": 30,
        "render_quality": "medium",
        "cache_size_mb": 50,
        "log_poll_interval": 1.0
    },
    "ui": {
        "font_name": "Microsoft YaHei",
        "bg_color": [0, 0, 0, 160],
        "text_color": [255, 255, 255, 255],
        "accent_color": [255, 165, 0, 255],
        "border_radius": 4,
        "padding": 8
    }
}


class Config:
    """配置管理器"""

    def __init__(self, config_path=None):
        self._data = {}
        self._config_path = config_path or self._default_path()
        self._callbacks = []

    def _default_path(self) -> str:
        config_dir = Path(os.path.expanduser("~/.d3oa"))
        config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir / "config.json")

    def load(self):
        """加载配置文件

        安全处理：
        - 主配置损坏时自动尝试加载 .bak 备份
        - 加载失败时使用默认配置
        """
        # 先加载默认值
        self._data = self._deep_copy(DEFAULT_CONFIG)

        # 尝试加载用户配置
        if os.path.exists(self._config_path):
            loaded = self._try_load_file(self._config_path)
            if loaded is not None:
                self._deep_merge(self._data, loaded)
                logger.info(f"配置已加载: {self._config_path}")
            else:
                # 主配置损坏，尝试加载备份
                backup_path = self._config_path + '.bak'
                if os.path.exists(backup_path):
                    logger.warning(f"主配置损坏，尝试从备份恢复: {backup_path}")
                    backup_data = self._try_load_file(backup_path)
                    if backup_data is not None:
                        self._deep_merge(self._data, backup_data)
                        self.save()  # 恢复后重新保存
                        logger.info("已从备份恢复配置")
                    else:
                        logger.error("备份也已损坏，使用默认配置")
                else:
                    logger.error("配置文件损坏且无备份，使用默认配置")
        else:
            # 创建默认配置文件
            self.save()
            logger.info(f"已创建默认配置: {self._config_path}")

    def reload(self):
        """从磁盘重新加载配置

        安全处理：
        - 仅在已知配置文件路径时重载
        - 无路径时静默返回，不抛异常
        """
        if not self._config_path:
            return
        self.load()

    def _get_mtime(self) -> Optional[float]:
        """获取配置文件 mtime，不存在返回 None"""
        if self._config_path and os.path.exists(self._config_path):
            return os.path.getmtime(self._config_path)
        return None

    def watch(self, callback, interval: float = 1.0):
        """启动配置监听（基本轮询实现）

        Args:
            callback: 配置变更后回调，签名为 ``callback(config: Config)``
            interval: 轮询间隔（秒）
        """
        import threading

        self._watch_stop = threading.Event()
        self._watch_callback = callback
        self._watch_interval = interval
        self._watch_mtime = self._get_mtime()

        def _poll():
            while not self._watch_stop.is_set():
                try:
                    mtime = self._get_mtime()
                    if mtime is not None and mtime != self._watch_mtime:
                        self._watch_mtime = mtime
                        self.reload()
                        if self._watch_callback:
                            try:
                                self._watch_callback(self)
                            except Exception:
                                pass
                except Exception:
                    pass
                self._watch_stop.wait(self._watch_interval)

        self._watch_thread = threading.Thread(target=_poll, daemon=True)
        self._watch_thread.start()

    def stop_watch(self):
        """停止配置监听"""
        if hasattr(self, "_watch_stop"):
            self._watch_stop.set()

    def _try_load_file(self, path: str) -> Optional[dict]:
        """尝试加载 JSON 配置文件，失败返回 None"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析错误 ({path}): {e}")
            return None
        except Exception as e:
            logger.error(f"配置加载失败 ({path}): {e}")
            return None

    def save(self):
        """保存配置到文件
        
        安全处理：
        - 保存前备份旧配置为 .bak
        - 使用原子写入（先写临时文件再重命名）
        """
        try:
            # 备份旧配置
            if os.path.exists(self._config_path):
                backup_path = self._config_path + '.bak'
                try:
                    import shutil
                    shutil.copy2(self._config_path, backup_path)
                except Exception:
                    pass  # 备份失败不影响主流程

            # 原子写入: 先写临时文件，再重命名
            tmp_path = self._config_path + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
                f.flush()
                import os as _os
                _os.fsync(f.fileno())  # 确保写入磁盘

            # 重命名替换旧文件
            if sys.platform == 'win32':
                # Windows 不允许直接覆盖已存在的文件
                if os.path.exists(self._config_path):
                    os.remove(self._config_path)
            os.rename(tmp_path, self._config_path)

            logger.info(f"配置已保存: {self._config_path}")
        except Exception as e:
            logger.error(f"配置保存失败: {e}")

    def get(self, path: str, default=None) -> Any:
        """通过点分路径获取配置值
        例如: config.get('overlay.opacity') -> 0.85
        """
        keys = path.split('.')
        value = self._data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, path: str, value: Any):
        """通过点分路径设置配置值"""
        keys = path.split('.')
        target = self._data
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        target[keys[-1]] = value

        # 通知回调
        for cb in self._callbacks:
            try:
                cb(path, value)
            except Exception:
                pass

    def on_change(self, callback):
        """注册配置变更回调"""
        self._callbacks.append(callback)

    def open_settings_ui(self):
        """打开设置界面（占位，可扩展为 GUI）"""
        logger.info("设置界面打开请求（暂未实现 GUI，编辑 config.json）")
        # 可以用 subprocess 打开默认编辑器
        try:
            import subprocess
            subprocess.Popen(['notepad.exe', self._config_path])
        except Exception:
            pass

    @staticmethod
    def _deep_copy(obj):
        """深拷贝"""
        return json.loads(json.dumps(obj))

    @staticmethod
    def _deep_merge(base: dict, override: dict):
        """深度合并字典"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                Config._deep_merge(base[key], value)
            else:
                base[key] = value
