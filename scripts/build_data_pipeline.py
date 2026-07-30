"""BuildAssistant 数据管线生成器：输入 d3planner JS / scraper / API 输入，输出版本化离线数据文件。

用法:
    python scripts/build_data_pipeline.py d3-data-v<season>.json
    python scripts/build_data_pipeline.py
默认输出:
    data/d3-data.json
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from typing import Any, Dict, List, Optional

# 确保 src 可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _try_import(name: str) -> Optional[Any]:
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


def _load_builtin_sample(data_mod: Any) -> Dict[str, Any]:
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
    parsed = data_mod.parse_skill_js(sample_js) or {}
    return {
        "meta": {
            "source": "d3planner-sample",
            "classes_count": len(parsed),
            "scraper_rows_count": 0,
        },
        "skills": parsed,
        "leveling_guide_samples": [],
    }


def _default_output_path(filename: Optional[str]) -> str:
    if filename:
        return os.path.abspath(os.path.join(".", filename))
    return os.path.abspath(os.path.join(".", "data", "d3-data.json"))


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    output_path = _default_output_path(argv[0] if argv else None)

    data_mod = _try_import("build_assistant_data")
    scraper_mod = _try_import("build_assistant_scraper")
    has_requests = _check_dependency("requests")
    has_bs4 = _check_dependency("bs4")

    print("=== BuildAssistant 数据管线生成器 ===")
    print(f"output: {output_path}")
    print(f"requests: {has_requests}, beautifulsoup4: {has_bs4}")

    if data_mod is None:
        print("数据模块未加载: build_assistant_data")
        return 1

    payload: Dict[str, Any] = _load_builtin_sample(data_mod)

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
            rows = scraper_mod.parse_leveling_guide(sample_html)
            fetched = scraper_mod.fetch_icyveins_guide("https://www.icy-veins.com/diablo-3")
            payload["meta"]["scraper_rows_count"] = len(rows)
            payload["leveling_guide_samples"] = rows[:20]
            print(f"scraper_sample_rows: {len(rows)}")
            print(f"scraper_fetched_rows: {len(fetched)}")
        except Exception as exc:
            print(f"抓取器运行失败: {type(exc).__name__}: {exc}")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"classes: {payload['meta']['classes_count']}")
    print(f"wrote: {output_path}")
    print("=== 完成 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
