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
    # How much of a jam's delay this vehicle actually suffers.
    #
    # A car and a two-wheeler both do 60 km/h on an empty road, so a top speed
    # cannot express the difference between them — the difference only appears
    # when the road is full. A two-wheeler filters past a queue the car has to
    # sit in; a bus cannot, and loses more than a car because it also stops.
    # 1.0 is the car, and leaves its times exactly as they were.
    jam_share: float = 1.0
    basis: str = ""
    assumption: bool = True

    def permits(self, data) -> bool:
        return not self.excluded or road_class(data) not in self.excluded

    def adjust_time(self, time_s: float, length_m: float,
                    free_flow_s: float | None = None) -> float:
        """
        Travel time for THIS vehicle on one road, in two steps.

        First the congestion delay is shared: everything above the free-flow
        time is a queue, and `jam_share` says how much of that queue this
        vehicle actually waits in. Then the top speed caps whatever is left —
        a bus cannot take a clear 80 km/h road at 80.

        Without a free-flow time (a graph built before the traffic layer, or a
        test edge) the delay cannot be separated from the journey, so the
        sharing is skipped rather than guessed.
        """
        if free_flow_s and self.jam_share != 1.0 and time_s > free_flow_s:
            time_s = free_flow_s + self.jam_share * (time_s - free_flow_s)
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
            "jamShare": self.jam_share,
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
            "two_wheeler", "Two-wheeler", excluded=EXPRESSWAY, jam_share=0.55,
            basis=("Access-controlled expressways commonly prohibit two-wheelers. "
                   "Check the local notification. In a jam it keeps moving where "
                   "a car queues: an assumed 55% of the car's delay, in the same "
                   "spirit as its 0.5 PCU — half a car's road space."),
        ),
        VehicleProfile(
            "auto_rickshaw", "Auto-rickshaw", excluded=EXPRESSWAY, max_speed_kph=50,
            jam_share=0.8,
            basis=("Three-wheelers are commonly barred from expressways and are "
                   "slow; 50 km/h is an assumed top speed. Narrower than a car "
                   "but not as nimble as a two-wheeler: an assumed 80% of the "
                   "car's delay in a jam."),
        ),
        VehicleProfile(
            "bus", "Bus", max_speed_kph=60, jam_share=1.15,
            basis=("60 km/h is an assumed top speed for a city bus. It cannot "
                   "filter and pulls away slowly, so it is assumed to lose 15% "
                   "more than a car in a jam. Bus stops are not modelled."),
        ),
        # No road ban. An earlier version barred trucks from every residential
        # street, and a truck then could not reach Charminar from Hitec City at
        # all: any address on a residential street became unreachable. Real
        # heavy-vehicle rules restrict THROUGH traffic and set hours and zones
        # — which needs data this project does not have — not access to an
        # address. A rule that makes ordinary trips impossible is worse than
        # none, so only the speed cap is modelled.
        VehicleProfile(
            "truck", "Truck", max_speed_kph=60, jam_share=1.15,
            basis=("60 km/h is an assumed top speed. Residential and time-of-day "
                   "restrictions on heavy vehicles are not modelled. Like a bus "
                   "it cannot filter: an assumed 15% more delay than a car."),
        ),
        VehicleProfile(
            "bicycle", "Bicycle", excluded=EXPRESSWAY, max_speed_kph=15,
            jam_share=0.6,
            basis=("Non-motorised vehicles do not use access-controlled "
                   "expressways. 15 km/h is an assumed riding speed, which "
                   "already dominates: a jam rarely slows a bicycle below it."),
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
