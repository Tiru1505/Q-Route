"""Route optimization API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.route_models import RerouteRequest, RouteRequest, RouteResponse
from app.services.route_service import RouteService

from app.core.security import SessionUser, current_user, optional_user, require_admin

router = APIRouter(prefix="/routes", tags=["routes"])

# Control-room actions: they change traffic, the monitor or shared state for
# everyone, so they need an admin session (see app/core/security.py).
_admin = [Depends(require_admin)]
_service = RouteService()


def _owned(request: RouteRequest, user: SessionUser | None) -> RouteRequest:
    """
    Tag the stored route with the SIGNED-IN user. The body's user_id used to be
    trusted, so anyone could file routes under anyone; with a session, the
    session decides. Unsigned calls keep the old behaviour.
    """
    if user is None:
        return request
    return request.model_copy(update={"user_id": user.id})


@router.post(
    "/optimize",
    response_model=RouteResponse,
    summary="Optimize a route",
    description=(
        "Find the optimal route between source and destination using the "
        "specified algorithm (default: QPSO). Returns route coordinates, "
        "distance, travel time, ETA, and congestion data."
    ),
    responses={
        200: {
            "description": "Successfully optimized route",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "request_id": "abc123",
                        "algorithm": "qpso",
                        "route": {
                            "coordinates": [
                                {"lat": 17.3850, "lon": 78.4867},
                                {"lat": 17.4500, "lon": 78.3800},
                            ],
                            "nodes": ["node-0001", "node-0002"],
                            "distance_km": 12.4,
                            "travel_time_minutes": 24.5,
                        },
                        "congestion": 0.38,
                        "fitness": 0.82,
                        "execution_time_ms": 145,
                    }
                }
            },
        },
        422: {"description": "Validation error (invalid coordinates, algorithm, etc.)"},
        503: {"description": "Graph or traffic service unavailable"},
    },
)
def optimize_route(request: RouteRequest,
                   user: SessionUser | None = Depends(optional_user)) -> RouteResponse:
    return _service.optimize(_owned(request, user))


@router.post(
    "/alternatives",
    response_model=list[RouteResponse],
    summary="Get alternative routes",
    description="Generate alternative routes using different algorithms.",
)
def alternative_routes(request: RouteRequest,
                       user: SessionUser | None = Depends(optional_user)) -> list[RouteResponse]:
    return _service.get_alternatives(_owned(request, user))


@router.post(
    "/reroute",
    dependencies=_admin,
    summary="Re-evaluate the active trip",
    description=(
        "Decide whether a better route exists from where the driver is now. "
        "Advances the active trip to `progress`, optionally congests the road "
        "ahead, then re-solves with Dijkstra from the current position. "
        "Requires a route to have been optimised first — the trip it creates "
        "is what this re-evaluates."
    ),
    responses={
        200: {
            "description": "The comparison. shouldReroute may be false, which "
                           "is a real answer, not a failure.",
            "content": {
                "application/json": {
                    "example": {
                        "shouldReroute": True,
                        "reason": "congestion ahead: remaining journey is +64% off plan",
                        "previousEtaMin": 21.4,
                        "currentEtaMin": 35.1,
                        "newEtaMin": 24.8,
                        "timeSavedMin": 10.3,
                        "savedPct": 29.3,
                        "algorithm": "Dijkstra",
                        "blocked": False,
                    }
                }
            },
        },
        404: {"description": "No active trip — optimise a route first"},
    },
)
def reroute(request: RerouteRequest) -> dict:
    return _service.reroute(request)


@router.get(
    "/history",
    summary="Route optimization history",
    description="Your past route optimisations. Admins may pass user_id to see another user's.",
)
def route_history(
    user_id: str | None = Query(default=None, description="Admins only: whose history"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results to return"),
    user: SessionUser = Depends(current_user),
) -> dict:
    # This trusted a user_id from the URL, so anyone could read anyone's
    # routes. A user now always gets their own; an admin may name someone.
    owner = user_id if (user.is_admin and user_id) else user.id
    results = _service.get_history(user_id=owner, limit=limit)
    return {"results": results}


@router.get(
    "/{request_id}",
    response_model=RouteResponse,
    summary="Get route by request ID",
    description="Retrieve a specific route optimization result.",
    responses={404: {"description": "Route request not found"}},
)
def get_route(request_id: str) -> RouteResponse:
    result = _service.get_by_id(request_id)
    if result is None:
        raise HTTPException(status_code=404, detail="route request not found")
    return result
