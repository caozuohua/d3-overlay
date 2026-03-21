"""
D3OA — 插件管理器

自动发现、加载和管理插件。
"""

import importlib
import importlib.util
import os
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("D3OA.PluginManager")


class PluginBase(ABC):
    """插件基类 — 所有插件必须继承此类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """插件版本"""
        ...

    @property
    def description(self) -> str:
        """插件描述"""
        return ""

    @property
    def enabled(self) -> bool:
        """是否启用"""
        return getattr(self, '_enabled', True)

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    @abstractmethod
    def on_init(self, context: dict):
        """初始化回调"""
        ...

    @abstractmethod
    def on_update(self, delta_time: float, game_data: dict):
        """每帧更新回调"""
        ...

    @abstractmethod
    def on_render(self, surface):
        """渲染回调"""
        ...

    def on_destroy(self):
        """清理回调"""
        pass

    def on_config_changed(self, config: dict):
        """配置变更回调"""
        pass


class PluginManager:
    """插件管理器"""

    def __init__(self, plugin_dir: str = None):
        if plugin_dir is None:
            plugin_dir = os.path.join(os.path.dirname(__file__), 'plugins')
        self.plugin_dir = plugin_dir
        self.plugins: dict[str, PluginBase] = {}

    def discover_and_load(self, context: dict):
        """自动发现并加载所有插件"""
        if not os.path.isdir(self.plugin_dir):
            logger.warning(f"插件目录不存在: {self.plugin_dir}")
            return

        for fname in sorted(os.listdir(self.plugin_dir)):
            if fname.endswith('.py') and not fname.startswith('_'):
                module_name = fname[:-3]
                self._load_plugin(module_name, context)

    def _load_plugin(self, module_name: str, context: dict):
        """加载单个插件模块"""
        try:
            spec = importlib.util.spec_from_file_location(
                module_name,
                os.path.join(self.plugin_dir, f"{module_name}.py")
            )
            if not spec or not spec.loader:
                return

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if not hasattr(module, 'Plugin'):
                logger.warning(f"插件 {module_name} 缺少 Plugin 类，跳过")
                return

            plugin = module.Plugin()

            # 检查配置中是否禁用
            plugin_config = context['config'].get(f'plugins.{module_name}', {})
            if plugin_config.get('enabled', True) is False:
                logger.info(f"插件 {module_name} 已在配置中禁用")
                return

            plugin.on_init(context)
            self.plugins[plugin.name] = plugin
            logger.info(f"插件已加载: {plugin.name} v{plugin.version}")

        except Exception as e:
            logger.error(f"加载插件 {module_name} 失败: {e}", exc_info=True)

    def update_all(self, delta_time: float, game_data: dict):
        """更新所有启用的插件"""
        for plugin in self.plugins.values():
            if plugin.enabled:
                try:
                    plugin.on_update(delta_time, game_data)
                except Exception as e:
                    logger.error(f"插件 {plugin.name} 更新失败: {e}")

    def render_all(self, surface):
        """渲染所有启用的插件"""
        for plugin in self.plugins.values():
            if plugin.enabled:
                try:
                    plugin.on_render(surface)
                except Exception as e:
                    logger.error(f"插件 {plugin.name} 渲染失败: {e}")

    def destroy_all(self):
        """销毁所有插件"""
        for plugin in self.plugins.values():
            try:
                plugin.on_destroy()
            except Exception as e:
                logger.error(f"插件 {plugin.name} 销毁失败: {e}")
        self.plugins.clear()

    def get_plugin(self, name: str) -> PluginBase:
        """获取指定插件"""
        return self.plugins.get(name)
