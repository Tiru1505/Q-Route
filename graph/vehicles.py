"""
What kind of vehicle is making the trip, and what that changes about the route.

WHY A VEHICLE CHANGES THE ROUTE
-------------------------------
The road graph's speeds are car speeds. A route that is right for a car is
wrong for a vehicle that cannot use some of those roads, or cannot reach the
speeds the graph assumes. Two effects are modelled, both entering through the
cost model so every algorithm — Dijkstra, QPSO, PSO, GA — sees the same rules:

  ACCESS     A road class the vehicle may not use costs infinity, exactly the
             way a closed road already does.
  TOP SPEED  Time on a road uses the slower of the road's current speed and
             the vehicle's maximum. In a jam everyone crawls at the jam's speed;
             on an open expressway a truck does not do car speed.

Both are per-edge, non-negative and additive, so Dijkstra stays provably
optimal and remains the ground truth the metaheuristics are measured against.

WHAT IS NOT MODELLED
--------------------
Two-wheelers filtering through queues, time-of-day entry bans for heavy goods
vehicles (Hyderabad restricts them inside the ORR at certain hours), bus-only
lanes, turn restrictions, and height or weight limits. Each is real; none has
data here to model it honestly.

THE RULES ARE ASSUMPTIONS
-------------------------
Only one rule below is close to universal in India: non-motorised vehicles do
not use access-controlled expressways. Everything else — which classes are
barred from which roads, and every top speed — is a modelling assumption that
varies by state and city and must be checked against the local notification
before it is presented as the law. The API and the interface both say so.
They are kept in this one table so that checking them means reading one place.

The car is the baseline and changes nothing: with no exclusions and no speed
cap it reproduces, exactly, every route computed before vehicles existed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# OSM road classes that are access-controlled expressways in India.
EXPRESSWAY = frozenset({"motorway", "motorway_link"})


def road_class(data) -> str:
    """The edge's OSM highway class. OSMnx stores a list when ways were merged."""
    h = data.get("highway")
    return str(h[0] if isinstance(h, list) else h)


@dataclass(frozen=True)
class VehicleProfile:
    id: str
    label: str
    excluded: frozenset = field(default_factory=frozenset)
    max_speed_kph: float | None = None
    basis: str = ""
    assumption: bool = True

    def permits(self, data) -> bool:
        return not self.excluded or road_class(data) not in self.excluded

    def adjust_time(self, time_s: float, length_m: float) -> float:
        """Travel time at the slower of the road's speed and this vehicle's cap."""
        if not self.max_speed_kph:
            return time_s
        return max(time_s, length_m / (self.max_speed_kph / 3.6))

    @property
    def neutral(self) -> bool:
        """True when this profile changes nothing — the car."""
        return not self.excluded and not self.max_speed_kph

    def describe(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "avoids": sorted(self.excluded),
            "maxSpeedKph": self.max_speed_kph,
            "basis": self.basis,
            "assumption": self.assumption,
        }


VEHICLES: dict[str, VehicleProfile] = {
    p.id: p for p in (
        VehicleProfile(
            "car", "Car",
            basis="The baseline. The road graph's speeds are car speeds.",
            assumption=False,
        ),
        VehicleProfile(
            "two_wheeler", "Two-wheeler", excluded=EXPRESSWAY,
            basis=("Access-controlled expressways commonly prohibit two-wheelers. "
                   "Check the local notification."),
        ),
        VehicleProfile(
            "auto_rickshaw", "Auto-rickshaw", excluded=EXPRESSWAY, max_speed_kph=50,
            basis=("Three-wheelers are commonly barred from expressways and are "
                   "slow; 50 km/h is an assumed top speed."),
        ),
        VehicleProfile(
            "bus", "Bus", max_speed_kph=60,
            basis="60 km/h is an assumed top speed for a city bus.",
        ),
        # No road ban. An earlier version barred trucks from every residential
        # street, and a truck then could not reach Charminar from Hitec City at
        # all: any address on a residential street became unreachable. Real
        # heavy-vehicle rules restrict THROUGH traffic and set hours and zones
        # — which needs data this project does not have — not access to an
        # address. A rule that makes ordinary trips impossible is worse than
        # none, so only the speed cap is modelled.
        VehicleProfile(
            "truck", "Truck", max_speed_kph=60,
            basis=("60 km/h is an assumed top speed. Residential and time-of-day "
                   "restrictions on heavy vehicles are not modelled."),
        ),
        VehicleProfile(
            "bicycle", "Bicycle", excluded=EXPRESSWAY, max_speed_kph=15,
            basis=("Non-motorised vehicles do not use access-controlled "
                   "expressways. 15 km/h is an assumed riding speed."),
        ),
    )
}

DEFAULT_VEHICLE = "car"


def vehicle_profile(vehicle: str | VehicleProfile | None) -> VehicleProfile:
    """Resolve an id (or None, for the car) to its profile."""
    if isinstance(vehicle, VehicleProfile):
        return vehicle
    key = vehicle or DEFAULT_VEHICLE
    if key not in VEHICLES:
        raise ValueError(f"Unknown vehicle '{key}'. Choose from {sorted(VEHICLES)}")
    return VEHICLES[key]
