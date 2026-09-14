"""
The vehicle profiles a route can be computed for.

Served so the interface draws its choices — and each one's rules — from the
same table the cost model routes by, rather than a second list in JavaScript
that could disagree with it.
"""

from __future__ import annotations

from fastapi import APIRouter

from graph.vehicles import DEFAULT_VEHICLE, VEHICLES

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get(
    "",
    summary="Vehicle profiles",
    description=(
        "Each profile's road-class exclusions and top speed, and what they rest "
        "on. Pass a profile's id as `vehicle` on /routes/optimize.\n\n"
        "Only one rule is close to universal in India — non-motorised vehicles "
        "do not use access-controlled expressways. The rest are modelling "
        "assumptions that vary by state and city, and `assumption` says which."
    ),
)
@router.get("/", include_in_schema=False)
def vehicles() -> dict:
    return {
        "default": DEFAULT_VEHICLE,
        "vehicles": [p.describe() for p in VEHICLES.values()],
        "note": (
            "Access and speed rules are modelling assumptions, not local law. "
            "Filtering through traffic, time-of-day bans and bus lanes are not "
            "modelled."
        ),
    }
