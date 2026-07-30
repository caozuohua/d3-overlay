"""
d3planner JS skill data parser (static offline).

Parses the ``DiabloCalc.skills = {...}`` object literal emitted by d3planner
skill JavaScript packs, without executing any code.
"""

from __future__ import annotations

import re


def parse_skill_js(js_text: str) -> dict:
    """Extract the ``DiabloCalc.skills`` object literal from d3planner JS text.

    The function locates the assignment ``DiabloCalc.skills = <object>`` and
    parses the trailing object literal using safe brace-counting.  It never
    evaluates the source and intentionally avoids ``eval`` / ``exec``.

    Args:
        js_text: Raw JavaScript source text that contains the d3planner
            ``DiabloCalc.skills`` definition.

    Returns:
        The skills mapping, e.g. ``{'barbarian': {...}, 'wizard': {...}}``.

    Raises:
        ValueError: If ``DiabloCalc.skills`` assignment cannot be located or
            the trailing braces are malformed.
    """
    marker = "DiabloCalc.skills"
    idx = js_text.find(marker)
    if idx == -1:
        raise ValueError("DiabloCalc.skills assignment not found in source")

    eq_idx = js_text.find("=", idx)
    if eq_idx == -1:
        raise ValueError("Malformed DiabloCalc.skills assignment: missing '='")

    start = js_text.find("{", eq_idx)
    if start == -1:
        raise ValueError("Malformed DiabloCalc.skills assignment: missing object start")

    depth = 0
    in_string = False
    string_char = ""
    i = start
    while i < len(js_text):
        ch = js_text[i]
        if in_string:
            if ch == "\\" and i + 1 < len(js_text):
                i += 2
                continue
            if ch == string_char:
                in_string = False
            i += 1
            continue

        if ch in ('"', "'", "`"):
            in_string = True
            string_char = ch
            i += 1
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                obj_text = js_text[start : i + 1]
                break
        i += 1
    else:
        raise ValueError("Malformed DiabloCalc.skills assignment: unbalanced braces")

    try:
        import json

        # JS allows unquoted keys and string values; json does not.
        stripped = _js_object_to_json(obj_text)
        # Remove trailing commas before closing braces/brackets.
        stripped = re.sub(r",\s*([}\]])", r"\1", stripped)
        return json.loads(stripped)
    except Exception:
        import ast

        try:
            return ast.literal_eval(obj_text)
        except Exception as exc:
            raise ValueError(
                "Failed to parse DiabloCalc.skills object literal: {}".format(exc)
            ) from exc


def _js_object_to_json(text: str) -> str:
    parts = re.split(r'("[^"]*")', text)
    out = []
    for part in parts:
        if part.startswith('"') and part.endswith('"'):
            out.append(part)
            continue
        part = re.sub(r"([A-Za-z_$][\w$]*)", lambda m: "\"{}\"".format(m.group(1)), part)
        out.append(part)
    return "".join(out)


def extract_skill_names(skills_by_class: dict, class_name: str) -> list[str]:
    """Return the list of skill names for a given class.

    Args:
        skills_by_class: The mapping returned by :func:`parse_skill_js`.
        class_name: The class key to look up (e.g. ``'barbarian'``).

    Returns:
        A list of skill name strings for the requested class.

    Raises:
        KeyError: If ``class_name`` is not present in ``skills_by_class``.
    """
    if class_name not in skills_by_class:
        raise KeyError("Class not found: {!r}".format(class_name))

    class_data = skills_by_class[class_name]
    if isinstance(class_data, dict):
        return list(class_data.keys())
    return list(class_data)


def is_sno_available() -> bool:
    """Placeholder: indicate whether SNO data is available.

    Returns:
        ``False`` until the SNO data path is wired up.
    """
    return False
