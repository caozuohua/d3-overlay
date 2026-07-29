"""SNO 离线解析器原型骨架的离线单元测试（无需真实 SNO 文件）。"""

import os
import sys

# 让 src 目录可被导入，与仓库里现有测试的风格保持一致
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sno_parser import SNOParser, is_sno_available


def test_sno_parser_init_without_path():
    parser = SNOParser()
    assert parser.sno_path is None


def test_sno_parser_parse_returns_none():
    parser = SNOParser()
    assert parser.parse_item("sword_1") is None


def test_is_sno_available_returns_false():
    assert is_sno_available() is False
