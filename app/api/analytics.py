"""
Analytics, scalability and multi-stop endpoints.

These three pages of the dashboard had nothing to call: the frontend requested
/analytics and /scalability, and both 404'd, so the Analytics page rendered
empty and the Benchmark page showed an empty table.

Everything here is served from the real optimisation engine. The heavy
endpoints (benchmark, scalability) are cached in-process because a full run
takes tens of seconds and the dashboard re-fetches on every visit.
"""
from __future__ import annotations

import threading

from fastapi import APIRouter, Query

from app.core.logging import get_logger

router = APIRouter(prefix="/analytics", tags=["Analytics"])
_logger = get_logger("api.analytics")

_cache: dict = {}
_lock = threading.Lock()


def _engine():
    from app.integrations.engine_bridge import get_engine
    return get_engine()


def _cached(key, build):
    """Compute once per process. Benchmarks take tens of seconds."""
    if key not in _cache:
        with _lock:
            if key not in _cache:
                _cache[key] = build()
    return _cache[key]


def _route_performance(limit: int = 6) -> list[dict]:
    """
    Distance and travel time of recently optimised routes.

    This chart used to plot `congestion * 30` as "Distance (km)" and
    `congestion * 60` as "Time (min)" for six road segments. Those were not
    distances or times at all — nothing was measured — and the giveaway was
    visible on screen: when every sampled segment sat at 95% congestion, all
    six pairs of bars came out exactly the same height.

    It now reads real optimisation results. An empty list is returned when no
    routes have been run yet, which the chart renders as an empty state; that
    is the honest answer, and better than filling the axes with arithmetic on
    an unrelated number.
    """
    try:
        from app.database.collections import get_optimization_results_col

        # Over-fetch, because consecutive rows are frequently the same trip run
        # again and those collapse to one bar below.
        cursor = (
            get_optimization_results_col()
            .find({}, {"route": 1, "source_name": 1, "destination_name": 1,
                       "request_id": 1, "created_at": 1})
            .sort("created_at", -1)
            .limit(limit * 10)
        )
    except Exception as exc:
        _logger.warning("route performance unavailable: %s", exc)
        return []

    out, seen = [], set()
    for doc in cursor:
        route = doc.get("route") or {}
        distance = route.get("distance_km")
        minutes = route.get("travel_time_minutes")
        if distance is None or minutes is None:
            continue

        src, dst = doc.get("source_name"), doc.get("destination_name")
        if src and dst:
            label = f"{src} → {dst}"
        else:
            # Older rows predate the endpoint names being recorded.
            label = f"Route {str(doc.get('request_id', ''))[:8]}"

        # Re-running the same trip should not draw the same bar six times. Key
        # on the endpoints where we know them, otherwise on the geometry, and
        # keep the most recent run of each.
        key = (src, dst) if (src and dst) else (round(float(distance), 2),
                                                round(float(minutes), 1))
        if key in seen:
            continue
        seen.add(key)

        out.append({
            "route": label[:28],
            "distance": round(float(distance), 2),
            "time": round(float(minutes), 1),
        })
        if len(out) >= limit:
            break

    out.reverse()          # oldest on the left, so the chart reads left to right
    return out


@router.get("", summary="Dashboard analytics")
@router.get("/", include_in_schema=False)
def analytics() -> dict:
    """
    Headline stats and chart series for the Analytics page.

    The traffic trend is the simulator's own diurnal profile, which is the
    honest thing to show: it is the curve the congestion model is actually
    driven by, not a decorative sine wave. That curve is now measured from 31
    days of real Indian junction counts rather than fitted by hand — see
    scripts/derive_diurnal_profile.py.
    """
    from traffic.simulator import MEASURED_HOURLY_VEHICLES, diurnal_factor

    engine = _engine()
    traffic = engine.traffic(limit=400)
    segments = traffic["segments"]

    counts = {"low": 0, "moderate": 0, "heavy": 0, "severe": 0}
    for s in segments:
        counts[s["level"]] += 1
    total = max(len(segments), 1)

    congestions = [s["congestion"] for s in segments] or [0.0]
    mean_congestion = sum(congestions) / len(congestions)

    # Peak intensity scales the diurnal curve to today's scenario.
    peak = max(mean_congestion, 0.01)
    trend = [
        {
            "hour": f"{h:02d}:00",
            # diurnal_factor is normalised to its own peak already, so the
            # curve needs no second division. It used to be divided by the
            # value at 18:30, which was where the OLD hand-fitted formula
            # peaked; the measured peak is 17:00 and that divisor now rescales
            # the whole curve wrongly.
            "congestion": round(diurnal_factor(h) * peak * 100, 1),
            # Measured at the junction the profile came from, not the 4,000
            # that used to sit here — that number was invented and described
            # nothing.
            "vehicles": MEASURED_HOURLY_VEHICLES[h],
        }
        for h in range(0, 24, 2)
    ]

    return {
        "stats": [
            {"label": "Average Traffic", "value": round(mean_congestion * 100, 1),
             "suffix": "%", "tone": "yellow", "trend": None},
            {"label": "Monitored Segments", "value": len(segments),
             "suffix": "", "tone": "cyan", "trend": None},
            {"label": "Severe Segments", "value": counts["severe"],
             "suffix": "", "tone": "red", "trend": None},
            {"label": "Heavy Segments", "value": counts["heavy"],
             "suffix": "", "tone": "orange", "trend": None},
            {"label": "Active Incidents", "value": len(traffic["incidents"]),
             "suffix": "", "tone": "orange", "trend": None},
            {"label": "Graph Edges", "value": engine.G.number_of_edges(),
             "suffix": "", "tone": "cyan", "trend": None},
        ],
        "trend": trend,
        "prediction": [
            {"time": "now", "actual": round(mean_congestion * 100, 1),
             "predicted": round(mean_congestion * 100, 1)},
            *[
                {"time": f"+{m}m", "actual": None,
                 "predicted": round(min(mean_congestion * (1 + m / 60) * 100, 99), 1)}
                for m in (5, 10, 15, 20, 25, 30)
            ],
        ],
        # Stated by the backend rather than assumed by the chart. The forward
        # curve is current congestion grown at a fixed rate — there is no
        # trained model behind it, and the UI must not imply otherwise. When an
        # LSTM/GRU is wired in, this string changes and the label follows.
        "predictionMethod": "linear",
        "predictionNote": (
            "Projection only: current congestion extended at a fixed rate. "
            "No trained forecasting model is wired in yet."
        ),
        "performance": _route_performance(),
        "distribution": [
            {"name": "Low", "value": round(counts["low"] / total * 100), "color": "#34d399"},
            {"name": "Moderate", "value": round(counts["moderate"] / total * 100), "color": "#fbbf24"},
            {"name": "Heavy", "value": round(counts["heavy"] / total * 100), "color": "#fb923c"},
            {"name": "Severe", "value": round(counts["severe"] / total * 100), "color": "#f43f5e"},
        ],
        "scenario": engine.scenario,
        "isDemoData": False,
    }


@router.get("/scalability", summary="Scalability of each algorithm")
def scalability(
    trials: int = Query(default=5, ge=1, le=30),
    max_stops: int = Query(default=7, ge=3, le=9),
) -> dict:
    """
    Runtime and solution quality against problem size.

    Brute force is included up to 8 stops; beyond that it is intractable, which
    is the point the chart is making.
    """
    def build():
        engine = _engine()
        sizes = tuple(range(3, max_stops + 1))
        rows = engine.scalability(sizes=sizes, trials=trials)["rows"]
        return {
            "isDemoData": False,
            "rows": [
                {
                    "nodes": r["stops"],
                    "orderings": r["orderings"],
                    "bruteMs": r.get("bruteMs"),
                    "dijkstra": r.get("bruteMs") or 0,
                    "qpso": r.get("QPSO") or 0,
                    "pso": r.get("PSO") or 0,
                    "ga": r.get("GA") or 0,
                    "qpsoQuality": round(100 - (r.get("QPSOGap") or 0), 2),
                }
                for r in rows
            ],
        }

    return _cached(f"scalability:{trials}:{max_stops}", build)
