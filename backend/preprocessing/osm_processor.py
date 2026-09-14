"""
Build a routable, traffic-ready road graph for any Indian city from OpenStreetMap.

    python scripts/build_city_graph.py --city "Hyderabad, Telangana, India"
    python scripts/build_city_graph.py --city "Bengaluru, Karnataka, India" --slug bengaluru

Outputs (data/processed/<slug>/):
    <slug>_drive.graphml     routable graph, speed_kph + travel_time on every edge
    <slug>_nodes.parquet     node table (osmid, lat, lon, street_count)
    <slug>_edges.parquet     edge table (u, v, key, length_m, highway, oneway, ...)
    <slug>_stats.json        summary stats for the report

The OSM download is the slow part; it is cached, so re-runs are instant unless --force.
"""
import argparse
import json
import pickle
import time
from pathlib import Path

import networkx as nx
import osmnx as ox
import pandas as pd

# Free-flow speeds (km/h) for Indian *urban* roads, by OSM highway tag.
# OSMnx's built-in defaults are calibrated on Western networks and overestimate
# Indian arterials badly; these are tuned to observed Hyderabad free-flow speeds
# and are the single most important realism knob in the whole graph.
INDIA_URBAN_SPEEDS_KPH = {
    "motorway": 80,          # Outer Ring Road
    "motorway_link": 45,
    "trunk": 60,             # PVNR Expressway, NH stretches
    "trunk_link": 35,
    "primary": 45,           # major arterials
    "primary_link": 30,
    "secondary": 38,
    "secondary_link": 28,
    "tertiary": 32,
    "tertiary_link": 25,
    "unclassified": 25,
    "residential": 22,
    "living_street": 12,
    "service": 15,
    "road": 25,
}
FALLBACK_SPEED_KPH = 25.0

# Nominatim's "Hyderabad, Telangana, India" polygon is the CITY only -- roughly
# 28 x 40 km. It excludes RGIA airport (Shamshabad), Medchal, Shamirpet,
# Patancheru, Narsingi and Bachupally, so any route to those snaps to the city
# edge and silently returns a distance shorter than the straight line.
# These bboxes cover the actual metropolitan region, ORR included.
# Format: (west, south, east, north)
METRO_BBOX = {
    "hyderabad": (78.15, 17.15, 78.75, 17.70),   # ORR + margin, ~61 x 61 km
    "bengaluru": (77.35, 12.75, 77.85, 13.20),
    "delhi":     (76.80, 28.40, 77.55, 28.90),
    "chennai":   (79.95, 12.80, 80.35, 13.25),
    "mumbai":    (72.75, 18.85, 73.05, 19.35),
    "pune":      (73.70, 18.40, 74.05, 18.70),
}

# Rough per-lane hourly PCU capacity by road class (IRC-style ballpark).
BASE_CAPACITY_PCU = {
    "motorway": 2000, "trunk": 1800, "primary": 1500,
    "secondary": 1200, "tertiary": 900, "residential": 600, "service": 300,
}


def _routing_fn(name):
    """OSMnx moved these between v1 and v2; support both layouts."""
    for holder in (ox, getattr(ox, "routing", None)):
        if holder is not None and hasattr(holder, name):
            return getattr(holder, name)
    raise AttributeError("osmnx has no " + name)


def _first(value):
    return value[0] if isinstance(value, list) else value


def _capacity(data):
    highway = str(_first(data.get("highway"))).split("_")[0]
    per_lane = BASE_CAPACITY_PCU.get(highway, 800)
    try:
        lanes = max(1, int(float(_first(data.get("lanes")))))
    except (TypeError, ValueError):
        lanes = 2
    return per_lane * lanes


def build(city, slug, out_dir, network_type="drive", simplify=True,
          consolidate_m=0, force=False, bbox=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = out_dir / (slug + "_drive.graphml")

    if cache.exists() and not force:
        print("[cache] loading " + str(cache))
        G = ox.load_graphml(cache)
    else:
        t0 = time.time()
        ox.settings.log_console = False
        ox.settings.use_cache = True
        ox.settings.cache_folder = str(out_dir.parent.parent / "raw" / "osm" / "cache")
        if bbox:
            w, s, e, n = bbox
            print("[osm]   downloading bbox W%.2f S%.2f E%.2f N%.2f (~%.0f x %.0f km) "
                  "network_type=%s ... (slow, one time)"
                  % (w, s, e, n, (e - w) * 106, (n - s) * 111, network_type))
            G = ox.graph_from_bbox(bbox=bbox, network_type=network_type,
                                   simplify=simplify)
        else:
            print("[osm]   downloading place '%s' network_type=%s ... (slow, one time)"
                  % (city, network_type))
            G = ox.graph_from_place(city, network_type=network_type, simplify=simplify)
        print("[osm]   downloaded in %.1fs  nodes=%s edges=%s"
              % (time.time() - t0, format(G.number_of_nodes(), ","),
                 format(G.number_of_edges(), ",")))

    # Keep only the largest strongly-connected component: guarantees a route exists
    # between ANY ordered (source, destination) pair we sample. Without this the
    # optimiser is intermittently handed unsolvable instances.
    if not nx.is_strongly_connected(G):
        before = G.number_of_nodes()
        largest = max(nx.strongly_connected_components(G), key=len)
        G = G.subgraph(largest).copy()
        print("[scc]   largest strongly-connected component: %s/%s nodes kept"
              % (format(G.number_of_nodes(), ","), format(before, ",")))

    # Optional: merge clustered intersection nodes (dual carriageways, big junctions).
    if consolidate_m:
        Gp = ox.project_graph(G)
        G = ox.consolidate_intersections(Gp, tolerance=consolidate_m,
                                         rebuild_graph=True, dead_ends=False)
        G = ox.project_graph(G, to_latlong=True)
        print("[consol] after %sm consolidation: nodes=%s"
              % (consolidate_m, format(G.number_of_nodes(), ",")))

    G = _routing_fn("add_edge_speeds")(G, hwy_speeds=INDIA_URBAN_SPEEDS_KPH,
                                       fallback=FALLBACK_SPEED_KPH)
    G = _routing_fn("add_edge_travel_times")(G)

    # Bearings are needed later for turn penalties / U-turn restrictions.
    try:
        G = ox.add_edge_bearings(G)
    except Exception as exc:
        print("[warn]  bearings skipped: %s" % exc)

    # Traffic-ready attributes. free_flow_* are immutable baselines; the current_*
    # fields are what the dynamic traffic layer mutates during a simulation.
    for _u, _v, _k, d in G.edges(keys=True, data=True):
        d["length_m"] = float(d.get("length", 0.0))
        d["free_flow_speed_kph"] = float(d.get("speed_kph", FALLBACK_SPEED_KPH))
        d["free_flow_time_s"] = float(d.get("travel_time", 0.0))
        d["congestion"] = 0.0          # 0..1, set by the traffic layer
        d["current_speed_kph"] = d["free_flow_speed_kph"]
        d["current_time_s"] = d["free_flow_time_s"]
        d["road_status"] = "open"      # open | closed | restricted
        d["capacity_pcu_h"] = _capacity(d)

    ox.save_graphml(G, cache)
    print("[save]  " + str(cache))

    # GraphML stores every attribute as a string and takes ~47s to reload for a
    # city this size. The pickle keeps native float types and loads in ~4s, which
    # matters when the optimiser reloads the graph on every benchmark run.
    pkl = out_dir / (slug + "_drive.pkl")
    with open(pkl, "wb") as fh:
        pickle.dump(G, fh, protocol=5)
    print("[save]  %s  (fast-load copy)" % pkl)

    nodes, edges = ox.graph_to_gdfs(G)
    pd.DataFrame({
        "osmid": nodes.index,
        "lat": nodes["y"].values,
        "lon": nodes["x"].values,
        "street_count": nodes["street_count"].values
        if "street_count" in nodes.columns else None,
    }).to_parquet(out_dir / (slug + "_nodes.parquet"), index=False)

    flat = edges.reset_index()
    keep = ["u", "v", "key", "length_m", "highway", "oneway", "reversed", "name",
            "ref", "lanes", "maxspeed", "free_flow_speed_kph", "free_flow_time_s",
            "capacity_pcu_h", "bearing"]
    e = flat[[c for c in keep if c in flat.columns]].copy()
    for c in ("highway", "oneway", "reversed", "name", "ref", "lanes", "maxspeed"):
        if c in e.columns:
            e[c] = e[c].astype(str)
    e.to_parquet(out_dir / (slug + "_edges.parquet"), index=False)

    node_lats = [float(d["y"]) for _, d in G.nodes(data=True)]
    node_lons = [float(d["x"]) for _, d in G.nodes(data=True)]
    stats = {
        "city": city,
        "slug": slug,
        "network_type": network_type,
        "requested_bbox": list(bbox) if bbox else None,
        "actual_bbox": [min(node_lons), min(node_lats), max(node_lons), max(node_lats)],
        "extent_km": [round((max(node_lons) - min(node_lons)) * 106, 1),
                      round((max(node_lats) - min(node_lats)) * 111, 1)],
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "total_length_km": round(float(e["length_m"].sum()) / 1000, 1),
        "strongly_connected": bool(nx.is_strongly_connected(G)),
        "oneway_edges": int((e["oneway"] == "True").sum()) if "oneway" in e else None,
        "highway_mix": e["highway"].value_counts().head(15).to_dict()
        if "highway" in e else {},
        "built_utc": pd.Timestamp.utcnow().isoformat(),
    }
    (out_dir / (slug + "_stats.json")).write_text(json.dumps(stats, indent=2))
    print(json.dumps({k: v for k, v in stats.items() if k != "highway_mix"}, indent=2))
    return G


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="Hyderabad, Telangana, India")
    ap.add_argument("--slug", default=None)
    ap.add_argument("--network-type", default="drive")
    ap.add_argument("--consolidate", type=float, default=0,
                    help="metres; merge clustered intersections (try 15)")
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--metro", action="store_true",
                    help="use the metropolitan bbox instead of the city polygon "
                         "(Hyderabad: includes RGIA, ORR, Medchal, Patancheru)")
    ap.add_argument("--bbox", default=None,
                    help="explicit 'west,south,east,north', overrides --metro")
    args = ap.parse_args()

    city_slug = args.slug or args.city.split(",")[0].strip().lower().replace(" ", "-")

    box = None
    if args.bbox:
        box = tuple(float(x) for x in args.bbox.split(","))
    elif args.metro:
        box = METRO_BBOX.get(city_slug)
        if box is None:
            raise SystemExit("no METRO_BBOX preset for '%s'; pass --bbox explicitly"
                             % city_slug)

    build(args.city, city_slug, Path(args.out) / city_slug, args.network_type,
          consolidate_m=args.consolidate, force=args.force, bbox=box)
