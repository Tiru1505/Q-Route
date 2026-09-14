"""
The multi-objective cost model — the single objective function every algorithm
minimises. Dijkstra, QPSO, PSO and GA all import this, which is what makes the
benchmark fair.

THE IDEA
--------
Each road segment has three costs that are measured in different units:

    travel time      seconds
    distance         metres
    congestion       "congested metres" = length x congestion  (0..1)

You cannot add seconds to metres. So we divide each by a REFERENCE value taken
from one specific route — the free-flow fastest route between the same two
points — which makes all three dimensionless:

    fitness(route) = w_t * (time     / T_ref)
                   + w_d * (distance / D_ref)
                   + w_c * (congested_metres / D_ref)

Congestion is normalised by D_ref as well, because congested-metres and metres
are the same unit. That means w_c trades off directly against w_d: at
w_c == w_d, driving one kilometre of fully jammed road costs the same as
driving an extra kilometre.

WHY THIS NORMALISATION
----------------------
Fitness becomes readable. The free-flow reference route scores exactly
w_t + w_d (0.7 in balanced mode, since its congestion is 0). A route scoring
1.4x that is 40% worse. The numbers mean the same thing for every
origin-destination pair, which is what lets you average across trials.

WHY IT STAYS ADDITIVE
---------------------
Every term is a non-negative per-edge quantity divided by a constant, so the
route fitness is exactly the sum of its edge costs. That is precisely the
condition Dijkstra requires to be optimal — which is why Dijkstra gives us
ground truth to measure the metaheuristics against.
"""
import math
from dataclasses import dataclass, asdict, field

import networkx as nx

from graph.vehicles import DEFAULT_VEHICLE, VEHICLES, VehicleProfile, vehicle_profile

# Preset objective weights. These are the four modes exposed in the UI.
MODES = {
    "balanced":       {"time": 0.40, "distance": 0.30, "congestion": 0.30},
    "fastest":        {"time": 0.70, "distance": 0.20, "congestion": 0.10},
    "shortest":       {"time": 0.20, "distance": 0.70, "congestion": 0.10},
    "low_congestion": {"time": 0.20, "distance": 0.10, "congestion": 0.70},
}

CLOSED_STATUSES = {"closed", "blocked"}


class NoPathError(ValueError):
    """
    No route connects the two points under these rules.

    Its own type because, once vehicles can be barred from roads, it is an
    ordinary answer — a bicycle cannot reach a point served only by an
    expressway — and the API has to report it as "no route", not as a crash
    or an outage. Subclasses ValueError, which is what calibrate always raised.
    """


@dataclass(frozen=True)
class ObjectiveWeights:
    time: float = 0.40
    distance: float = 0.30
    congestion: float = 0.30

    @classmethod
    def from_mode(cls, mode="balanced"):
        if mode not in MODES:
            raise ValueError(f"Unknown mode '{mode}'. Choose from {list(MODES)}")
        return cls(**MODES[mode])

    def normalised(self):
        """Weights summing to 1, so fitness is comparable across modes."""
        total = self.time + self.distance + self.congestion
        if total <= 0:
            raise ValueError("Objective weights must sum to a positive value.")
        return ObjectiveWeights(self.time / total, self.distance / total,
                                self.congestion / total)

    def as_dict(self):
        return asdict(self)


def edge_components(data):
    """
    The three raw costs of traversing one edge.

    time_s comes from `current_time_s`, which the traffic layer (Phase 4)
    updates when congestion changes. With no traffic loaded it equals the
    free-flow time, so this module works before Phase 4 exists.
    """
    length_m = float(data.get("length_m", data.get("length", 0.0)) or 0.0)
    time_s = float(data.get("current_time_s", data.get("free_flow_time_s", 0.0)) or 0.0)
    congestion = float(data.get("congestion", 0.0) or 0.0)
    congestion = min(max(congestion, 0.0), 1.0)
    return time_s, length_m, length_m * congestion


def is_closed(data):
    return str(data.get("road_status", "open")).lower() in CLOSED_STATUSES


@dataclass
class CostModel:
    """Objective weights plus the reference scales used to normalise them."""

    weights: ObjectiveWeights
    ref_time_s: float
    ref_distance_m: float
    mode: str = "balanced"
    # Which roads the traveller may use and how fast they can go. The car is
    # neutral, so every model built before vehicles existed behaves the same.
    vehicle: VehicleProfile = field(default_factory=lambda: VEHICLES[DEFAULT_VEHICLE])

    # ---------------------------------------------------------------- build
    @classmethod
    def calibrate(cls, G, source, target, mode="balanced", weights=None, vehicle=None):
        """
        Establish the reference scales from the free-flow fastest route between
        the same endpoints. Uses NetworkX directly (not our own Dijkstra) purely
        to avoid a circular import.

        The reference is the fastest route THIS vehicle could take, on the
        roads it may use at the speed it can reach. Against a car's reference a
        bicycle's every route would score as three times worse than free flow,
        and the readable-fitness property below — a free-flow route scores
        exactly w_t + w_d — would hold only for cars.
        """
        w = (weights or ObjectiveWeights.from_mode(mode)).normalised()
        profile = vehicle_profile(vehicle)

        if profile.neutral:
            # The car. Kept exactly as it was, so every route and benchmark
            # computed before vehicles existed is reproduced bit for bit.
            try:
                path = nx.shortest_path(G, source, target, weight="free_flow_time_s")
            except nx.NetworkXNoPath as exc:
                raise NoPathError(
                    f"No route exists between {source} and {target}."
                ) from exc

            t_ref = d_ref = 0.0
            for u, v in zip(path, path[1:]):
                data = min(G[u][v].values(), key=lambda d: d.get("free_flow_time_s", math.inf))
                t_ref += float(data.get("free_flow_time_s", 0.0) or 0.0)
                d_ref += float(data.get("length_m", 0.0) or 0.0)
        else:
            def free_time(d):
                length = float(d.get("length_m", 0.0) or 0.0)
                return profile.adjust_time(float(d.get("free_flow_time_s", 0.0) or 0.0), length)

            def weight(_u, _v, keydict):
                usable = [free_time(d) for d in keydict.values() if profile.permits(d)]
                return min(usable) if usable else None      # None hides the edge

            try:
                path = nx.shortest_path(G, source, target, weight=weight)
            except nx.NetworkXNoPath as exc:
                raise NoPathError(
                    f"No route a {profile.label.lower()} may use exists between "
                    f"{source} and {target}."
                ) from exc

            t_ref = d_ref = 0.0
            for u, v in zip(path, path[1:]):
                data = min((d for d in G[u][v].values() if profile.permits(d)), key=free_time)
                t_ref += free_time(data)
                d_ref += float(data.get("length_m", 0.0) or 0.0)

        # Floors guard against degenerate instances (source == target).
        return cls(weights=w, ref_time_s=max(t_ref, 1.0),
                   ref_distance_m=max(d_ref, 1.0), mode=mode, vehicle=profile)

    # ----------------------------------------------------------------- use
    def usable(self, data):
        """Open, and a road this vehicle is allowed on."""
        return not is_closed(data) and self.vehicle.permits(data)

    def components(self, data):
        """
        The three raw costs of one edge, for THIS vehicle.

        Use this wherever a cost model is in hand, rather than edge_components:
        the route would otherwise be chosen for the vehicle and then timed as if
        driven by a car, and the ETA shown would be the car's.
        """
        time_s, length_m, congested_m = edge_components(data)
        return self.vehicle.adjust_time(time_s, length_m), length_m, congested_m

    def edge_cost(self, data):
        """Normalised cost of one edge. Infinite for a closed road, or one this vehicle may not use."""
        if is_closed(data):
            return math.inf
        vehicle = self.vehicle
        if vehicle.excluded and not vehicle.permits(data):
            return math.inf
        time_s, length_m, congested_m = edge_components(data)
        if vehicle.max_speed_kph:
            time_s = vehicle.adjust_time(time_s, length_m)
        return (
            self.weights.time * (time_s / self.ref_time_s)
            + self.weights.distance * (length_m / self.ref_distance_m)
            + self.weights.congestion * (congested_m / self.ref_distance_m)
        )

    def best_edge(self, G, u, v):
        """
        Cheapest parallel edge between u and v.

        OSM graphs are MultiDiGraphs: two nodes can be joined by several edges
        (a service road beside a main road, for example). Routing should use the
        cheapest one, and every algorithm must agree on which that is.
        """
        best, best_cost = None, math.inf
        for data in G[u][v].values():
            c = self.edge_cost(data)
            if c < best_cost:
                best, best_cost = data, c
        return best, best_cost

    def fitness(self, time_s, distance_m, congested_m):
        """Route-level objective value. Lower is better."""
        return (
            self.weights.time * (time_s / self.ref_time_s)
            + self.weights.distance * (distance_m / self.ref_distance_m)
            + self.weights.congestion * (congested_m / self.ref_distance_m)
        )

    @property
    def reference_fitness(self):
        """
        Score of the free-flow reference route (its congestion is zero).
        Useful as a sanity anchor when reading results.
        """
        return self.weights.time + self.weights.distance

    def describe(self):
        w = self.weights
        return (
            f"mode={self.mode}  vehicle={self.vehicle.id}  "
            f"w_time={w.time:.2f} w_dist={w.distance:.2f} "
            f"w_cong={w.congestion:.2f}  |  T_ref={self.ref_time_s / 60:.1f} min  "
            f"D_ref={self.ref_distance_m / 1000:.2f} km"
        )
