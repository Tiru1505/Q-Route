"""
Load the cached Hyderabad graph and resolve named places to graph nodes.

Every algorithm gets its problem instance from here, so they all provably work
on the same graph — which is what makes the benchmark fair.
"""
import os
import pickle
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# QRO_GRAPH_PATH lets a deployed instance point at a graph that is not in the
# repository. The 575 MB GraphML (214 MB as a pickle) is far past GitHub's
# limit, so a hosted backend has to build it at deploy time or download it to
# somewhere writable, and neither location is knowable in advance.
DEFAULT_GRAPH = Path(
    os.environ.get("QRO_GRAPH_PATH")
    or ROOT / "data/processed/hyderabad/hyderabad_drive.pkl"
)
PLACES_FILE = ROOT / "config/places.yaml"

# ---------------------------------------------------------------------------
# Named graphs
# ---------------------------------------------------------------------------
# Two graphs at different resolutions, because no single one can do both jobs.
#
#   hyderabad  every street in the metro. Routes to an address, one city only.
#   india      motorway/trunk/primary nationwide. Routes between cities, but
#              has no residential streets, so it cannot reach a house.
#
# They are not interchangeable and neither is a superset of the other. The
# caller picks; nothing here guesses.
GRAPHS = {
    "hyderabad": {
        "path": DEFAULT_GRAPH,
        "label": "Hyderabad metro",
        "scope": "All drivable streets inside the ORR",
        "bbox": (78.15, 17.15, 78.75, 17.70),
        # Furthest a request may sit from a node before the route is refused.
        # Every street is present, so anything more than a short walk away is
        # outside the city, not a gap in the map.
        "snap_limit_m": 2_000.0,
        "build": 'python preprocessing/osm_processor.py --city "Hyderabad, Telangana, India" --metro',
    },
    "india": {
        "path": Path(os.environ.get("QRO_INDIA_GRAPH_PATH")
                     or ROOT / "data/processed/india-highways/india_highways.pkl"),
        "label": "India highways",
        "scope": "National arterial network — motorway, trunk and primary only",
        "bbox": (68.0, 6.5, 97.5, 35.7),
        # Far looser, and deliberately so: this network has no residential
        # streets, so a genuine address can legitimately be tens of kilometres
        # from the nearest arterial road. Still bounded, so a request in the
        # ocean is refused rather than snapped to a coastal highway.
        "snap_limit_m": 50_000.0,
        "build": "python scripts/build_india_highways.py",
    },
}
DEFAULT_GRAPH_NAME = "hyderabad"


def graph_names() -> list[str]:
    """Every configured graph, whether or not its file is present."""
    return list(GRAPHS)


def available_graphs() -> dict[str, dict]:
    """Configured graphs, each marked with whether its file exists on disk."""
    return {
        name: {**{k: v for k, v in cfg.items() if k != "path"},
               "path": str(cfg["path"]),
               "available": cfg["path"].exists()}
        for name, cfg in GRAPHS.items()
    }


def graph_path(name: str) -> Path:
    """Resolve a graph name to its file, failing loudly on both bad name and missing file."""
    if name not in GRAPHS:
        raise KeyError(
            f"Unknown graph '{name}'. Known: {', '.join(sorted(GRAPHS))}"
        )
    cfg = GRAPHS[name]
    if not cfg["path"].exists():
        raise FileNotFoundError(
            f"Graph '{name}' not built — nothing at {cfg['path']}.\n"
            f"Build it with:\n  {cfg['build']}"
        )
    return cfg["path"]

# Edge fields that must be floats for the cost model to work. GraphML stringifies
# everything on save, so we coerce defensively regardless of the source format.
NUMERIC_EDGE_FIELDS = (
    "length_m", "free_flow_speed_kph", "free_flow_time_s", "capacity_pcu_h",
    "congestion", "current_speed_kph", "current_time_s",
)


def load_graph(path=None, verbose=True):
    """Load the routable graph. The .pkl loads ~6x faster than the .graphml."""
    path = Path(path) if path else DEFAULT_GRAPH
    if not path.exists():
        raise FileNotFoundError(
            f"Graph not found at {path}.\nBuild it first:\n"
            '  python preprocessing/osm_processor.py --city "Hyderabad, Telangana, India" --metro'
        )

    if path.suffix == ".pkl":
        with open(path, "rb") as fh:
            G = pickle.load(fh)
    else:
        import osmnx as ox
        G = ox.load_graphml(path)

    for _u, _v, _k, d in G.edges(keys=True, data=True):
        for f in NUMERIC_EDGE_FIELDS:
            if f in d:
                try:
                    d[f] = float(d[f])
                except (TypeError, ValueError):
                    d[f] = 0.0
        d.setdefault("congestion", 0.0)
        d.setdefault("road_status", "open")
        d.setdefault("current_time_s", d.get("free_flow_time_s", 0.0))

    if verbose:
        print(f"[graph] {G.number_of_nodes():,} nodes | {G.number_of_edges():,} edges")
    return G


@lru_cache(maxsize=1)
def load_places():
    return yaml.safe_load(PLACES_FILE.read_text())["places"]


def place_names():
    return {k: v["name"] for k, v in load_places().items()}


def resolve_place(G, key, limit_m=None):
    """Named place -> nearest graph node. Raises if the place is off-graph."""
    import osmnx as ox

    places = load_places()
    if key not in places:
        raise KeyError(f"Unknown place '{key}'. Known: {', '.join(sorted(places))}")

    p = places[key]
    node = ox.nearest_nodes(G, p["lon"], p["lat"])
    snap_m = ox.distance.great_circle(
        p["lat"], p["lon"], float(G.nodes[node]["y"]), float(G.nodes[node]["x"])
    )
    # A large snap distance means the place lies outside the graph's extent and
    # any route to it would be silently wrong. Fail loudly instead.
    #
    # The threshold follows the graph. 1 km is right for a street-level city
    # network where every road is present; it is wrong for the national graph,
    # which carries only arterial roads, so a real landmark there sits several
    # hundred metres from the nearest mapped way as a matter of course —
    # measured medians are 139 m in Bengaluru and 500 m in Chennai, with a
    # worst case near 4 km in Delhi.
    limit = float(limit_m) if limit_m is not None else 1000.0
    if snap_m > limit:
        raise ValueError(
            f"'{p['name']}' is {snap_m:.0f} m from the nearest road node, past "
            f"the {limit:.0f} m limit for this network — it is probably outside "
            "the graph."
        )
    return node, p["name"], snap_m


def reset_traffic(G):
    """Return every edge to free-flow. Call between benchmark runs."""
    for _u, _v, _k, d in G.edges(keys=True, data=True):
        d["congestion"] = 0.0
        d["current_speed_kph"] = d.get("free_flow_speed_kph", 25.0)
        d["current_time_s"] = d.get("free_flow_time_s", 0.0)
        d["road_status"] = "open"
    return G
