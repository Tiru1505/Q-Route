"""
Simulation control — traffic events a demonstrator can trigger on demand.

WHY THIS IS AN API AND NOT A BUTTON THAT FAKES A RESULT
-------------------------------------------------------
Every event here changes the actual traffic state the router optimises against.
An accident closes real edges in the graph; congestion raises real congestion
values; clearing restores them. Nothing writes a pre-baked "after" picture.

That matters because the whole point of the demonstration is that the route
changes BECAUSE the road changed, not because a script said so. If an event
produced no reroute, that is the honest answer and the agent says why.

EVERYTHING HERE IS LABELLED
---------------------------
Each response carries dataSource: "SIMULATED". These are generated conditions,
not measurements, and no part of the UI should be able to present them as
observed traffic.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/simulation", tags=["simulation"])

# The scenarios the traffic layer actually implements. Exposed rather than
# duplicated, so this list cannot drift from what the simulator supports.
FRIENDLY = {
    "normal": "Normal traffic",
    "peak_hour": "Peak-hour traffic",
    "heavy_congestion": "Heavy congestion",
    "sudden_congestion": "Sudden congestion",
    "accident": "Accident",
    "road_closure": "Road closure",
    "multiple_congested": "Multiple congested corridors",
    "clearing": "Traffic clearing",
}


@router.get(
    "/scenarios",
    summary="Traffic scenarios that can be triggered",
    description="Every scenario the traffic layer implements, with the one in effect now.",
)
def scenarios(graph: str | None = Query(default=None)) -> dict:
    from traffic.simulator import SCENARIO_IDS
    from app.integrations.engine_bridge import get_engine

    engine = get_engine(graph)
    return {
        "active": engine.scenario,
        "scenarios": [
            {"id": s, "label": FRIENDLY.get(s, s.replace("_", " ").title())}
            for s in SCENARIO_IDS
        ],
        "dataSource": "SIMULATED",
    }


@router.post(
    "/event",
    summary="Trigger a traffic event",
    description=(
        "Switches the traffic layer to a scenario and re-applies it to the "
        "graph. Edge congestion, road closures and incidents all change for "
        "real, so a subsequent /agent/analyze or /routes/optimize sees the new "
        "conditions.\n\n"
        "Cached cost models are invalidated, because a calibration made under "
        "the previous traffic would otherwise be reused and quietly wrong."
    ),
    responses={
        200: {"description": "The new traffic state"},
        422: {"description": "Unknown scenario"},
    },
)
def event(
    scenario: str = Query(..., description="Scenario id from /simulation/scenarios"),
    graph: str | None = Query(default=None),
) -> dict:
    from traffic.simulator import SCENARIO_IDS
    from app.integrations.engine_bridge import get_engine, invalidate_caches

    if scenario not in SCENARIO_IDS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown scenario {scenario!r}. Known: {', '.join(SCENARIO_IDS)}",
        )

    engine = get_engine(graph)
    engine.set_scenario(scenario)
    # Cost models are calibrated against the traffic present when they were
    # built. Leaving them cached would route the new scenario using the old
    # one's reference scales.
    invalidate_caches()

    state = engine.state
    return {
        "ok": True,
        "scenario": scenario,
        "label": FRIENDLY.get(scenario, scenario),
        "closedEdges": len(getattr(state, "closures", []) or []),
        "incidents": [
            {"type": i.get("type"), "location": i.get("location"),
             "lat": i.get("lat"), "lon": i.get("lon")}
            for i in (getattr(state, "incidents", []) or [])
        ],
        "dataSource": "SIMULATED",
        "note": (
            "Generated traffic conditions, not measurements. The graph really "
            "changed — routes and ETAs computed after this reflect it."
        ),
    }


@router.post(
    "/congest-route",
    summary="Congest the active route specifically",
    description=(
        "Raises congestion on the road the driver is actually on.\n\n"
        "Scenario hotspots sit where real jams form, which often means they "
        "miss whichever route was chosen — and an event that does not touch "
        "the current route cannot demonstrate rerouting. This puts the "
        "disruption where it will be felt."
    ),
    responses={
        200: {"description": "Congestion applied"},
        409: {"description": "No active trip to congest"},
    },
)
def congest_route(
    level: float = Query(default=0.92, ge=0.0, le=0.98,
                         description="Congestion to apply, 0-0.98"),
    graph: str | None = Query(default=None),
) -> dict:
    from app.integrations.engine_bridge import get_engine, invalidate_caches

    engine = get_engine(graph)
    if engine.trip is None:
        raise HTTPException(
            status_code=409,
            detail="No active trip. Optimise a route first, then congest it.",
        )
    out = engine.spike_route(level=level)
    invalidate_caches()
    return {**out, "dataSource": "SIMULATED"}


@router.post(
    "/advance",
    summary="Move the simulated driver along the route",
    description=(
        "Places the driver `progress` of the way along the active trip. Nothing "
        "else: no congestion, no reroute check.\n\n"
        "A spike lands on the road AHEAD of the driver, so a demonstration needs "
        "the driver part-way along first. /routes/reroute also moves the driver, "
        "but it evaluates a reroute as it does — and an alert raised there, "
        "before the monitor sees the jam, would put the monitor's own alert "
        "inside the policy's cooldown."
    ),
    responses={409: {"description": "No active trip"}},
)
def advance(
    progress: float = Query(default=0.3, ge=0.0, le=0.95,
                            description="Fraction of the route already driven"),
    graph: str | None = Query(default=None),
) -> dict:
    from app.integrations.engine_bridge import get_engine

    engine = get_engine(graph)
    if engine.trip is None:
        raise HTTPException(status_code=409, detail="No active trip to advance.")
    # Forward only. Re-running a demo step must not move the driver backwards
    # onto road already driven.
    target = max(float(progress), engine.trip.progress)
    engine.advance(target)
    return {"ok": True, "progress": round(engine.trip.progress, 3), "dataSource": "SIMULATED"}


@router.post(
    "/reset",
    summary="Return traffic to normal",
    description="Clears events and closures by re-applying the 'normal' scenario.",
)
def reset(graph: str | None = Query(default=None)) -> dict:
    from app.integrations.engine_bridge import get_engine, invalidate_caches

    engine = get_engine(graph)
    engine.set_scenario("normal")
    invalidate_caches()
    return {"ok": True, "scenario": "normal", "dataSource": "SIMULATED"}
