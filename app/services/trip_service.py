"""
Trips — one journey, from "Start navigation" to arrival, as the user lived it.

WHY THIS EXISTS
---------------
History used to list optimisation *requests*: every press of the button, with
no idea whether anyone drove the route, whether it was switched on the way, or
what switching saved. A trip is the journey itself:

    start      the route the user chose to drive becomes the one the backend
               monitors (the same node sequence the car on the map follows)
    progress   the car's position, so the monitor looks at the road AHEAD
    reroute    recorded by the server when the user switches, from the
               engine's own figures — the browser is not trusted to report
               how much time it saved
    finish     arrived, or ended early

WHAT THE NUMBERS MEAN
---------------------
    planned_eta_min     the chosen route's ETA when navigation started
    original_eta_min    at the first switch: the ETA of STAYING on the road
                        you were on, from where you were
    optimized_eta_min   at the last switch: the ETA of the route switched to
    time_saved_min      the sum of what each switch saved against staying

"Time saved" is always against staying put at that moment, never against the
plan — a jam that forms mid-journey makes both roads slower than planned, and
comparing with the plan would hide the benefit or invent one.

ONE JOURNEY AT A TIME
---------------------
The routing engine holds a single active trip, so starting a trip replaces
whatever it was monitoring. The service remembers which trip that is, and a
trip that has been displaced — someone planned another route since — is told
so rather than silently advancing somebody else's journey.
"""

from __future__ import annotations

import threading

from app.core.logging import get_logger
from app.core.security import SessionUser
from app.utils.time_helpers import utc_now_iso

_logger = get_logger("services.trips")

MAX_PROGRESS = 0.95   # the same ceiling /simulation/advance uses

# id(engine) -> (trip_id, the ActiveTrip object the engine held when it started)
_monitored: dict[int, tuple[str, object]] = {}
_lock = threading.Lock()


class TripNotFound(LookupError):
    """No such trip — or it belongs to someone else, which is answered the same way."""


class TripConflict(RuntimeError):
    """The trip has ended, or the engine is now monitoring a different one."""


class InvalidTrip(ValueError):
    """The route sent is not a drivable path on the network."""


# ------------------------------------------------------------------ helpers

def _col():
    from app.database.collections import get_trips_col

    return get_trips_col()


def _id_query(trip_id: str) -> dict:
    from bson import ObjectId

    return {"_id": ObjectId(trip_id)} if ObjectId.is_valid(trip_id) else {"_id": trip_id}


def _level(congestion: float) -> str:
    c = congestion or 0.0
    return "low" if c < 0.3 else "moderate" if c < 0.5 else "heavy" if c < 0.7 else "severe"


def _own(trip_id: str, user: SessionUser) -> dict:
    doc = _col().find_one({**_id_query(trip_id), "user_id": user.id})
    if not doc:
        raise TripNotFound("No such trip.")
    return doc


def public_trip(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "status": doc.get("status"),
        "createdAt": doc.get("created_at"),
        "endedAt": doc.get("ended_at"),
        "graph": doc.get("graph"),
        "source": doc.get("source"),
        "destination": doc.get("destination"),
        "vehicle": doc.get("vehicle"),
        "mode": doc.get("mode"),
        "route": doc.get("route"),
        "currentRoute": doc.get("current_route"),
        "plannedEtaMin": doc.get("planned_eta_min"),
        "distanceKm": doc.get("distance_km"),
        "trafficCondition": doc.get("traffic_condition"),
        "progress": doc.get("progress", 0.0),
        "rerouted": bool(doc.get("rerouted")),
        "reroutes": doc.get("reroutes", []),
        "declined": doc.get("declined", 0),
        "originalEtaMin": doc.get("original_eta_min"),
        "optimizedEtaMin": doc.get("optimized_eta_min"),
        "timeSavedMin": doc.get("time_saved_min", 0.0),
        "endReason": doc.get("end_reason"),
    }


def _is_monitored(trip_id: str, engine) -> bool:
    with _lock:
        entry = _monitored.get(id(engine))
    return bool(entry and entry[0] == trip_id and engine.trip is entry[1])


# ------------------------------------------------------------------ journey

def start_trip(user: SessionUser, body) -> dict:
    """Make the chosen route the monitored trip, and record the journey."""
    from app.integrations.engine_bridge import get_engine
    from routing.rerouting import ActiveTrip
    from routing.route import evaluate_route

    engine = get_engine(body.graph)
    # OSM node ids travel as strings; the graph keys them as integers.
    nodes = [int(n) if str(n).lstrip("-").isdigit() else n for n in body.route.nodes]

    with engine.lock:
        if engine.cost_model is None:
            raise InvalidTrip("Plan a route first, then start navigation.")
        route = evaluate_route(engine.G, nodes, engine.cost_model, algorithm="navigation")
        if not route.valid:
            raise InvalidTrip(
                "That route is no longer a drivable path on this network — the "
                "traffic may have closed a road since it was planned. Find the "
                "route again.")
        # The route the user chose — which may be an alternative, not the one
        # the optimiser recommended — is what the monitor must watch.
        engine.trip = ActiveTrip(route=route)
        engine.alerts.new_trip()
        trip_obj = engine.trip

    now = utc_now_iso()
    col = _col()
    col.update_many(
        {"user_id": user.id, "status": "active"},
        {"$set": {"status": "cancelled", "ended_at": now,
                  "end_reason": "A new trip was started."}},
    )
    doc = {
        "user_id": user.id,
        "status": "active",
        "graph": body.graph,
        "request_id": body.request_id,
        "source": body.source.model_dump(),
        "destination": body.destination.model_dump(),
        "vehicle": body.vehicle,
        "mode": body.mode,
        "route": {"label": body.route.label, "via": body.route.via,
                  "distanceKm": body.route.distance_km, "etaMin": body.route.eta_min,
                  "congestion": body.route.congestion},
        "current_route": {"distanceKm": body.route.distance_km,
                          "etaMin": body.route.eta_min, "via": body.route.via},
        "planned_eta_min": body.route.eta_min,
        "distance_km": body.route.distance_km,
        "traffic_condition": _level(body.route.congestion),
        "progress": 0.0,
        "rerouted": False,
        "reroutes": [],
        "declined": 0,
        "original_eta_min": None,
        "optimized_eta_min": None,
        "time_saved_min": 0.0,
        "created_at": now,
        "ended_at": None,
    }
    doc["_id"] = col.insert_one(doc).inserted_id
    trip_id = str(doc["_id"])
    with _lock:
        _monitored[id(engine)] = (trip_id, trip_obj)
    _logger.info("Trip %s started by %s: %.1f km, %.0f min", trip_id, user.email,
                 body.route.distance_km, body.route.eta_min)
    return public_trip(doc)


def report_progress(user: SessionUser, trip_id: str, fraction: float) -> dict:
    """Move the monitored driver to where the car is. Forward only."""
    from app.integrations.engine_bridge import get_engine

    doc = _own(trip_id, user)
    if doc.get("status") != "active":
        raise TripConflict("This trip has ended.")
    engine = get_engine(doc.get("graph"))
    if not _is_monitored(trip_id, engine):
        raise TripConflict(
            "This trip is no longer the one being monitored — another route was "
            "planned since. Start navigation again to be watched.")
    target = min(max(float(fraction), engine.trip.progress), MAX_PROGRESS)
    out = engine.advance(target)
    _col().update_one({"_id": doc["_id"]}, {"$set": {"progress": out["progress"]}})
    return {"progress": out["progress"], "remainingEtaMin": out.get("remainingEtaMin"),
            "blocked": out.get("blocked", False)}


def outlook(user: SessionUser, trip_id: str) -> dict:
    """
    The road ahead: congestion now, the forecaster's prediction, and whether a
    better route exists — asked in preview, so it spends no alert.
    """
    from app.integrations.engine_bridge import get_engine
    from app.services.agent_service import AgentUnavailableError, TrafficAgent

    doc = _own(trip_id, user)
    engine = get_engine(doc.get("graph"))
    if doc.get("status") != "active" or not _is_monitored(trip_id, engine):
        raise TripConflict("This trip is not being monitored.")
    try:
        d = TrafficAgent(graph=doc.get("graph")).analyse(apply_forecast=True, commit=False)
    except AgentUnavailableError as exc:
        raise TripConflict(str(exc)) from exc
    fc = d.get("forecast") or {}
    return {
        "forecastApplied": bool(fc.get("applied")),
        "horizonMin": fc.get("horizonMin"),
        "observedCongestion": fc.get("observedMean"),
        "predictedCongestion": fc.get("predictedMean"),
        "worsening": bool(fc.get("worsening")),
        "decision": d.get("decision"),
        "currentEtaMin": d.get("currentEta"),
        "alternativeEtaMin": d.get("alternativeEta"),
        "timeSavedMin": d.get("timeSaved"),
        "suppressedBecause": d.get("suppressedBecause"),
        "dataSource": "PREDICTION" if fc.get("applied") else "SIMULATED",
    }


def finish_trip(user: SessionUser, trip_id: str, status: str) -> dict:
    from app.integrations.engine_bridge import get_engine

    doc = _own(trip_id, user)
    if doc.get("status") == status:
        return public_trip(doc)
    if doc.get("status") != "active":
        raise TripConflict(f"This trip already ended ({doc.get('status')}).")
    changes = {"status": status, "ended_at": utc_now_iso(),
               "end_reason": "Arrived." if status == "completed" else "Ended by the driver."}
    if status == "completed":
        changes["progress"] = 1.0
    _col().update_one({"_id": doc["_id"]}, {"$set": changes})
    doc.update(changes)
    try:
        engine = get_engine(doc.get("graph"))
        with _lock:
            if _monitored.get(id(engine), ("",))[0] == trip_id:
                _monitored.pop(id(engine), None)
    except Exception:  # the engine being gone does not stop the trip ending
        pass
    return public_trip(doc)


def list_trips(user: SessionUser, limit: int = 50) -> list[dict]:
    cursor = _col().find({"user_id": user.id}).sort("created_at", -1).limit(limit)
    return [public_trip(d) for d in cursor]


# ---------------------------------------------- called by the agent endpoints

def monitored_trip(engine) -> str | None:
    """The trip id the engine's active trip belongs to, if it belongs to one."""
    with _lock:
        entry = _monitored.get(id(engine))
    return entry[0] if entry and engine.trip is entry[1] else None


def record_reroute(trip_id: str, engine, out: dict) -> None:
    """
    The user switched. Recorded from the engine's accept result — measured on
    the server, not reported by the browser.
    """
    try:
        col = _col()
        doc = col.find_one(_id_query(trip_id))
        if not doc:
            return
        event = {
            "at": utc_now_iso(),
            "previousEtaMin": out.get("previousEtaMin"),
            "newEtaMin": out.get("newEtaMin"),
            "timeSavedMin": out.get("timeSavedMin"),
            "savedPct": out.get("savedPct"),
            "reason": out.get("reason"),
            "newDistanceKm": (out.get("newRoute") or {}).get("distanceKm"),
        }
        saved = round(float(doc.get("time_saved_min") or 0.0)
                      + float(out.get("timeSavedMin") or 0.0), 1)
        new_route = out.get("newRoute") or {}
        col.update_one({"_id": doc["_id"]}, {
            "$push": {"reroutes": event},
            "$set": {
                "rerouted": True,
                "original_eta_min": (doc.get("original_eta_min")
                                     if doc.get("original_eta_min") is not None
                                     else out.get("previousEtaMin")),
                "optimized_eta_min": out.get("newEtaMin"),
                "time_saved_min": saved,
                "current_route": {"distanceKm": new_route.get("distanceKm"),
                                  "etaMin": new_route.get("etaMin"),
                                  "via": new_route.get("via")},
                "progress": 0.0,
            },
        })
        # The engine now holds the new route as its trip; it is still this journey.
        with _lock:
            _monitored[id(engine)] = (trip_id, engine.trip)
    except Exception as exc:
        _logger.warning("Could not record the reroute on trip %s: %s", trip_id, exc)


def record_decline(trip_id: str) -> None:
    try:
        _col().update_one(_id_query(trip_id), {"$inc": {"declined": 1}})
    except Exception as exc:
        _logger.warning("Could not record the declined reroute on trip %s: %s", trip_id, exc)
