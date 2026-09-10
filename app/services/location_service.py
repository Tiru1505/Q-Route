"""
Cities and roads a traffic observation can be attached to.

WHY AN OBSERVATION NEEDS A PLACE
--------------------------------
A vehicle count on its own is not traffic data. "71 vehicles" answers nothing
until you know which road, in which city, at what time — that is the difference
between a detection and an observation, and it is what lets counts accumulate
into a per-road series rather than a pile of unrelated numbers.

WHERE THE ROADS COME FROM
-------------------------
The graphs themselves. Every road offered here is a real named way in a built
road network, with real coordinates, so an observation attached to it can be
written back onto the same edges the router uses. Nothing here is a curated
list that can drift away from the map.

The two networks answer for different places, and the difference is reported
rather than hidden:

    Hyderabad     the metro graph — every drivable street
    other cities  the national graph — motorway, trunk and primary only

So Bengaluru offers its arterial roads and not its residential ones. That is a
real limitation of what has been built, and a city with no graph at all is
listed as unavailable instead of being quietly dropped from the menu.
"""

from __future__ import annotations

import re
import threading
import unicodedata

from app.core.logging import get_logger

_logger = get_logger("services.location")

_lock = threading.Lock()
_index: dict[str, list] = {}

# Cities the project has bounding boxes for. Pan-India by construction: adding
# one here is a bbox, not a code change.
from preprocessing.osm_processor import METRO_BBOX  # noqa: E402

CITY_LABELS = {
    "hyderabad": "Hyderabad",
    "bengaluru": "Bengaluru",
    "delhi": "Delhi",
    "chennai": "Chennai",
    "mumbai": "Mumbai",
    "pune": "Pune",
}

# Which network answers for a city. Only Hyderabad has a street-level graph;
# everywhere else falls back to the national arterial network.
CITY_GRAPH = {c: ("hyderabad" if c == "hyderabad" else "india") for c in CITY_LABELS}

MAX_ROADS_PER_CITY = 400


def slugify(text: str) -> str:
    """A stable, readable id. Same name in the same city always gives the same id."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "road"


def _first(value):
    return value[0] if isinstance(value, list) else value


def cities() -> list[dict]:
    """Every configured city, each marked with whether a network covers it."""
    from graph.graph_loader import GRAPHS

    out = []
    for key, label in CITY_LABELS.items():
        graph = CITY_GRAPH[key]
        built = GRAPHS.get(graph, {}).get("path")
        out.append({
            "id": key,
            "label": label,
            "graph": graph,
            "bbox": list(METRO_BBOX[key]),
            "available": bool(built and built.exists()),
            "coverage": ("Every drivable street" if graph == "hyderabad"
                         else "Motorway, trunk and primary roads only"),
        })
    return out


def _build_index(city: str) -> list[dict]:
    """
    Named roads inside a city's bounding box, from its graph.

    Built once per city because it walks every edge in the network. A road is
    represented by one node on it — enough to anchor an observation and to ask
    the forecaster about that spot.
    """
    from app.integrations.engine_bridge import get_engine

    graph_name = CITY_GRAPH[city]
    engine = get_engine(graph_name)
    lon_min, lat_min, lon_max, lat_max = METRO_BBOX[city]

    seen: dict[str, dict] = {}
    for u, _v, data in engine.G.edges(data=True):
        name = _first(data.get("name"))
        if not name or not isinstance(name, str):
            continue
        node = engine.G.nodes[u]
        lat, lon = float(node["y"]), float(node["x"])
        if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
            continue

        key = slugify(name)
        entry = seen.get(key)
        if entry is None:
            seen[key] = {
                "road_id": f"{city}:{key}",
                "name": name,
                "city": city,
                "graph": graph_name,
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "highway": str(_first(data.get("highway", "")) or ""),
                "segments": 1,
            }
        else:
            entry["segments"] += 1

    # Longest roads first: a road made of many segments is a major one, and a
    # judge picking from a list wants the arterials at the top.
    roads = sorted(seen.values(), key=lambda r: -r["segments"])
    _logger.info("Indexed %d named roads for %s (%s graph)",
                 len(roads), city, graph_name)
    return roads


def roads(city: str, q: str = "", limit: int = 50) -> dict:
    """Named roads in a city, optionally filtered by what the user typed."""
    if city not in CITY_LABELS:
        raise KeyError(f"Unknown city {city!r}. Known: {', '.join(CITY_LABELS)}")

    if city not in _index:
        with _lock:
            if city not in _index:
                _index[city] = _build_index(city)

    found = _index[city]
    needle = q.strip().lower()
    if needle:
        starts = [r for r in found if r["name"].lower().startswith(needle)]
        contains = [r for r in found
                    if needle in r["name"].lower() and r not in starts]
        found = starts + contains

    return {
        "city": city,
        "label": CITY_LABELS[city],
        "graph": CITY_GRAPH[city],
        "total": len(_index[city]),
        "truncated": len(found) > limit,
        "roads": found[:limit],
        "coverage": ("Every drivable street in the metro graph"
                     if CITY_GRAPH[city] == "hyderabad"
                     else "Arterial roads only — this city is served by the "
                          "national highway network, which has no residential streets"),
    }


def resolve(city: str | None, road_id: str | None) -> dict | None:
    """Look one road back up, so an observation can carry its real coordinates."""
    if not (city and road_id):
        return None
    try:
        listing = roads(city, limit=MAX_ROADS_PER_CITY * 10)
    except KeyError:
        return None
    for r in listing["roads"]:
        if r["road_id"] == road_id:
            return r
    return None
