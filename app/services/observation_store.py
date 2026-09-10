"""
Traffic observations, keyed by road.

WHY THIS EXISTS
---------------
Uploaded footage already produced a forecast, but that forecast lived inside
the browser session that uploaded it. The rolling window was keyed by session
id, which is the right shape for showing one visitor their own progress and the
wrong shape for the system: an observation belongs to a ROAD, not to a tab.

The consequence was two parallel universes. The Traffic Analysis Lab counted
real vehicles on Inner Ring Road and forecast them; the routing agent, asked
about that same road seconds later, ignored every one of those counts and
re-derived a forecast by anchoring to the simulator. Nothing on screen revealed
that the two disagreed about the same piece of tarmac.

This is the shared surface between them. Vision writes here; the forecaster
reads here before falling back to anything synthetic.

WHAT IT DOES NOT DO
-------------------
It does not persist. Observations live for the process, because they are demo
input rather than a system of record, and writing them to MongoDB would imply a
provenance they do not have.

It does not interpolate. A road with two observations has two, not four — the
forecaster needs a full window and is told plainly when one is not there, since
padding a short series is exactly how a confident number gets built out of
nothing.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque

from app.core.logging import get_logger

_logger = get_logger("services.observations")

# Per road. Enough for the longest lookback the forecaster might use, with room
# to see recent history beyond the window it consumes.
MAX_PER_ROAD = 32

# Roads tracked at once. Bounded because this is process memory and a long demo
# session should not grow without limit.
MAX_ROADS = 256

_lock = threading.Lock()
_roads: dict[str, dict] = {}


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def record(road_id: str, city: str, name: str, lat: float, lon: float,
           counts: dict, source: str = "upload") -> dict:
    """
    Append one observation for a road.

    `counts` are vehicles per 15 minutes by the forecaster's four classes —
    flow, not occupancy. An image cannot supply this and must not call here.
    """
    with _lock:
        entry = _roads.get(road_id)
        if entry is None:
            if len(_roads) >= MAX_ROADS:
                oldest = min(_roads, key=lambda k: _roads[k]["last"])
                _roads.pop(oldest, None)
            entry = _roads[road_id] = {
                "road_id": road_id, "city": city, "name": name,
                "lat": lat, "lon": lon,
                "observations": deque(maxlen=MAX_PER_ROAD),
                "last": 0.0,
            }
        now = time.time()
        entry["observations"].append({"counts": dict(counts), "at": now,
                                      "source": source})
        entry["last"] = now
        entry["lat"], entry["lon"] = lat, lon
        depth = len(entry["observations"])

    _logger.info("Observation on %s (%s): %d in the series", name, road_id, depth)
    return {"roadId": road_id, "observations": depth}


def series_for_road(road_id: str, need: int) -> list | None:
    """The most recent `need` observations for a road, or None if short."""
    with _lock:
        entry = _roads.get(road_id)
        if entry is None or len(entry["observations"]) < need:
            return None
        return list(entry["observations"])[-need:]


def nearest_with_series(lat: float, lon: float, need: int,
                        radius_m: float = 2000.0) -> dict | None:
    """
    The closest road within `radius_m` that has a full window of observations.

    Distance is measured to the road's own anchor point, so a forecast is only
    driven by counts taken somewhere near the place being asked about. Roads
    with a partial series are skipped rather than padded.
    """
    best, best_d = None, float("inf")
    with _lock:
        for entry in _roads.values():
            if len(entry["observations"]) < need:
                continue
            d = _haversine_m(lat, lon, entry["lat"], entry["lon"])
            if d < best_d and d <= radius_m:
                best, best_d = entry, d
    if best is None:
        return None
    return {
        "road_id": best["road_id"],
        "name": best["name"],
        "city": best["city"],
        "distance_m": round(best_d, 1),
        "observations": list(best["observations"])[-need:],
        "depth": len(best["observations"]),
    }


def summary() -> dict:
    """What has been observed, for status surfaces."""
    with _lock:
        roads = [{
            "roadId": e["road_id"], "name": e["name"], "city": e["city"],
            "observations": len(e["observations"]),
            "lastSeenS": round(time.time() - e["last"], 1),
        } for e in _roads.values()]
    roads.sort(key=lambda r: r["lastSeenS"])
    return {"roads": roads, "total": len(roads)}


def clear(road_id: str | None = None) -> dict:
    with _lock:
        if road_id:
            existed = _roads.pop(road_id, None) is not None
            return {"cleared": 1 if existed else 0}
        n = len(_roads)
        _roads.clear()
        return {"cleared": n}
