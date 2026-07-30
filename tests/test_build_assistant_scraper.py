"""Tests for src/build_assistant_scraper.py (Phase 2 Task 5)."""

import os
import sys

# 让 src 可被导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest import mock

from build_assistant_scraper import fetch_icyveins_guide, parse_leveling_guide


PUBLIC_SKILL_HTML = """<!doctype html><html><body>
<table>
  <tr>
    <td>
      <a href="/diablo-3/skills/barbarian/whirlwind">Whirlwind</a>
    </td>
    <td class="level">12</td>
  </tr>
  <tr>
    <td>
      <a href="/diablo-3/skills/barbarian/rend">Rend</a>
    </td>
    <td class="level">18</td>
  </tr>
</table>
</body></html>"""


def test_parse_leveling_guide_extracts_skills():
    skills = parse_leveling_guide(PUBLIC_SKILL_HTML)

    assert len(skills) == 2
    assert skills[0] == {"name": "Whirlwind", "level": "12"}
    assert skills[1] == {"name": "Rend", "level": "18"}


def test_fetch_icyveins_guide_returns_empty_without_requests():
    with mock.patch.dict("sys.modules", {"requests": None}):
        result = fetch_icyveins_guide("https://www.icy-veins.com/diablo-3")

    assert result == []


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests)-failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
