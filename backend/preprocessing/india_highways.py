"""
Build a routable national highway graph for the whole of India.

WHY THIS EXISTS, AND WHY IT IS NOT "EVERY ROAD IN INDIA"
-------------------------------------------------------
The Hyderabad metro graph covers 61 x 61 km with 286,603 nodes in a 224 MB
pickle. India is about 3.28 million km², roughly 890 times that area. Scaling
linearly gives ~250 million nodes and something near 200 GB — not a tuning
problem, a different class of machine.

What IS tractable is the arterial network. Filtering to motorway, trunk and
primary keeps the roads that intercity journeys actually use and discards the
residential streets that make up the overwhelming bulk of the node count. The
result is a graph of a size this project already handles, covering the country.

So the honest description is: national coverage at highway resolution. You can
route Hyderabad to Mumbai. You cannot route to a specific house — that needs
the city graph, which is a separate build.

WHERE THE DATA COMES FROM
-------------------------
A Geofabrik country extract, parsed by preprocessing/osm_pbf.py.

The first implementation tiled India into bounding boxes and queried Overpass
for each. It does not work from this machine: overpass-api.de times out
completely, the kumi.systems mirror needed twelve seconds merely to answer a
status ping, and a 25-minute run over a single 1-degree tile produced zero
tiles while exiting cleanly. That code has been removed rather than kept as a
fallback, because a path that silently produces nothing is worse than no path.

Geofabrik ships the whole country as one file, rebuilt daily, and their extract
is already cut to India's boundary — so there is no cross-border spill to clip
and no Nominatim round trip to fetch a polygon.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import networkx as nx
import osmnx as ox

# Bounding box of the Indian mainland plus island territories, kept for
# reference and for sanity-checking what comes out of an extract.
# (west, south, east, north)
INDIA_BBOX = (68.0, 6.5, 97.5, 35.7)

# Free-flow speeds for INTERCITY highways, km/h.
#
# Deliberately not INDIA_URBAN_SPEEDS_KPH from osm_processor. That table is
# calibrated on Hyderabad arterials, where "trunk" means a congested city road
# at 60 and "primary" means 45. The same OSM tags on a National Highway between
# cities describe a completely different road. Using the urban numbers here
# would make every intercity journey come out roughly 40% slower than it is.
#
# These are free-flow, not speed limits: an expressway posted at 120 does not
# average 120. Traffic is applied on top by the congestion model.
INDIA_HIGHWAY_SPEEDS_KPH = {
    "motorway": 90,          # access-controlled expressways
    "motorway_link": 50,
    "trunk": 70,             # National Highways
    "trunk_link": 40,
    "primary": 55,           # State Highways and major intercity roads
    "primary_link": 35,
}
FALLBACK_SPEED_KPH = 50.0

# Per-lane hourly PCU capacity, matching osm_processor's ballpark figures.
BASE_CAPACITY_PCU = {"motorway": 2000, "trunk": 1800, "primary": 1500}


def _routing_fn(name):
    """OSMnx moved these between v1 and v2; support both layouts."""
    for holder in (ox, getattr(ox, "routing", None)):
        if holder is not None and hasattr(holder, name):
            return getattr(holder, name)
    raise AttributeError("osmnx has no " + name)


def _first(value):
    return value[0] if isinstance(value, list) else value


def _capacity(data) -> float:
    hwy = str(_first(data.get("highway", "primary"))).replace("_link", "")
    per_lane = BASE_CAPACITY_PCU.get(hwy, 1200)
    try:
        lanes = float(_first(data.get("lanes", 2)) or 2)
    except (TypeError, ValueError):
        lanes = 2.0
    return per_lane * max(lanes, 1.0)


def build(pbf: Path) -> nx.MultiDiGraph:
    """Extract the arterial network from a Geofabrik extract, trimmed to routable."""
    from preprocessing.osm_pbf import extract

    G = extract(pbf)

    # The router must be able to reach any node from any other. Without this it
    # is intermittently handed unsolvable pairs, and a national network always
    # has islands: ferry-linked roads, mapping gaps, stubs cut at the border.
    if G.number_of_nodes() and not nx.is_strongly_connected(G):
        before = G.number_of_nodes()
        largest = max(nx.strongly_connected_components(G), key=len)
        G = G.subgraph(largest).copy()
        pct = 100.0 * G.number_of_nodes() / before
        print(f"[scc]   kept {G.number_of_nodes():,}/{before:,} nodes "
              f"({pct:.1f}%) in the largest strongly-connected component")
        if pct < 60.0:
            print("[warn]  a large fraction was discarded — check the extract "
                  "and the highway filter before trusting this graph")
    return G


def finalise(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Attach the speed, time and traffic fields the engine expects."""
    G = _routing_fn("add_edge_speeds")(G, hwy_speeds=INDIA_HIGHWAY_SPEEDS_KPH,
                                       fallback=FALLBACK_SPEED_KPH)
    G = _routing_fn("add_edge_travel_times")(G)
    try:
        G = ox.add_edge_bearings(G)
    except Exception as exc:
        print(f"[warn]  bearings skipped: {exc}")

    # Identical field names to the city graph, so the optimiser, the congestion
    # model and the traffic layer all work against this graph unchanged.
    for _u, _v, _k, d in G.edges(keys=True, data=True):
        d["length_m"] = float(d.get("length", 0.0))
        d["free_flow_speed_kph"] = float(d.get("speed_kph", FALLBACK_SPEED_KPH))
        d["free_flow_time_s"] = float(d.get("travel_time", 0.0))
        d["congestion"] = 0.0
        d["current_speed_kph"] = d["free_flow_speed_kph"]
        d["current_time_s"] = d["free_flow_time_s"]
        d["road_status"] = "open"
        d["capacity_pcu_h"] = _capacity(d)
    return G


def save(G: nx.MultiDiGraph, out_dir: Path, slug: str = "india_highways") -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    pkl = out_dir / f"{slug}.pkl"
    with open(pkl, "wb") as fh:
        pickle.dump(G, fh, protocol=5)
    print(f"[save]  {pkl}  ({pkl.stat().st_size / 1e6:.0f} MB)")

    classes: dict[str, int] = {}
    total_km = 0.0
    lats, lons = [], []
    for _u, _v, d in G.edges(data=True):
        hwy = str(_first(d.get("highway", "unknown")))
        classes[hwy] = classes.get(hwy, 0) + 1
        total_km += d.get("length_m", 0.0) / 1000.0
    for _n, d in G.nodes(data=True):
        lats.append(d["y"])
        lons.append(d["x"])

    stats = {
        "slug": slug,
        "source": "Geofabrik india-latest.osm.pbf",
        "scope": "National arterial network: motorway, trunk, primary (+ links)",
        "not_included": "Secondary, tertiary, residential and service roads",
        "reference_bbox": list(INDIA_BBOX),
        "actual_bbox": [round(min(lons), 4), round(min(lats), 4),
                        round(max(lons), 4), round(max(lats), 4)],
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        # Each carriageway of a two-way road is its own edge, so this counts
        # driveable lane-direction length, not centre-line road length.
        "directed_km": round(total_km, 1),
        "edges_by_class": dict(sorted(classes.items(), key=lambda kv: -kv[1])),
        "free_flow_speeds_kph": INDIA_HIGHWAY_SPEEDS_KPH,
        "speed_note": (
            "Intercity free-flow speeds, distinct from the urban table in "
            "osm_processor.py. The same OSM tag describes a different road "
            "between cities than inside one."
        ),
        "pickle_mb": round(pkl.stat().st_size / 1e6, 1),
    }
    (out_dir / f"{slug}_stats.json").write_text(json.dumps(stats, indent=2))
    print(f"[save]  {out_dir / (slug + '_stats.json')}")
    return stats
