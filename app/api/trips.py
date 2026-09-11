"""
Trip endpoints — the user's journeys. Every one needs a signed-in user, and a
user only ever sees or changes their own trips.

    POST /trips                  start navigation on the chosen route
    POST /trips/{id}/progress    where the car is now (forward only)
    GET  /trips/{id}/outlook     congestion now vs predicted, on the road ahead
    POST /trips/{id}/finish      arrived, or ended early
    GET  /trips                  my trips, newest first (the History page)

Switching routes is recorded by /agent/accept itself, from the engine's own
figures, so there is no endpoint here for the browser to report a saving.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.core.security import SessionUser, current_user
from app.services import trip_service
from app.services.trip_service import InvalidTrip, TripConflict, TripNotFound

router = APIRouter(prefix="/trips", tags=["trips"])


class Place(BaseModel):
    name: str = Field(default="", max_length=200)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class TripRoute(BaseModel):
    label: str = Field(default="", max_length=80)
    via: str = Field(default="", max_length=300)
    distance_km: float = Field(..., ge=0)
    eta_min: float = Field(..., ge=0)
    congestion: float = Field(default=0.0, ge=0, le=1)
    nodes: list[str] = Field(..., min_length=2, max_length=50_000,
                             description="The road-graph nodes the car will follow, in order")


class StartTrip(BaseModel):
    graph: str | None = None
    request_id: str | None = Field(default=None, max_length=100)
    source: Place
    destination: Place
    route: TripRoute
    vehicle: str = Field(default="car", max_length=40)
    mode: str = Field(default="balanced", max_length=40)


class Progress(BaseModel):
    fraction: float = Field(..., ge=0.0, le=1.0,
                            description="How far along the current route the car is, by road nodes")


class Finish(BaseModel):
    status: Literal["completed", "cancelled"]


def _answer(fn, *args):
    try:
        return fn(*args)
    except TripNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TripConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidTrip as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("", summary="Start navigation on the chosen route")
async def start(body: StartTrip, user: SessionUser = Depends(current_user)) -> dict:
    from app.services import monitor_service

    # Off the event loop: the engine lock can be held by a forecast for a
    # few seconds, and waiting for it here would stall every other request.
    trip = await run_in_threadpool(_answer, trip_service.start_trip, user, body)

    # A user cannot start the monitor (that is an admin control), but a trip
    # nobody watches can never raise an alert. So starting a trip makes sure
    # it is watched — at the current cadence if it is already running.
    status = monitor_service.status()
    await monitor_service.start(
        tick_s=status["tickSeconds"] if status["running"] else monitor_service.DEFAULT_TICK_S,
        graph=body.graph,
    )
    return {"trip": trip}


@router.post("/{trip_id}/progress", summary="Where the car is now")
def progress(trip_id: str, body: Progress, user: SessionUser = Depends(current_user)) -> dict:
    return _answer(trip_service.report_progress, user, trip_id, body.fraction)


@router.get("/{trip_id}/outlook", summary="Congestion now and predicted, on the road ahead")
def outlook(trip_id: str, user: SessionUser = Depends(current_user)) -> dict:
    return _answer(trip_service.outlook, user, trip_id)


@router.post("/{trip_id}/finish", summary="Arrived, or ended the trip early")
def finish(trip_id: str, body: Finish, user: SessionUser = Depends(current_user)) -> dict:
    return {"trip": _answer(trip_service.finish_trip, user, trip_id, body.status)}


@router.get("", summary="My trips, newest first")
def mine(limit: int = Query(default=50, ge=1, le=200),
         user: SessionUser = Depends(current_user)) -> dict:
    return {"trips": trip_service.list_trips(user, limit)}
