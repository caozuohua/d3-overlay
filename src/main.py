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

# ─── Windows 兼容性初始化（必须在其他导入之前）────────────

def _init_windows_compat():
    """Windows 平台兼容性初始化
    
    1. 设置 DPI 感知，避免高分辨率屏幕模糊
    2. 禁用 DPI 缩放代理，确保叠加窗口坐标正确
    3. 设置控制台编码为 UTF-8
    """
    if sys.platform != 'win32':
        return

    # 设置 DPI 感知（优先 PerMonitorV2，回退到 PerMonitor，再回退到 System）
    try:
        import ctypes
        shcore = ctypes.windll.shcore
        
        # Process_DPI_Awareness 枚举
        DPI_AWARENESS_INVALID = -1
        DPI_AWARENESS_UNAWARE = 0
        DPI_AWARENESS_SYSTEM_AWARE = 1
        DPI_AWARENESS_PER_MONITOR_AWARE = 2
        
        # Windows 10 1703+ 支持 PerMonitorV2
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(
                ctypes.c_void_p(-4)  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            )
            logging.getLogger("D3OA").info("DPI 感知设置: PerMonitorV2")
        except (AttributeError, OSError):
            # 回退到 shcore.SetProcessDpiAwareness (Windows 8.1+)
            try:
                shcore.SetProcessDpiAwareness(DPI_AWARENESS_PER_MONITOR_AWARE)
                logging.getLogger("D3OA").info("DPI 感知设置: PerMonitor")
            except (AttributeError, OSError):
                # 最终回退 (Windows Vista+)
                ctypes.windll.user32.SetProcessDPIAware()
                logging.getLogger("D3OA").info("DPI 感知设置: System")
    except Exception as e:
        logging.getLogger("D3OA").warning(f"DPI 感知设置失败: {e}")

    # 设置控制台输出编码为 UTF-8
    try:
        import ctypes
        # 设置控制台代码页为 UTF-8 (65001)
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

    # 禁用 Windows 的 DPI 虚拟化（防止窗口位置偏移）
    try:
        import ctypes
        # 设置 DWM 窗口属性，禁用非客户区 DPI 缩放
        # 这对于透明叠加窗口非常重要，否则窗口位置会偏移
        pass  # overlay.py 中通过 DWM API 处理
    except Exception:
        pass

_init_windows_compat()

# 确保 src 目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from overlay import OverlayManager
from game_monitor import GameMonitor
from data_provider import DataProvider
from plugin_manager import PluginManager
from hotkey import HotkeyManager
from click_simulator import ClickSimulator
from event_bus import EventBus

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
        self.click_simulator = None

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
        self._event_bus = EventBus()

        # 4. 初始化叠加窗口
        logger.info("创建透明叠加窗口...")
        self.overlay = OverlayManager(self.config)
        result = self.overlay.create()
        if not result:
            err_msg = result if isinstance(result, str) else "未知错误"
            logger.error(f"叠加窗口创建失败: {err_msg}")
            logger.error("可能原因: ")
            logger.error("  1. 安全软件拦截了 CreateWindowExW 调用")
            logger.error("  2. 系统 DPI 缩放导致窗口创建参数异常")
            logger.error("  3. 缺少 d3oa.manifest 文件导致兼容性问题")
            logger.error("解决方案: ")
            logger.error("  1. 将 D3OA 添加到杀毒软件白名单")
            logger.error("  2. 确保 d3oa.manifest 文件与 EXE 在同一目录")
            logger.error("  3. 尝试以管理员身份运行一次（仅首次）")
            return False
        logger.info("叠加窗口创建成功")
        if self.config.get('overlay.follow_game_window', True):
            self.overlay.hide()
        else:
            self.overlay.show()

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

        # 7. 初始化自动点击器
        if self.config.get('autoclicker.enabled', True):
            logger.info("初始化自动点击器...")
            self.click_simulator = ClickSimulator(self.config, self.game_monitor)
            logger.info("自动点击器就绪 (F7 切换)")

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
        # 自动点击切换
        if self.click_simulator:
            self.hotkey_manager.register(
                self.config.get('hotkeys.toggle_autoclick', 'F7'),
                self._on_toggle_autoclick
            )
        # 老板键
        self.hotkey_manager.register(
            'Ctrl+Shift+H',
            self._on_boss_key
        )
        # 临时叠加层诊断：Ctrl+Shift+D 开启 10 秒左上角红框 TEST 标记
        self.hotkey_manager.register(
            'Ctrl+Shift+D',
            self._on_debug_test_overlay
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

        # 叠加层默认可见（create() 已 ShowWindow）。可见性完全交给用户
        # （Ctrl+Shift+O / 老板键），不再由“游戏是否检测到”每帧强制 hide，
        # 否则一旦检测失败叠加层会永远不可见，且会覆盖用户的显隐操作。
        game_was_running = False

        try:
            while self.running:
                frame_start = time.time()

                # 同步叠加窗口到游戏窗口（仅负责“位置/尺寸”，不负责显隐）
                if time.time() - last_sync > sync_interval:
                    game_running = self.game_monitor.is_game_running()
                    if game_running != game_was_running:
                        if game_running:
                            # 游戏出现：若用户未手动隐藏则显示并跟随
                            if not self.overlay.user_hidden:
                                self.overlay.show()
                        else:
                            # 仅在“曾运行→关闭”的边界自动隐藏一次；
                            # 启动即未检测到游戏时不隐藏，保证叠加层可验证。
                            if game_was_running and not self.overlay.user_hidden:
                                self.overlay.hide()
                        game_was_running = game_running
                    if game_running:
                        self.overlay.sync_to_game_window()
                    last_sync = time.time()

                # 获取游戏数据
                game_data = self._collect_game_data()

                # 更新插件
                self.plugin_manager.update_all(frame_time, game_data)

                # 渲染
                self.overlay.begin_frame()
                self.plugin_manager.render_all(self.overlay.get_surface())
                self.overlay.end_frame()

                # 更新自动点击器
                if self.click_simulator:
                    self.click_simulator.update()

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
        events = self.data_provider.get_log_events()
        self._event_bus.process_log_events(events)
        return {
            'game_running': self.game_monitor.is_game_running(),
            'game_foreground': self.game_monitor.is_foreground(),
            'log_events': events,
            'event_bus': self._event_bus,
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

    def _on_toggle_autoclick(self):
        """切换自动点击"""
        if self.click_simulator:
            self.click_simulator.toggle()
            state = "开启" if self.click_simulator.is_active() else "关闭"
            logger.info(f"热键: 自动点击{state}")

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
        self.overlay.user_hidden = True
        self.overlay.hide()

    def _on_debug_test_overlay(self):
        """临时诊断：在叠加层左上角显示 10 秒 TEST 标记，确认像素管线是否出图。"""
        logger.info("热键: 叠加层诊断 TEST 标记 10s")
        self.overlay._debug_test_until = time.time() + 10
        logger.info(f"_debug_test_until set to {self.overlay._debug_test_until}")

    def shutdown(self):
        """关闭应用"""
        logger.info("D3OA 正在关闭...")
        self.running = False

        if self.game_monitor:
            self.game_monitor.stop()  # F6: 终止监控线程

        if self.hotkey_manager:
            self.hotkey_manager.stop()

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
