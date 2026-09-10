"""
Cut street-level road networks for several cities out of one country extract.

WHY ONE PASS FOR ALL CITIES
---------------------------
The India extract is 1.71 GB and reading it end to end takes about fourteen
minutes per pass. Building five city graphs one at a time would mean ten passes
and over two hours of re-reading the same file.

A node either falls in a city's bounding box or it does not, and that test is
almost free once the node has been read. So the file is read twice in total —
once for nodes, once for ways — and every city is filled during the same sweep.
Five cities cost barely more than one.

WHY THIS AND NOT OVERPASS
-------------------------
Overpass does not work from this machine: the main instance times out entirely
and a 25-minute run over a single 1-degree tile produced nothing while exiting
cleanly. The country extract was already downloaded for the national highway
graph, so the data is on disk and needs no network at all.

WHAT "STREET LEVEL" MEANS HERE
------------------------------
Every drivable public road class, down to residential and living streets — the
detail needed to route to an address rather than to the nearest arterial.
Service ways are excluded: they are parking aisles, driveways and alleys, they
outnumber real streets, and routing through a supermarket car park to save
thirty seconds is not a route anyone would drive.

MEMORY
------
Node coordinates are held only for nodes inside a city box, so the cost scales
with the cities being built rather than with the size of India. Ways are held
only if they touch one of those boxes.
"""

from __future__ import annotations

import pickle
import time
from pathlib import Path

import networkx as nx

# Drivable public road classes. Mirrors INDIA_URBAN_SPEEDS_KPH in
# osm_processor, so a graph built here carries the same classes the speed table
# knows how to price.
STREET_KEEP = {
    "motorway", "motorway_link",
    "trunk", "trunk_link",
    "primary", "primary_link",
    "secondary", "secondary_link",
    "tertiary", "tertiary_link",
    "unclassified", "residential", "living_street", "road",
}

# (west, south, east, north) per city, from preprocessing.osm_processor.
from preprocessing.osm_processor import METRO_BBOX  # noqa: E402


def _tag(obj, key, default=None):
    try:
        return obj.tags.get(key, default)
    except Exception:
        return default


def scan_nodes(pbf: Path, cities: list[str]) -> dict[str, dict]:
    """
    Pass one: coordinates for every node inside any requested city box.

    One sweep serves every city. A node in two overlapping boxes is stored for
    both, which is correct — the same junction really is in both extracts.
    """
    import osmium

    boxes = {c: METRO_BBOX[c] for c in cities}
    coords: dict[str, dict[int, tuple]] = {c: {} for c in cities}

    t0, seen = time.time(), 0
    for obj in osmium.FileProcessor(str(pbf), osmium.osm.NODE):
        seen += 1
        if seen % 20_000_000 == 0:
            kept = sum(len(v) for v in coords.values())
            print(f"[nodes] {seen:,} read, {kept:,} kept ({time.time() - t0:.0f}s)",
                  flush=True)
        lat, lon = obj.location.lat, obj.location.lon
        for city, (w, s, e, n) in boxes.items():
            if s <= lat <= n and w <= lon <= e:
                coords[city][obj.id] = (lat, lon)

    for city in cities:
        print(f"[nodes] {city:<10s} {len(coords[city]):>10,} nodes in box")
    print(f"[nodes] {seen:,} scanned in {(time.time() - t0) / 60:.1f} min")
    return coords


def scan_ways(pbf: Path, coords: dict[str, dict]) -> tuple[dict, dict]:
    """
    Pass two: drivable ways touching each city, and how often each node is used.

    A way is kept for a city when any of its nodes is in that city's box, so a
    road crossing the boundary is not chopped in half at the edge.
    """
    import osmium
    from collections import defaultdict

    cities = list(coords)
    ways: dict[str, list] = {c: [] for c in cities}
    refs: dict[str, dict] = {c: defaultdict(int) for c in cities}

    t0, seen = time.time(), 0
    for obj in osmium.FileProcessor(str(pbf), osmium.osm.WAY):
        seen += 1
        if seen % 5_000_000 == 0:
            total = sum(len(v) for v in ways.values())
            print(f"[ways]  {seen:,} read, {total:,} kept ({time.time() - t0:.0f}s)",
                  flush=True)

        hwy = _tag(obj, "highway")
        if hwy not in STREET_KEEP:
            continue
        nodes = [n.ref for n in obj.nodes]
        if len(nodes) < 2:
            continue

        record = None
        for city in cities:
            here = coords[city]
            if not any(n in here for n in nodes):
                continue
            if record is None:
                record = {
                    "id": obj.id, "nodes": nodes, "highway": hwy,
                    "oneway": _tag(obj, "oneway", "no"),
                    "lanes": _tag(obj, "lanes"),
                    "maxspeed": _tag(obj, "maxspeed"),
                    "name": _tag(obj, "name"),
                }
            ways[city].append(record)
            counter = refs[city]
            for n in nodes:
                counter[n] += 1
            counter[nodes[0]] += 1
            counter[nodes[-1]] += 1

    for city in cities:
        print(f"[ways]  {city:<10s} {len(ways[city]):>10,} drivable ways")
    print(f"[ways]  {seen:,} scanned in {(time.time() - t0) / 60:.1f} min")
    return ways, refs


def build_city(city: str, ways: list, refs: dict, coords: dict) -> nx.MultiDiGraph:
    """Junction-split graph for one city, then trimmed to something routable."""
    from preprocessing.osm_pbf import build_graph

    G = build_graph(ways, refs, coords)
    if G.number_of_nodes() and not nx.is_strongly_connected(G):
        before = G.number_of_nodes()
        largest = max(nx.strongly_connected_components(G), key=len)
        G = G.subgraph(largest).copy()
        pct = 100.0 * G.number_of_nodes() / before
        print(f"[scc]   {city:<10s} kept {G.number_of_nodes():,}/{before:,} "
              f"({pct:.1f}%)")
        if pct < 60.0:
            print(f"[warn]  {city}: most of the network was discarded — the box "
                  "may clip the city, or the extract may be incomplete")
    return G


def finalise_and_save(G: nx.MultiDiGraph, city: str, out_root: Path) -> dict:
    """
    Attach the routing fields and write the graph where the loader expects it.

    Uses the URBAN speed table, not the intercity one. Inside a city "trunk"
    means a congested arterial at 60, not a National Highway at 70, and pricing
    city streets with intercity speeds would make every urban ETA optimistic.
    """
    import json

    import osmnx as ox

    from preprocessing.osm_processor import (
        BASE_CAPACITY_PCU, FALLBACK_SPEED_KPH, INDIA_URBAN_SPEEDS_KPH,
    )

    def first(v):
        return v[0] if isinstance(v, list) else v

    G = ox.add_edge_speeds(G, hwy_speeds=INDIA_URBAN_SPEEDS_KPH,
                           fallback=FALLBACK_SPEED_KPH)
    G = ox.add_edge_travel_times(G)
    try:
        G = ox.add_edge_bearings(G)
    except Exception as exc:
        print(f"[warn]  {city}: bearings skipped ({exc})")

    for _u, _v, _k, d in G.edges(keys=True, data=True):
        hwy = str(first(d.get("highway", "residential"))).replace("_link", "")
        try:
            lanes = float(first(d.get("lanes", 2)) or 2)
        except (TypeError, ValueError):
            lanes = 2.0
        d["length_m"] = float(d.get("length", 0.0))
        d["free_flow_speed_kph"] = float(d.get("speed_kph", FALLBACK_SPEED_KPH))
        d["free_flow_time_s"] = float(d.get("travel_time", 0.0))
        d["congestion"] = 0.0
        d["current_speed_kph"] = d["free_flow_speed_kph"]
        d["current_time_s"] = d["free_flow_time_s"]
        d["road_status"] = "open"
        d["capacity_pcu_h"] = BASE_CAPACITY_PCU.get(hwy, 600) * max(lanes, 1.0)

    out_dir = out_root / city
    out_dir.mkdir(parents=True, exist_ok=True)
    pkl = out_dir / f"{city}_drive.pkl"
    with open(pkl, "wb") as fh:
        pickle.dump(G, fh, protocol=5)

    lats = [d["y"] for _n, d in G.nodes(data=True)]
    lons = [d["x"] for _n, d in G.nodes(data=True)]
    classes: dict[str, int] = {}
    total_km = 0.0
    for _u, _v, d in G.edges(data=True):
        k = str(first(d.get("highway", "unknown")))
        classes[k] = classes.get(k, 0) + 1
        total_km += d.get("length_m", 0.0) / 1000.0

    stats = {
        "city": city,
        "source": "Geofabrik india-latest.osm.pbf",
        "scope": "Street level — every drivable public road class",
        "not_included": "Service ways (parking aisles, driveways, alleys)",
        "requested_bbox": list(METRO_BBOX[city]),
        "actual_bbox": [round(min(lons), 4), round(min(lats), 4),
                        round(max(lons), 4), round(max(lats), 4)],
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "directed_km": round(total_km, 1),
        "edges_by_class": dict(sorted(classes.items(), key=lambda kv: -kv[1])),
        "pickle_mb": round(pkl.stat().st_size / 1e6, 1),
    }
    (out_dir / f"{city}_stats.json").write_text(json.dumps(stats, indent=2))
    print(f"[save]  {pkl}  ({stats['pickle_mb']} MB)")
    return stats
