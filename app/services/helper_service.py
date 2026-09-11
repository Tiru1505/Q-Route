"""
The assistant's answers, taken from the system's own state.

WHY THIS IS NOT JUST A CALL TO A LANGUAGE MODEL
-----------------------------------------------
The questions a driver or a judge actually asks the robot are questions this
system already knows the answer to. "Will there be congestion?" is the
forecaster's output. "Should I switch?" is the agent's decision. "How long will
it take?" is the active trip's ETA. Sending those to a language model would
route a known fact through something that can only guess at it.

So the assistant answers from the real state first. A model, when one is
configured, handles the open-ended remainder — and never the numbers.

WHAT THAT BUYS
--------------
It works with no API key. Every question below is answered from measured state,
so the robot is useful on a laptop with no internet, and the figures it quotes
are the same ones the rest of the interface is showing rather than a model's
recollection of them.

WHEN IT DOES NOT KNOW
---------------------
It says so, and says what would make the answer available — no active trip, no
observations for that road, no forecaster trained. An assistant that produces a
confident paragraph when it has nothing is worse than one that admits the gap,
because the paragraph is indistinguishable from a real answer.
"""

from __future__ import annotations

import re

from app.core.logging import get_logger

_logger = get_logger("services.helper")


def _pct(x) -> str:
    return f"{float(x) * 100:.0f}%" if x is not None else "unknown"


# --------------------------------------------------------------- answers

def _forecast_answer(graph: str | None) -> dict:
    """What the forecaster expects on the road ahead."""
    from app.integrations.engine_bridge import get_engine
    from app.services.agent_service import AgentUnavailableError, TrafficAgent

    try:
        engine = get_engine(graph)
    except Exception as exc:
        return {"text": f"The road network is not loaded: {exc}"}

    if engine.trip is None:
        return {"text": (
            "There is no journey in progress, so there is nothing to forecast "
            "yet. Optimise a route first and I will watch it for you — I check "
            "the road ahead and tell you if it is worth changing.")}

    try:
        d = TrafficAgent(graph=graph).analyse(apply_forecast=True, commit=False)
    except AgentUnavailableError as exc:
        return {"text": str(exc)}

    fc = d.get("forecast") or {}
    if not fc.get("applied"):
        # It used to stop here — promising an answer "based on conditions as
        # they are" and then giving none. The re-solve against current traffic
        # still happened, so its verdict is said.
        return {"text": (
            "I could not forecast the road ahead just now, so this is based on "
            "conditions as they are rather than what is coming. " + _verdict(d)),
            "decision": _compact(d)}

    direction = "rising" if fc.get("worsening") else "not rising"
    text = (
        f"Looking {fc['horizonMin']} minutes ahead across {fc['samples']} points "
        f"on your route: congestion is {_pct(fc['observedMean'])} now and "
        f"{_pct(fc['predictedMean'])} predicted — {direction}."
    )
    text += " " + _verdict(d)
    return {"text": text, "decision": _compact(d)}


def _verdict(d: dict) -> str:
    """
    The recommendation, in the agent's own terms.

    The suppression reason is READ, never assumed. An earlier version of this
    said "too small to be worth changing for" whenever an alternative was
    suppressed, and then reported a 19-minute saving in the same sentence —
    because the real reason was a cooldown, not the threshold. The assistant
    stating a false reason about its own system is the worst failure available
    to it, so the reason comes from `suppressedBecause` when there is one.
    """
    if d.get("blocked"):
        return "The road ahead is closed, so a replacement route is needed."

    if d.get("decision") == "reroute":
        return (f"I would switch: the alternative saves {d['timeSaved']:.0f} "
                f"minutes, {d['currentEta']:.0f} down to {d['alternativeEta']:.0f}.")

    if d.get("betterButBelowThreshold"):
        saved = d.get("timeSaved") or 0.0
        why = d.get("suppressedBecause")
        head = f"A faster route exists, saving about {saved:.0f} minutes"
        return f"{head}, but I am not suggesting a switch: {why}." if why else (
            f"{head}, which is below the threshold for suggesting a change.")

    return "Your current route is still the best option."


def _compact(d: dict) -> dict:
    """
    The decision without its route geometry.

    The full contract carries every coordinate of the recommended path — tens
    of kilobytes the chat panel never reads. The figures a caller might want to
    display are kept; the polyline is what the map endpoint is for.
    """
    keep = ("decision", "severity", "reason", "currentEta", "alternativeEta",
            "timeSaved", "savedPct", "blocked", "betterButBelowThreshold",
            "suppressedBecause", "algorithm", "analysisMs")
    out = {k: d.get(k) for k in keep if k in d}
    fc = d.get("forecast") or {}
    if fc:
        out["forecast"] = {k: fc.get(k) for k in
                           ("applied", "horizonMin", "samples", "observedMean",
                            "predictedMean", "worsening")}
    return out


def _reroute_answer(graph: str | None) -> dict:
    from app.services.agent_service import AgentUnavailableError, TrafficAgent

    try:
        d = TrafficAgent(graph=graph).analyse(apply_forecast=True, commit=False)
    except AgentUnavailableError as exc:
        return {"text": str(exc)}
    return {"text": d.get("reason") or "I have no recommendation right now.",
            "decision": _compact(d)}


def _traffic_answer(graph: str | None) -> dict:
    from app.integrations.engine_bridge import get_engine

    try:
        engine = get_engine(graph)
        snap = engine.traffic(limit=200)
    except Exception as exc:
        return {"text": f"I cannot read the traffic layer: {exc}"}

    segs = snap["segments"]
    if not segs:
        return {"text": "No traffic data is loaded."}
    mean = sum(s["congestion"] for s in segs) / len(segs)
    heavy = sum(1 for s in segs if s["level"] in ("heavy", "severe"))
    return {"text": (
        f"Across {len(segs)} sampled roads congestion averages {_pct(mean)}, "
        f"with {heavy} heavily congested. The scenario in force is "
        f"'{engine.scenario}', and {len(snap['incidents'])} incidents are "
        "active. These are simulated conditions, not live measurements.")}


def _observations_answer() -> dict:
    from app.services.forecast_service import _load
    from app.services.observation_store import summary

    obs = summary()
    try:
        model, _ = _load()
        need = model.lookback
    except Exception:
        return {"text": "The forecaster is not trained, so I cannot use counts yet."}

    if not obs["roads"]:
        return {"text": (
            f"No traffic has been observed yet. Upload footage in the Traffic "
            f"Analysis Lab or start a camera feed, and after {need} observations "
            "on a road I can forecast it from real counts rather than an estimate.")}

    lines = [f"{r['name']}: {r['observations']}/{need}" for r in obs["roads"][:4]]
    ready = [r for r in obs["roads"] if r["observations"] >= need]
    text = "Roads I have counts for — " + "; ".join(lines) + "."
    text += (f" {len(ready)} of them can drive a forecast from measured traffic."
             if ready else
             f" None has the {need} needed yet, so forecasts still use an estimate.")
    return {"text": text}


def _route_answer(graph: str | None) -> dict:
    from app.integrations.engine_bridge import get_engine

    try:
        engine = get_engine(graph)
    except Exception as exc:
        return {"text": f"The road network is not loaded: {exc}"}

    if engine.trip is None:
        return {"text": ("No journey is active. Choose a start and destination "
                         "and press Optimize Route, and I will track it.")}
    # Set when a route was solved, which is also when a trip exists — but read
    # defensively, because an unset cost model would raise inside a chat reply.
    cost_model = getattr(engine, "cost_model", None)
    if cost_model is None:
        return {"text": "A journey is active but its cost model is missing; "
                        "re-optimise the route and ask me again."}

    remaining = engine.trip.remaining_on_current_route(engine.G, cost_model)
    if remaining is None:
        return {"text": "The road ahead is blocked — a new route is needed."}
    return {"text": (
        f"You are {engine.trip.progress * 100:.0f}% along, with about "
        f"{remaining.time_min:.0f} minutes and {remaining.distance_km:.1f} km "
        "left on the current route.")}


def _system_answer() -> dict:
    from app.core.config import get_settings
    from app.services.forecast_service import ForecastService
    from app.services.vision_service import VisionService

    parts = [
        f"detector {'ready' if VisionService().available() else 'not trained'}",
        f"forecaster {'ready' if ForecastService().available() else 'not trained'}",
        f"wording {'by assistant' if get_settings().ai_api_key else 'from templates'}",
    ]
    return {"text": (
        "I watch the road you are driving. A detector counts vehicles from "
        "camera footage, a trained model forecasts the next fifteen minutes "
        "from those counts, and if a better route appears I tell you how much "
        "time it saves. Right now: " + ", ".join(parts) + ".")}


def _help_answer() -> dict:
    return {"text": (
        "Ask me things like: will there be congestion, should I reroute, how "
        "long is left, what is the traffic like, what have you counted, or how "
        "does this work. Every number I give is measured by the system — I do "
        "not estimate them myself."),
        "suggestions": ["Will there be congestion?", "Should I reroute?",
                        "How long is left?", "What have you counted?"]}


# --------------------------------------------------------------- routing

INTENTS = [
    (r"\b(predict|forecast|congestion ahead|will there be|next \d+ min|upcoming)\b",
     "forecast"),
    (r"\b(reroute|re-route|switch|alternative|another route|better route|should i)\b",
     "reroute"),
    (r"\b(how long|eta|time left|remaining|arrive|distance)\b", "route"),
    (r"\b(traffic|congested|jam|busy|conditions)\b", "traffic"),
    (r"\b(count\w*|observ\w*|camera|footage|upload\w*|vehicles?|yolo|detect\w*)\b",
     "observations"),
    (r"\b(help|what can you|how do you|explain|how does this|who are you|what are you)\b",
     "help"),
    (r"\b(status|system|working|ready|online)\b", "system"),
]


def classify(question: str) -> str | None:
    q = (question or "").lower()
    for pattern, intent in INTENTS:
        if re.search(pattern, q):
            return intent
    return None


def answer(question: str, graph: str | None = None) -> dict:
    """
    Answer from real state where possible.

    Returns the answer plus how it was produced, so the interface can say
    whether a figure was measured or a model was asked.
    """
    intent = classify(question)
    handlers = {
        "forecast": lambda: _forecast_answer(graph),
        "reroute": lambda: _reroute_answer(graph),
        "route": lambda: _route_answer(graph),
        "traffic": lambda: _traffic_answer(graph),
        "observations": _observations_answer,
        "system": _system_answer,
        "help": _help_answer,
    }

    if intent in handlers:
        try:
            out = handlers[intent]()
        except Exception as exc:
            _logger.warning("helper '%s' failed: %s", intent, exc)
            return {"text": f"I could not check that just now ({exc}).",
                    "intent": intent, "source": "error"}
        out.update({"intent": intent, "source": "measured"})
        return out

    return {
        "intent": None,
        "source": "unmatched",
        "text": (
            "I can answer about the forecast, whether to reroute, your ETA, "
            "current traffic, and what has been counted so far. Ask 'help' to "
            "see examples."),
        "suggestions": ["Will there be congestion?", "Should I reroute?",
                        "What is the traffic like?", "Help"],
    }


# ------------------------------------------------------- after a switch

def check_new_route(graph: str | None = None) -> dict | None:
    """
    Look at the route the driver has just switched to, and say what is there.

    Runs after a reroute is accepted. The alert that prompted the switch was
    about the OLD road; nothing had yet looked ahead on the NEW one. This is
    the same analysis the monitor runs — forecast the road ahead, re-solve,
    decide — pointed at the new trip, and its result is published as the
    assistant's message to the driver.

    If the new road is itself forecast to worsen, it says so. It does not raise
    a fresh alert: the policy's cooldown, reset by the switch, is what stops
    the system asking the driver to change route twice in a minute.
    """
    from app.integrations.engine_bridge import get_engine
    from app.services import notify_service
    from app.services.agent_service import AgentUnavailableError, TrafficAgent

    try:
        engine = get_engine(graph)
        if engine.trip is None:
            return None
        d = TrafficAgent(graph=graph).analyse(apply_forecast=True, commit=False)
        remaining = engine.trip.remaining_on_current_route(engine.G, engine.cost_model)
    except AgentUnavailableError:
        return None
    except Exception as exc:
        _logger.warning("route check after switch failed: %s", exc)
        return None

    text = _route_check_text(d, remaining)
    notify_service.publish_threadsafe(d, source="assistant", facts=text, kind="route-check")
    return {"text": text, "decision": _compact(d)}


def _route_check_text(d: dict, remaining) -> str:
    """The check, in sentences built only from what was measured."""
    if remaining is None:
        return ("I checked your new route: the road ahead has since been closed, "
                "so it needs replacing.")

    parts = [f"I've checked your new route: about {remaining.time_min:.0f} min "
             f"and {remaining.distance_km:.1f} km to go."]

    fc = d.get("forecast") or {}
    if fc.get("applied"):
        trend = "rising" if fc.get("worsening") else "not rising"
        parts.append(
            f"Congestion ahead is {_pct(fc['observedMean'])} now and forecast "
            f"{_pct(fc['predictedMean'])} in {fc['horizonMin']} minutes — {trend}.")
    else:
        parts.append("I couldn't forecast the road ahead just now, so this is "
                     "based on conditions as they are.")

    parts.append(_verdict(d))
    return " ".join(parts)
