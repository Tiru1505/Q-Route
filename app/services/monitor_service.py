"""
The continuous monitoring loop.

WHAT THIS IS
------------
Everything in the pipeline worked but had to be asked. Detection ran when a
file was uploaded, the forecast ran when the agent was called, the agent ran
when a button was pressed. Nothing watched anything on its own, so a jam
forming on the driver's route went unnoticed until somebody thought to look.

This is the part that keeps watching.

TWO CADENCES, BECAUSE THE DATA HAS TWO CADENCES
-----------------------------------------------
The loop ticks on a short interval. What it DOES on each tick depends on
whether anything has actually changed:

    every tick        re-evaluate the current route against the graph as it
                      stands now. Cheap, and catches closures and congestion
                      the moment the traffic layer applies them.

    when input moves  re-run the forecast. The LSTM reads 15-minute vehicle
                      counts, so feeding it the same window twice returns the
                      same answer twice. Re-running it every tick would burn
                      real CPU to reproduce a number we already have.

A fingerprint of the inputs — observation count per road, traffic scenario,
trip progress — decides which. When it has not moved, the tick reports
"unchanged" rather than manufacturing the appearance of fresh work.

WHY NOT EVERY SECOND
--------------------
A per-second forecast is not achievable from this data and no amount of
engineering changes that. The model was trained on 15-minute counts; its
shortest horizon is fifteen minutes. Running it 900 times inside one window
produces 900 identical answers.

What genuinely runs continuously is DETECTION — measured at about 8 frames per
second on this CPU — and the route evaluation here. A live vehicle count beside
a forecast that updates when its window closes is the honest version of "always
watching", and it is what this loop implements.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from app.core.logging import get_logger

_logger = get_logger("services.monitor")

# How often the loop wakes. Short enough that a closure is noticed promptly,
# long enough that a re-solve is not running back to back.
DEFAULT_TICK_S = 15.0

# Never re-forecast more often than this, even when inputs keep changing —
# the model cannot say anything new inside one 15-minute bucket.
MIN_FORECAST_GAP_S = 60.0

# Ticks kept for the status surface.
HISTORY = 40


@dataclass
class Tick:
    at: float
    kind: str                      # forecast | evaluate | idle | error
    decision: str | None = None
    time_saved: float | None = None
    alerted: bool = False
    # Why no alert, when the comparison favoured an alternative. Without this a
    # tick reading "keep" beside a 47-minute saving looks like the loop ignored
    # it, when the policy deliberately stayed quiet — usually its cooldown
    # after having already raised one.
    suppressed: str | None = None
    note: str = ""
    ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "at": round(self.at, 1),
            "agoS": round(time.time() - self.at, 1),
            "kind": self.kind,
            "decision": self.decision,
            "timeSaved": self.time_saved,
            "alerted": self.alerted,
            "suppressed": self.suppressed,
            "note": self.note,
            "ms": round(self.ms),
        }


@dataclass
class MonitorState:
    running: bool = False
    tick_s: float = DEFAULT_TICK_S
    graph: str | None = None
    started_at: float = 0.0
    ticks: int = 0
    forecasts: int = 0
    alerts: int = 0
    errors: int = 0
    last_fingerprint: tuple = ()
    last_forecast_at: float = 0.0
    history: deque = field(default_factory=lambda: deque(maxlen=HISTORY))


_state = MonitorState()
_lock = threading.Lock()
_task: asyncio.Task | None = None


def _fingerprint(graph: str | None) -> tuple:
    """
    What the forecast depends on. When this is unchanged, so is the answer.

    Deliberately cheap: counting observations and reading the scenario costs
    nothing next to running the model, which is the whole point of checking.
    """
    from app.integrations.engine_bridge import get_engine
    from app.services.observation_store import summary

    try:
        engine = get_engine(graph)
    except Exception:
        return ("no-engine",)

    obs = summary()
    per_road = tuple(sorted((r["roadId"], r["observations"]) for r in obs["roads"]))
    progress = round(engine.trip.progress, 3) if engine.trip is not None else None
    return (engine.scenario, progress, per_road)


def _run_tick(graph: str | None, force_forecast: bool = False) -> Tick:
    """One pass. Runs in a worker thread — everything here is blocking."""
    from app.integrations.engine_bridge import get_engine
    from app.services.agent_service import AgentUnavailableError, TrafficAgent

    t0 = time.perf_counter()
    now = time.time()

    try:
        engine = get_engine(graph)
    except Exception as exc:
        return Tick(now, "error", note=f"engine unavailable: {exc}",
                    ms=(time.perf_counter() - t0) * 1000)

    if engine.trip is None:
        return Tick(now, "idle", note="no active trip to monitor",
                    ms=(time.perf_counter() - t0) * 1000)

    fingerprint = _fingerprint(graph)
    changed = fingerprint != _state.last_fingerprint
    cooled = (now - _state.last_forecast_at) >= MIN_FORECAST_GAP_S
    forecast = force_forecast or (changed and cooled)

    try:
        # apply_forecast=False still re-solves against the live graph, which is
        # what catches a closure or a congestion spike between forecasts.
        result = TrafficAgent(graph=graph).analyse(apply_forecast=forecast)
    except AgentUnavailableError as exc:
        return Tick(now, "idle", note=str(exc),
                    ms=(time.perf_counter() - t0) * 1000)
    except Exception as exc:
        _logger.warning("monitor tick failed: %s", exc)
        return Tick(now, "error", note=str(exc)[:160],
                    ms=(time.perf_counter() - t0) * 1000)

    with _lock:
        _state.last_fingerprint = fingerprint
        if forecast:
            _state.last_forecast_at = now
            _state.forecasts += 1

    alerted = result.get("alert") is not None

    # Tell the driver. Only when the policy actually raised something, or a
    # closure makes the current plan undriveable — a notification for every
    # tick would be noise, and noise is how a real alert gets ignored.
    if alerted or result.get("blocked"):
        from app.services import notify_service

        notify_service.publish_threadsafe(result, source="monitor")

    note = ("inputs changed — forecast refreshed" if forecast
            else "inputs unchanged — route re-evaluated, forecast reused")

    suppressed = None
    if not alerted and result.get("betterButBelowThreshold"):
        suppressed = (result.get("suppressedBecause")
                      or "saving is below the alert policy threshold")

    return Tick(
        now, "forecast" if forecast else "evaluate",
        decision=result.get("decision"),
        time_saved=result.get("timeSaved"),
        alerted=alerted,
        suppressed=suppressed,
        note=note,
        ms=(time.perf_counter() - t0) * 1000,
    )


async def _loop() -> None:
    """The monitor itself. Heavy work goes to a thread so the API stays live."""
    _logger.info("Traffic monitor started (tick %.0fs)", _state.tick_s)
    first = True
    try:
        while _state.running:
            try:
                tick = await asyncio.to_thread(_run_tick, _state.graph, first)
                first = False
                with _lock:
                    _state.ticks += 1
                    if tick.alerted:
                        _state.alerts += 1
                    if tick.kind == "error":
                        _state.errors += 1
                    _state.history.append(tick)
                if tick.alerted:
                    _logger.info("Monitor raised an alert: %s saving %s min",
                                 tick.decision, tick.time_saved)
            except asyncio.CancelledError:
                raise
            except Exception as exc:                 # a bad tick must not kill
                _logger.warning("monitor loop error: %s", exc)
                with _lock:
                    _state.errors += 1

            await asyncio.sleep(_state.tick_s)
    except asyncio.CancelledError:
        pass
    finally:
        _logger.info("Traffic monitor stopped after %d ticks", _state.ticks)


async def start(tick_s: float = DEFAULT_TICK_S, graph: str | None = None) -> dict:
    """
    Begin monitoring. Idempotent — starting a running monitor re-tunes it.

    Async because it creates the task. FastAPI runs a sync endpoint in a
    worker thread, where asyncio.create_task raises "no running event loop" —
    which is exactly how this first failed.
    """
    global _task

    with _lock:
        already = _state.running
        _state.tick_s = max(float(tick_s), 1.0)
        _state.graph = graph
        if not already:
            _state.running = True
            _state.started_at = time.time()
            _state.ticks = _state.forecasts = _state.alerts = _state.errors = 0
            _state.last_fingerprint = ()
            _state.last_forecast_at = 0.0
            _state.history.clear()

    if not already:
        _task = asyncio.create_task(_loop())
    return status()


async def stop() -> dict:
    """Stop monitoring and wait for the in-flight tick to finish."""
    global _task

    with _lock:
        _state.running = False
    task, _task = _task, None
    if task is not None:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    return status()


def status() -> dict:
    with _lock:
        uptime = time.time() - _state.started_at if _state.started_at else 0.0
        next_forecast = None
        if _state.running and _state.last_forecast_at:
            next_forecast = max(
                0.0,
                MIN_FORECAST_GAP_S - (time.time() - _state.last_forecast_at),
            )
        return {
            "running": _state.running,
            "tickSeconds": _state.tick_s,
            "graph": _state.graph,
            "uptimeS": round(uptime, 1),
            "ticks": _state.ticks,
            "forecasts": _state.forecasts,
            "alerts": _state.alerts,
            "errors": _state.errors,
            "minForecastGapS": MIN_FORECAST_GAP_S,
            "nextForecastInS": (round(next_forecast, 1)
                                if next_forecast is not None else None),
            "history": [t.to_dict() for t in reversed(_state.history)],
            "note": (
                "The route is re-evaluated every tick; the forecast is re-run "
                "only when its inputs have changed. The model reads 15-minute "
                "counts, so re-running it inside one window returns the answer "
                "it already gave."
            ),
        }
