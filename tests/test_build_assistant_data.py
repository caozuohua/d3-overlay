"""
d3planner JS skill parser -- unit tests.

运行:
    python tests/test_build_assistant_data.py
"""

import os
import sys

# 让 src 可被导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from build_assistant_data import (
    extract_skill_names,
    is_sno_available,
    parse_skill_js,
)


# ───────────────────────────────────────────────────────
# 1) parse_skill_js: extract barbarian skills
# ───────────────────────────────────────────────────────
def test_parse_skill_js_extracts_barbarian_skills():
    js_fragment = """/* some comment */
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
    result = parse_skill_js(js_fragment)
    assert isinstance(result, dict)
    assert "barbarian" in result
    assert "wizard" in result
    assert "Bash" in result["barbarian"]
    assert "Frenzy" in result["barbarian"]


# ───────────────────────────────────────────────────────
# 2) extract_skill_names: returns list
# ───────────────────────────────────────────────────────
def test_extract_skill_names_returns_list():
    skills = {
        "barbarian": {
            "Bash": {"name": "Bash"},
            "Cleave": {"name": "Cleave"},
        },
    }
    names = extract_skill_names(skills, "barbarian")
    assert isinstance(names, list)
    assert set(names) == {"Bash", "Cleave"}


# ───────────────────────────────────────────────────────
# 3) is_sno_available: returns False
# ───────────────────────────────────────────────────────
def test_is_sno_available_returns_false():
    assert is_sno_available() is False
    assert is_sno_available() == False


if __name__ == "__main__":
    test_parse_skill_js_extracts_barbarian_skills()
    test_extract_skill_names_returns_list()
    test_is_sno_available_returns_false()
    print("all passed")
