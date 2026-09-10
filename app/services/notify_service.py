"""
Notifications — telling the driver, in words, what the agent decided.

THE RULE THAT SHAPES ALL OF THIS
--------------------------------
The language model PHRASES. It never computes.

Every number in a notification — the current ETA, the alternative, the minutes
saved, the congestion — is measured by the routing engine and the forecaster
before the model is called at all. The model receives those figures and is
asked for one sentence. It is not asked what the traffic is, whether to
reroute, or how much time a driver would save, because a model that is allowed
to answer those questions will eventually invent an answer, and an invented
"13 minutes saved" is indistinguishable on screen from a measured one.

So the notification is built first and completely, in deterministic text. The
model is an optional pass that improves the wording of something already true,
and every notification records which produced it.

WITHOUT AN API KEY
------------------
Everything still works. The deterministic sentence is the notification, marked
`phrasedBy: "template"`. Nothing is disabled, nothing errors, and the driver is
told exactly the same facts — in slightly stiffer English.

DELIVERY
--------
Notifications are held in a bounded queue and pushed to any connected listener.
A page that is open receives them without asking; a page that connects later
gets the recent ones. They do not persist beyond the process, because they are
transient advice about a journey in progress rather than a record of anything.
"""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from collections import deque

from app.core.logging import get_logger

_logger = get_logger("services.notify")

KEEP = 50

_lock = threading.Lock()
_notifications: deque = deque(maxlen=KEEP)
_listeners: set = set()
_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    """
    Remember the event loop so a worker thread can reach the listeners.

    The monitor runs its ticks in a thread pool; broadcasting from there needs
    the loop that owns the WebSockets, and asking for the running loop inside
    a worker thread finds nothing.
    """
    global _loop
    _loop = loop


# --------------------------------------------------------------- building

def _template(decision: dict) -> str:
    """
    The notification, written from measured values alone.

    This is the fallback when no model is configured, and the source of truth
    when one is: the model is shown this and asked to say the same thing more
    naturally.
    """
    saved = decision.get("timeSaved") or 0.0
    current = decision.get("currentEta")
    alternative = decision.get("alternativeEta")

    if decision.get("blocked"):
        return ("The road ahead on your route is closed. A new route has been "
                f"calculated — {alternative} min from where you are now.")

    if decision.get("decision") == "reroute":
        pct = decision.get("savedPct") or 0
        return (f"Heavy traffic ahead on your route. Switching saves about "
                f"{saved:.0f} minutes — {current:.0f} min now versus "
                f"{alternative:.0f} min on the alternative, {pct:.0f}% better.")

    if decision.get("betterButBelowThreshold"):
        return (f"A slightly faster route exists, saving about {saved:.0f} "
                "minutes. That is below the threshold for suggesting a change, "
                "so you are staying on your current route.")

    return "Your current route is still the best option. No change needed."


async def _phrase_with_model(decision: dict, facts: str) -> tuple[str, str]:
    """
    Ask the model to say the same thing more naturally.

    Returns (text, phrasedBy). Any failure — no key, a timeout, a refusal —
    returns the template, because a notification that does not arrive is worse
    than one that is plainly worded.
    """
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.ai_api_key:
        return facts, "template"

    system = (
        "You rephrase a traffic notification for a driver. You are given the "
        "facts, already measured. Rewrite them as one or two short, calm "
        "sentences a driver could read at a glance.\n"
        "Rules, without exception:\n"
        "- Use ONLY the numbers you are given. Never add, adjust or round away "
        "a figure, and never introduce one that is not present.\n"
        "- Do not speculate about causes, roads or conditions you were not told.\n"
        "- If a fact is absent, leave it out rather than filling the gap.\n"
        "Reply with the sentence only."
    )

    try:
        import httpx

        async with httpx.AsyncClient(timeout=8) as client:
            res = await client.post(
                f"{settings.ai_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.ai_api_key}"},
                json={
                    "model": settings.ai_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": facts},
                    ],
                    # Low, because this is a rewording task and invention is the
                    # one failure that matters here.
                    "temperature": 0.2,
                    "max_tokens": 120,
                },
            )
            res.raise_for_status()
            text = (res.json()["choices"][0]["message"].get("content") or "").strip()
    except Exception as exc:
        _logger.warning("Notification phrasing failed, using the template: %s", exc)
        return facts, "template"

    if not text:
        return facts, "template"
    return text, "llm"


# ------------------------------------------------------------- publishing

def _broadcast(payload: dict) -> None:
    """Push to every connected listener, from whichever thread we are on."""
    if _loop is None or not _listeners:
        return

    async def send_all():
        dead = []
        for ws in list(_listeners):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _listeners.discard(ws)

    try:
        asyncio.run_coroutine_threadsafe(send_all(), _loop)
    except Exception as exc:
        _logger.warning("Could not broadcast notification: %s", exc)


async def publish(decision: dict, source: str = "agent",
                  facts: str | None = None, kind: str = "alert") -> dict:
    """
    Turn an agent decision into a notification, phrase it, and deliver it.

    `facts` replaces the standard alert wording when the message is about
    something else — the assistant's check of a route the driver has just
    switched to. It is still built from measured values by the caller, and
    still the only text a model may reword.
    """
    facts = facts or _template(decision)
    text, phrased_by = await _phrase_with_model(decision, facts)

    note = {
        "id": uuid.uuid4().hex[:12],
        "at": time.time(),
        "source": source,
        "kind": kind,
        "severity": decision.get("severity", "info"),
        "decision": decision.get("decision"),
        "text": text,
        # The deterministic version is kept alongside, so a phrased message can
        # always be checked against what was actually measured.
        "facts": facts,
        "phrasedBy": phrased_by,
        "currentEta": decision.get("currentEta"),
        "alternativeEta": decision.get("alternativeEta"),
        "timeSaved": decision.get("timeSaved"),
        # A route check reports; it never asks the driver to act, even if the
        # agent's comparison favours something — that is what the next alert,
        # past the policy's cooldown, is for.
        "actionable": (kind == "alert" and decision.get("decision") == "reroute"
                       and bool(decision.get("alert"))),
        "reason": decision.get("reason"),
    }

    with _lock:
        _notifications.appendleft(note)
    _broadcast(note)
    _logger.info("Notification (%s, %s): %s", note["severity"], phrased_by, text[:80])
    return note


def publish_threadsafe(decision: dict, source: str = "agent",
                       facts: str | None = None, kind: str = "alert") -> None:
    """Publish from a worker thread — the monitor's ticks run in one."""
    if _loop is None:
        _logger.debug("No event loop bound; notification dropped")
        return
    asyncio.run_coroutine_threadsafe(publish(decision, source, facts, kind), _loop)


# ---------------------------------------------------------------- reading

def recent(limit: int = 20) -> list:
    with _lock:
        return list(_notifications)[:limit]


def clear() -> dict:
    with _lock:
        n = len(_notifications)
        _notifications.clear()
    return {"cleared": n}


def add_listener(ws) -> None:
    _listeners.add(ws)


def remove_listener(ws) -> None:
    _listeners.discard(ws)


def listener_count() -> int:
    return len(_listeners)
