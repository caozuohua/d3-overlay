"""
D3OA — Diablo 3 Overlay Assistant
主入口模块

基于透明窗口叠加技术的游戏增强辅助工具。
零内存注入，零 DLL 注入，完全合法安全。
"""

import sys
import os
import signal
import threading
import time
import logging
from pathlib import Path

# 确保 src 目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from overlay import OverlayManager
from game_monitor import GameMonitor
from data_provider import DataProvider
from plugin_manager import PluginManager
from hotkey import HotkeyManager

# ─── 日志配置 ───────────────────────────────────────────

LOG_DIR = Path(os.path.expanduser("~/.d3oa/logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "d3oa.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("D3OA")


class D3OverlayApp:
    """D3OA 主应用类"""

    def __init__(self):
        self.running = False
        self.config = None
        self.overlay = None
        self.game_monitor = None
        self.data_provider = None
        self.plugin_manager = None
        self.hotkey_manager = None

    def initialize(self):
        """初始化所有组件"""
        logger.info("=" * 50)
        logger.info("D3OA — Diablo 3 Overlay Assistant 启动中...")
        logger.info("=" * 50)

        # 1. 加载配置
        logger.info("加载配置...")
        self.config = Config()
        self.config.load()
        logger.info(f"配置加载完成: region={self.config.get('data.region')}")

        # 2. 初始化游戏监控
        logger.info("初始化游戏监控...")
        self.game_monitor = GameMonitor(
            process_name="Diablo III64.exe"
        )

        # 3. 初始化数据提供器
        logger.info("初始化数据提供器...")
        self.data_provider = DataProvider(self.config)

        # 4. 初始化叠加窗口
        logger.info("创建透明叠加窗口...")
        self.overlay = OverlayManager(self.config)
        if not self.overlay.create():
            logger.error("叠加窗口创建失败！请检查是否以管理员权限运行。")
            return False
        logger.info("叠加窗口创建成功")

        # 5. 初始化插件系统
        logger.info("加载插件...")
        self.plugin_manager = PluginManager()
        context = {
            'config': self.config,
            'overlay': self.overlay,
            'data_provider': self.data_provider,
            'game_monitor': self.game_monitor,
        }
        self.plugin_manager.discover_and_load(context)
        logger.info(f"已加载 {len(self.plugin_manager.plugins)} 个插件")

        # 6. 初始化热键
        logger.info("注册全局热键...")
        self.hotkey_manager = HotkeyManager(self.config)
        self._register_hotkeys()

        logger.info("D3OA 初始化完成！")
        return True

    def _register_hotkeys(self):
        """注册全局热键"""
        self.hotkey_manager.register(
            self.config.get('hotkeys.toggle_overlay', 'F8'),
            self._on_toggle_overlay
        )
        self.hotkey_manager.register(
            self.config.get('hotkeys.toggle_timer', 'F9'),
            self._on_toggle_timer
        )
        self.hotkey_manager.register(
            self.config.get('hotkeys.cycle_layout', 'F10'),
            self._on_cycle_layout
        )
        self.hotkey_manager.register(
            self.config.get('hotkeys.settings', 'F11'),
            self._on_settings
        )
        # 老板键
        self.hotkey_manager.register(
            'Ctrl+Shift+H',
            self._on_boss_key
        )

    def run(self):
        """主运行循环"""
        if not self.initialize():
            logger.error("初始化失败，退出")
            return

        self.running = True
        logger.info("D3OA 主循环启动")

        last_sync = 0
        sync_interval = 0.1  # 100ms 同步一次窗口位置
        target_fps = self.config.get('performance.target_fps', 30)
        frame_time = 1.0 / target_fps

        try:
            while self.running:
                frame_start = time.time()

                # 同步叠加窗口到游戏窗口
                if time.time() - last_sync > sync_interval:
                    game_running = self.game_monitor.is_game_running()
                    if game_running:
                        self.overlay.sync_to_game_window()
                        self.overlay.show()
                    else:
                        self.overlay.hide()
                    last_sync = time.time()

                # 获取游戏数据
                game_data = self._collect_game_data()

                # 更新插件
                self.plugin_manager.update_all(frame_time, game_data)

                # 渲染
                self.overlay.begin_frame()
                self.plugin_manager.render_all(self.overlay.get_surface())
                self.overlay.end_frame()

                # 处理热键
                self.hotkey_manager.poll()

                # 帧率控制
                elapsed = time.time() - frame_start
                sleep_time = frame_time - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("收到中断信号")
        finally:
            self.shutdown()

    def _collect_game_data(self) -> dict:
        """收集游戏相关数据"""
        return {
            'game_running': self.game_monitor.is_game_running(),
            'game_foreground': self.game_monitor.is_foreground(),
            'log_events': self.data_provider.get_log_events(),
            'timestamp': time.time(),
        }

    def _on_toggle_overlay(self):
        """切换叠加层可见性"""
        logger.info("热键: 切换叠加层")
        self.overlay.toggle_visibility()

    def _on_toggle_timer(self):
        """切换计时器"""
        logger.info("热键: 切换计时器")
        timer = self.plugin_manager.plugins.get('Timer')
        if timer:
            timer.toggle()

    def _on_cycle_layout(self):
        """切换布局"""
        logger.info("热键: 切换布局")
        self.overlay.cycle_layout()

    def _on_settings(self):
        """打开设置"""
        logger.info("热键: 打开设置")
        # 在主线程中打开设置窗口
        self.config.open_settings_ui()

    def _on_boss_key(self):
        """老板键 — 立即隐藏叠加层"""
        logger.info("热键: 老板键，隐藏叠加层")
        self.overlay.hide()

    def shutdown(self):
        """关闭应用"""
        logger.info("D3OA 正在关闭...")
        self.running = False

        if self.hotkey_manager:
            self.hotkey_manager.unregister_all()

        if self.plugin_manager:
            for p in self.plugin_manager.plugins.values():
                p.on_destroy()

        if self.overlay:
            self.overlay.destroy()

        logger.info("D3OA 已退出")


def main():
    """入口函数"""
    # 处理 Windows 下的信号
    app = D3OverlayApp()

    def signal_handler(sig, frame):
        app.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    app.run()


if __name__ == '__main__':
    main()
