"""
Extract a routable highway graph from a Geofabrik .osm.pbf extract.

WHY A PBF AND NOT THE OVERPASS API
----------------------------------
The first attempt at a national graph tiled the country into bounding boxes and
asked Overpass for each. It does not work from here: overpass-api.de times out
entirely, the kumi.systems mirror took twelve seconds merely to answer a status
ping, and a 25-minute run over a single 1-degree tile produced nothing at all
while exiting cleanly. Overpass is built for modest extracts, and a country's
arterial network is not one.

Geofabrik publishes the whole of India as a single 1.7 GB file, rebuilt daily.
One download, no rate limits, no partial failures, and the same OpenStreetMap
data underneath.

WHY TWO PASSES
--------------
A .pbf stores ways as lists of node ids, with the coordinates elsewhere in the
file. Resolving them the obvious way needs an index of every node in India —
over 100 million — which does not fit in memory.

Instead the file is read twice. The first pass keeps only the ways we want and
remembers which node ids they mention. The second pass collects coordinates for
exactly those ids and nothing else. Memory is then bounded by the size of the
highway network rather than by the size of the country, and both passes stream
rather than loading the file.

WHY WAYS ARE SPLIT AT JUNCTIONS
-------------------------------
An OSM way can run for tens of kilometres. Turning every consecutive pair of
node ids into an edge would model the shape of the road faithfully and produce
an enormous graph of mostly-useless degree-two nodes. Ways are therefore cut
only where they meet another way, plus at their own endpoints, so a node in the
finished graph is a junction and an edge is the road between two junctions.
Geometry between junctions is discarded, but its LENGTH is kept, so distances
and travel times stay correct.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from pathlib import Path

import networkx as nx

# The arterial classes. `_link` roads are the slip roads joining them; without
# those, interchanges are disconnected and the router cannot enter or leave a
# motorway.
HIGHWAY_KEEP = {
    "motorway", "trunk", "primary",
    "motorway_link", "trunk_link", "primary_link",
}

EARTH_R = 6371008.8


def haversine(lat1, lon1, lat2, lon2) -> float:
    """Great-circle metres between two points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def _tag(way, key, default=None):
    try:
        return way.tags.get(key, default)
    except Exception:
        return default


def scan_ways(pbf: Path, keep: set[str] | None = None) -> tuple[list, dict]:
    """
    First pass: the highway ways, and how often each node id is referenced.

    A node referenced by more than one kept way is a junction. Endpoints count
    as junctions too, so a dead-end still terminates an edge.
    """
    import osmium

    keep = keep or HIGHWAY_KEEP
    ways: list[dict] = []
    refs: dict[int, int] = defaultdict(int)

    t0 = time.time()
    for obj in osmium.FileProcessor(str(pbf), osmium.osm.WAY):
        hwy = _tag(obj, "highway")
        if hwy not in keep:
            continue
        nodes = [n.ref for n in obj.nodes]
        if len(nodes) < 2:
            continue

        ways.append({
            "id": obj.id,
            "nodes": nodes,
            "highway": hwy,
            "oneway": _tag(obj, "oneway", "no"),
            "lanes": _tag(obj, "lanes"),
            "maxspeed": _tag(obj, "maxspeed"),
            "name": _tag(obj, "name"),
        })
        for n in nodes:
            refs[n] += 1
        # Endpoints are junctions by definition, so bump them once more.
        refs[nodes[0]] += 1
        refs[nodes[-1]] += 1

        if len(ways) % 50_000 == 0:
            print(f"[pass1] {len(ways):,} highway ways ...", flush=True)

    print(f"[pass1] {len(ways):,} ways, {len(refs):,} distinct nodes "
          f"({time.time() - t0:.0f}s)")
    return ways, refs


def scan_nodes(pbf: Path, wanted: set[int]) -> dict[int, tuple[float, float]]:
    """Second pass: coordinates for the node ids the kept ways mention."""
    import osmium

    coords: dict[int, tuple[float, float]] = {}
    t0 = time.time()
    for obj in osmium.FileProcessor(str(pbf), osmium.osm.NODE):
        if obj.id in wanted:
            coords[obj.id] = (obj.location.lat, obj.location.lon)
            if len(coords) % 200_000 == 0:
                print(f"[pass2] {len(coords):,}/{len(wanted):,} located ...",
                      flush=True)

    print(f"[pass2] {len(coords):,}/{len(wanted):,} nodes located "
          f"({time.time() - t0:.0f}s)")
    return coords


def _oneway(value) -> bool:
    return str(value).lower() in {"yes", "true", "1", "-1"}


def build_graph(ways: list[dict], refs: dict[int, int],
                coords: dict[int, tuple[float, float]]) -> nx.MultiDiGraph:
    """Cut each way at its junctions and emit one edge per junction-to-junction run."""
    G = nx.MultiDiGraph()
    G.graph["crs"] = "epsg:4326"

    skipped = 0
    for w in ways:
        nodes = [n for n in w["nodes"] if n in coords]
        if len(nodes) < 2:
            skipped += 1
            continue

        reverse = str(w["oneway"]).strip() == "-1"
        one = _oneway(w["oneway"])

        start = nodes[0]
        length = 0.0
        prev = nodes[0]
        for cur in nodes[1:]:
            (la1, lo1), (la2, lo2) = coords[prev], coords[cur]
            length += haversine(la1, lo1, la2, lo2)
            prev = cur

            # Cut here if this node is shared with another way, or ends the way.
            if refs[cur] > 1 or cur == nodes[-1]:
                if start != cur and length > 0:
                    for n in (start, cur):
                        if n not in G:
                            G.add_node(n, y=coords[n][0], x=coords[n][1])
                    attrs = {
                        "osmid": w["id"], "highway": w["highway"],
                        "length": length, "name": w["name"],
                        "lanes": w["lanes"], "maxspeed": w["maxspeed"],
                        "oneway": one,
                    }
                    u, v = (cur, start) if reverse else (start, cur)
                    G.add_edge(u, v, **attrs)
                    if not one:
                        G.add_edge(v, u, **attrs)
                start, length = cur, 0.0

    if skipped:
        print(f"[build] {skipped:,} ways skipped (no located nodes)")
    print(f"[build] {G.number_of_nodes():,} nodes  {G.number_of_edges():,} edges")
    return G


def extract(pbf: Path, keep: set[str] | None = None) -> nx.MultiDiGraph:
    """Full extraction: two streaming passes, then the junction-split graph."""
    pbf = Path(pbf)
    if not pbf.exists():
        raise FileNotFoundError(
            f"No extract at {pbf}.\n"
            "Download it with:\n"
            "  curl -L -o data/raw/osm/geofabrik/india-latest.osm.pbf \\\n"
            "    https://download.geofabrik.de/asia/india-latest.osm.pbf"
        )
    print(f"[pbf]   {pbf}  ({pbf.stat().st_size / 1e9:.2f} GB)")
    ways, refs = scan_ways(pbf, keep)
    if not ways:
        raise ValueError("No highway ways found — is this the right extract?")
    coords = scan_nodes(pbf, set(refs))
    return build_graph(ways, refs, coords)
