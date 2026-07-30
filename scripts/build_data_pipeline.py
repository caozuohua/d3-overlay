"""BuildAssistant 数据管道集成脚本（Phase 3 Task 9）。

加载 ``src/build_assistant_data.py`` 与 ``src/build_assistant_scraper.py``，
打印解析摘要，并在缺失可选依赖时优雅降级。

运行:
    python scripts/build_data_pipeline.py
"""

from __future__ import annotations

import importlib
import os
import sys
from typing import Any

# 让 src 可被导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _try_import(name: str) -> Any:
    """导入模块，失败时返回 None。"""
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def _check_dependency(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def main() -> int:
    # 可选依赖状态
    has_requests = _check_dependency("requests")
    has_bs4 = _check_dependency("bs4")

    data_mod = _try_import("build_assistant_data")
    scraper_mod = _try_import("build_assistant_scraper")

    print("=== BuildAssistant 数据管道摘要 ===")
    print(f"requests 可用: {has_requests}")
    print(f"beautifulsoup4 可用: {has_bs4}")

    # 解析器摘要
    if data_mod is None:
        print("数据模块未加载: build_assistant_data")
        return 1

    sample_js = """/* some comment */
DiabloCalc.skills = {
    barbarian: {
        Bash: { name: "Bash" },
        Frenzy: { name: "Frenzy" },
    },
    wizard: {
        MagicMissile: { name: "Magic Missile" },
    },
};
var other = 1;
"""
    try:
        parsed = data_mod.parse_skill_js(sample_js)
        classes = list(parsed.keys())
        print(f"解析到的职业数量: {len(classes)}")
        for cls in classes:
            names = data_mod.extract_skill_names(parsed, cls)
            print(f"  - {cls}: {len(names)} 个技能 ({', '.join(names)})")
        print(f"SNO 数据可用: {data_mod.is_sno_available()}")
    except Exception as exc:
        print(f"解析器运行失败: {type(exc).__name__}: {exc}")
        return 2

    # 抓取器摘要
    if scraper_mod is None:
        print("抓取模块未加载: build_assistant_scraper")
        return 3

    try:
        # 用示例 HTML 验证解析路径，再尝试一个假 URL 观察网络分支
        sample_html = """<!doctype html><html><body>
<table>
  <tr>
    <td><a href="/diablo-3/skills/barbarian/whirlwind">Whirlwind</a></td>
    <td class="level">12</td>
  </tr>
</table>
</body></html>"""
        rows = scraper_mod.parse_leveling_guide(sample_html)
        print(f"示例 HTML 解析到技能行数: {len(rows)}")

        fetched = scraper_mod.fetch_icyveins_guide("https://www.icy-veins.com/diablo-3")
        print(f"网络抓取返回条目数: {len(fetched)}")
        print(f"抓取器状态: {'就绪 (requests=可用)' if has_requests else '降级 (requests=缺失)'}")
    except Exception as exc:
        print(f"抓取器运行失败: {type(exc).__name__}: {exc}")
        return 4

    print("=== 数据管道集成检查完成 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
