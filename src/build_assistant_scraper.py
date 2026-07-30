"""Phase 2 Task 5 — IcyVeins leveling guide scraper skeleton."""

import re
from typing import List, Dict


def parse_leveling_guide(html: str) -> List[Dict[str, str]]:
    """Extract visible skill rows from an IcyVeins leveling guide HTML page.

    Returns a list of dicts with keys ``name`` and ``level``.  Uses only the
    standard library (``re``) so this stays lightweight.
    """
    skills: List[Dict[str, str]] = []

    # IcyVeins leveling guides typically list skills in a table or a series of
    # div/li elements.  This regex is intentionally broad so the skeleton keeps
    # working across minor layout changes until a more precise selector is
    # needed.
    pattern = re.compile(
        r'<a[^>]*href="[^"]*skills[^"]*"[^>]*>([^<]+)</a>'
        r'.*?'
        r'<[^>]*class="[^"]*level[^"]*"[^>]*>(\d+)</[^>]+>',
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(html):
        name = match.group(1).strip()
        level = match.group(2).strip()
        if name and level:
            skills.append({"name": name, "level": level})

    return skills


def fetch_icyveins_guide(url: str) -> List[Dict[str, str]]:
    """Fetch an IcyVeins guide page and parse its skill rows.

    ``requests`` is imported inside the function so the module can still be
    imported in environments where it is not installed.  When the dependency
    is missing the function returns an empty list instead of raising.
    """
    try:
        import requests  # noqa: F401  (imported only for its side-effect)
    except Exception:
        return []

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return parse_leveling_guide(response.text)
    except Exception:
        return []
