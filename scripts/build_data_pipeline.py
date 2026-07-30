"""BuildAssistant 数据管道集成脚本（Phase 3 Task 9）。"""

from __future__ import annotations

import importlib
import json
import os
import sys
from typing import Any, Dict, List

# 让 src 可被导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _try_import(name: str) -> Any:
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
    has_requests = _check_dependency("requests")
    has_bs4 = _check_dependency("bs4")

    data_mod = _try_import("build_assistant_data")
    scraper_mod = _try_import("build_assistant_scraper")

    print("=== BuildAssistant 数据管道摘要 ===")
    print(f"requests 可用: {has_requests}")
    print(f"beautifulsoup4 可用: {has_bs4}")

    # ── 1) d3planner 解析器摘要 ──
    parsed: Dict[str, Any] = {}
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
        parsed = data_mod.parse_skill_js(sample_js) or {}
        classes = list(parsed.keys())
        print(f"解析到的职业数量: {len(classes)}")
        for cls in classes:
            names = data_mod.extract_skill_names(parsed, cls)
            print(f"  - {cls}: {len(names)} 个技能 ({', '.join(names)})")
        print(f"SNO 数据可用: {data_mod.is_sno_available()}")
    except Exception as exc:
        print(f"解析器运行失败: {type(exc).__name__}: {exc}")
        return 2

    # ── 2) 抓取器摘要 ──
    scraper_rows: List[Dict[str, str]] = []
    if scraper_mod is not None:
        try:
            sample_html = """<!doctype html><html><body>
<table>
  <tr>
    <td><a href="/diablo-3/skills/barbarian/whirlwind">Whirlwind</a></td>
    <td class="level">12</td>
  </tr>
</table>
</body></html>"""
            scraper_rows = scraper_mod.parse_leveling_guide(sample_html)
            fetched = scraper_mod.fetch_icyveins_guide("https://www.icy-veins.com/diablo-3")
            print(f"示例 HTML 解析到技能行数: {len(scraper_rows)}")
            print(f"网络抓取返回条目数: {len(fetched)}")
        except Exception as exc:
            print(f"抓取器运行失败: {type(exc).__name__}: {exc}")
    else:
        print("抓取模块未加载: build_assistant_scraper")

    print(f"抓取器状态: {'就绪 (requests=可用)' if has_requests else '降级 (requests=缺失)'}")

    # ── 3) 产出离线数据文件 ──
    output_path = os.path.abspath(os.path.join(".", "data", "d3-data.json"))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    payload = {
        "meta": {
            "source": "d3planner-sample + scraper-smoke",
            "classes_count": len(parsed),
            "scraper_rows_count": len(scraper_rows),
        },
        "skills": parsed,
        "leveling_guide_samples": scraper_rows,
    }

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"已写入数据文件: {output_path}")
    print("=== 数据管道集成检查完成 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
