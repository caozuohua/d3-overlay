"""
SNO 离线解析器原型骨架

SNO 是 Diablo 3 使用的二进制资源包（BundleNumericOps）格式。
通过解析 SNO 文件，可以离线读取游戏内物品、英雄、技能等静态数据
而不需要连入暴雪服务器。

本模块目前仅提供骨架接口，后续会填充：
- 对 SNO 文件头 / 数据块布局的二进制读取
- 常见表（items/heroes/skills）的解码与缓存
- 与 overlay 现有 data_provider 层的对接

文件格式概要（TODO）:
- SNO 通常以 0x09 魔术字开头，随后是条目计数与哈希表
- 每条目含 string table 偏移 + 数据块偏移/长度
- 字符串表为 UTF-16/ASCII 混合；数据块是类型特定的紧凑二进制
"""

from __future__ import annotations

import os


class SNOParser:
    """SNO 离线解析器骨架。

    用法::

        parser = SNOParser()            # 暂不指定路径
        item = parser.parse_item("sword_1")
        # 目前始终返回 None，直到 _find_default_path / parse_* 被真正实现
    """

    def __init__(self, sno_path: str | os.PathLike[str] | None = None) -> None:
        self.sno_path: str | None = (
            os.fspath(sno_path) if sno_path is not None else self._find_default_path()
        )

    def _find_default_path(self) -> str | None:
        """在常见安装位置寻找 SNO 根目录。返回找到的路径或 None。"""
        # 常见候选：D3 安装目录 + Media/Assets, 用户自定义路径, 环境变量等
        candidates = [
            os.environ.get("D3_SNO_ROOT"),
            os.path.expanduser("~/D3/Media/Assets"),
            os.path.expanduser("~/Games/Diablo III/Media/Assets"),
            r"C:\Program Files\Diablo III\Media\Assets",
            r"C:\Program Files (x86)\Diablo III\Media\Assets",
        ]
        for path in candidates:
            if path and os.path.isdir(path):
                return path
        return None

    def parse_item(self, item_slug: str) -> dict | None:
        """解析物品记录（待实现）。"""
        return None

    def parse_hero(self, hero_id: str | int) -> dict | None:
        """解析英雄记录（待实现）。"""
        return None

    def parse_skill(self, skill_slug: str) -> dict | None:
        """解析技能记录（待实现）。"""
        return None


def is_sno_available() -> bool:
    """快速检测 SNO 解析是否就绪。当前为占位返回 False。

    当 _find_default_path 找到有效目录并且二进制解析接入后，
    此函数应返回 True。
    """
    return False


if __name__ == "__main__":
    p = SNOParser()
    print("sno_path =", p.sno_path)
    print("available =", is_sno_available())
