"""Which road networks this instance can route on."""

from fastapi import APIRouter

router = APIRouter(prefix="/graphs", tags=["graphs"])


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
