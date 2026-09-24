"""
The place names the code asks for must exist in config/places.yaml.

WHY THIS EXISTS
---------------
places.yaml was rebuilt to cover seven cities, and every key gained a city
prefix: "hitec" became "hyderabad_hitec_city". Nothing failed at import time.
It failed later, and quietly: /api/analytics/scalability returned 500 to the
admin Analytics page, and scripts/run_demo.py, run_dijkstra.py and
run_constrained.py all raised KeyError on their first lookup — found in a
server log, not by a test.

Short names still resolve (see graph_loader._full_key), and these tests hold
both halves of that: the names the code uses resolve to exactly one place, and
a name that matches two cities is refused rather than guessed.

No graph is loaded here: this reads the YAML only, so it runs in milliseconds.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from graph.graph_loader import _full_key, load_places

BACKEND = pathlib.Path(__file__).resolve().parents[1]
PLACES = load_places()

# Where place names actually appear. Scanning the whole file matched graph
# names and field names too, so each source is read where it is written.
SOURCES = {
    "engine.scalability": (BACKEND / "engine.py", r"keys = \[(.*?)\]"),
    "run_demo stops": (BACKEND / "scripts" / "run_demo.py", r"plan_multistop\((.*?)\)"),
    "run_dijkstra pairs": (BACKEND / "scripts" / "run_dijkstra.py", r"VERIFY_PAIRS = \[(.*?)\]"),
}
DEFAULTS = re.compile(r'dest="(?:src|dst)", default="([a-z_]+)"')


def used_keys() -> dict[str, set[str]]:
    """Every place name the code asks for, by where it was written."""
    found: dict[str, set[str]] = {}
    for label, (path, pattern) in SOURCES.items():
        text = path.read_text(encoding="utf-8")
        block = re.search(pattern, text, re.S)
        if block:
            found[label] = set(re.findall(r'"([a-z][a-z_]+)"', block.group(1)))
    for path in sorted((BACKEND / "scripts").glob("run_*.py")):
        names = set(DEFAULTS.findall(path.read_text(encoding="utf-8")))
        if names:
            found[f"{path.name} defaults"] = names
    return found


def test_the_sweep_found_some_keys():
    keys = used_keys()
    assert len(keys) >= 3, f"the scan matched almost nothing: {keys}"
    assert sum(len(v) for v in keys.values()) >= 10


def test_every_place_the_code_asks_for_resolves():
    """
    A name the code uses must name exactly one place. This is the check that
    was missing when the city prefixes landed: the scalability chart answered
    500 and three scripts raised KeyError, and nothing noticed.
    """
    broken = {}
    for where, names in used_keys().items():
        for name in sorted(names):
            if name in PLACES:
                continue
            try:
                _full_key(name, PLACES)
            except KeyError as exc:
                broken.setdefault(where, []).append(f"{name}: {str(exc)[:60]}")
    assert not broken, f"names that no longer resolve: {broken}"


@pytest.mark.parametrize("short,expected", [
    ("hitec", "hyderabad_hitec_city"),
    ("jubilee", "hyderabad_jubilee_hills"),
    ("charminar", "hyderabad_charminar"),
])
def test_short_names_still_resolve(short, expected):
    assert _full_key(short, PLACES) == expected


def test_an_unknown_name_is_still_refused():
    with pytest.raises(KeyError, match="Unknown place"):
        _full_key("atlantis_junction", PLACES)
