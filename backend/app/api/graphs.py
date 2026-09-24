"""Which road networks this instance can route on."""

from fastapi import APIRouter

router = APIRouter(prefix="/graphs", tags=["graphs"])



def _stats_for(graph_path) -> dict | None:
    """
    What the build actually produced, read from the stats file written beside
    the graph: nodes, edges and road length. Measured at build time, not
    estimated here — and absent rather than invented when the file is missing.
    """
    import json
    from pathlib import Path

    if not graph_path:
        return None
    built = Path(graph_path)
    stats_file = built.with_name(f"{built.name.split('_')[0]}_stats.json")
    if not stats_file.exists():
        # Some builds name the stats after the folder rather than the pickle.
        candidates = list(built.parent.glob("*_stats.json"))
        if not candidates:
            return None
        stats_file = candidates[0]
    try:
        raw = json.loads(stats_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    # The two builders measure length differently and say so rather than
    # being averaged into one number: the OSMnx city build sums each road
    # once, the PBF build sums each direction. Comparing them as if they were
    # the same figure would overstate every city built the second way.
    return {
        "nodes": raw.get("nodes"),
        "edges": raw.get("edges"),
        "roadKm": raw.get("total_length_km") or raw.get("directed_km"),
        "roadKmBasis": "undirected" if raw.get("total_length_km") else (
            "directed" if raw.get("directed_km") else None),
        "builtUtc": raw.get("built_utc"),
        "extentKm": raw.get("extent_km"),
    }


@router.get(
    "",
    summary="List the available road networks",
    description=(
        "Two networks at different resolutions, and neither contains the "
        "other.\n\n"
        "`hyderabad` has every drivable street inside the Outer Ring Road, so "
        "it can route to an address — but it stops at the city limit.\n\n"
        "`india` covers the whole country along motorway, trunk and primary "
        "roads only, so it can route between cities but cannot reach a "
        "residential street.\n\n"
        "Pass the name as `graph` on a route request, or on /places/search to "
        "scope the search to the same network."
    ),
)
@router.get("/", include_in_schema=False)
def list_graphs() -> dict:
    from graph.graph_loader import DEFAULT_GRAPH_NAME, available_graphs
    from app.integrations.engine_bridge import loaded_engines

    graphs = available_graphs()
    resident = set(loaded_engines())

    for name, info in graphs.items():
        # "loaded" is not the same as "available": a graph is only resident
        # after something routes on it, because each costs over a gigabyte of
        # memory and loading both speculatively is not free.
        info["loaded"] = name in resident
        info["stats"] = _stats_for(info.get("path"))
        # The absolute path of the pickle on the server is of no use to a
        # caller and names a home directory; whether it exists is the answer
        # the question was really asking.
        info.pop("path", None)

    return {
        "default": DEFAULT_GRAPH_NAME,
        "graphs": graphs,
        "note": (
            "Neither network is a superset of the other. Routing a city "
            "address on 'india' snaps to the nearest highway, which may be "
            "kilometres away; routing between cities on 'hyderabad' fails "
            "because the destination is off the graph."
        ),
    }
