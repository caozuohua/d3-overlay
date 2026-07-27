"""
D3OA — 配置管理器

支持 JSON 配置文件，提供点分路径访问和默认值。
"""

import json
import os
import logging
from pathlib import Path
from typing import Any

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
        "toggle_overlay": "F8",
        "toggle_timer": "F9",
        "cycle_layout": "F10",
        "settings": "F11"
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
        """加载配置文件"""
        # 先加载默认值
        self._data = self._deep_copy(DEFAULT_CONFIG)

        # 尝试加载用户配置
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                self._deep_merge(self._data, user_config)
                logger.info(f"配置已加载: {self._config_path}")
            except Exception as e:
                logger.error(f"配置加载失败: {e}，使用默认配置")
        else:
            # 创建默认配置文件
            self.save()
            logger.info(f"已创建默认配置: {self._config_path}")

    def save(self):
        """保存配置到文件"""
        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
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
