"""
The congestion model — turns traffic on a road into a congestion score, a
current speed, and a current travel time.

THE PHYSICS (and why it is defensible)
--------------------------------------
We use the Greenshields fundamental diagram, the standard first-order model in
transport engineering. It says speed falls linearly as density rises:

    v = vf * (1 - k / kj)

    v  = current mean speed        (km/h)
    vf = free-flow speed           (km/h)   -- from the OSM graph
    k  = traffic density           (PCU/km)
    kj = jam density               (PCU/km) -- density at which traffic stops

Rearranging gives our congestion score directly:

    congestion = 1 - v / vf = k / kj          in [0, 1]

    0.0 = free flow      1.0 = fully stopped

That definition is not invented here. Tsuboi & Yoshikawa (2019), the Ahmedabad
study in our dataset registry, define congestion as exactly the ratio of mean
speed to free speed. Our TomTom collector derives its congestion_ratio the same
way. So the simulated and the real signal mean the same thing — which is what
lets a model trained on one transfer to the other.

WHERE kj COMES FROM (no new assumptions)
----------------------------------------
Greenshields also fixes the relationship between capacity and jam density.
Flow is q = k*v, which is maximised at k = kj/2, giving q_max = vf*kj/4.
Both q_max (capacity_pcu_h) and vf are already attributes on every edge from
Phase 2, so:

    kj = 4 * capacity_pcu_h / vf

Nothing is guessed. For a two-lane primary road (capacity 3000 PCU/h, vf 45
km/h) this gives kj = 267 PCU/km, i.e. ~133 PCU/km/lane — at the high end of
the usual 100-140 range, which is right for Indian mixed traffic where
two-wheelers pack into gaps a car could not use.

UNITS: PCU
----------
Everything is in Passenger Car Units, not raw vehicle counts. This is the
correct choice for heterogeneous Indian traffic and follows the Ahmedabad study.
A car is 1.0 PCU by definition; a two-wheeler occupies far less road space.
"""
import math
from dataclasses import dataclass

# Passenger Car Unit equivalents (IRC:106-1990 urban road values).
# Used to convert a mixed vehicle count into PCU.
PCU_FACTORS = {
    "two_wheeler": 0.5,
    "car": 1.0,
    "auto_rickshaw": 0.8,
    "bus": 3.0,
    "truck": 3.0,
    "bicycle": 0.4,
}

# Typical Hyderabad urban fleet mix. Two-wheeler dominance is the defining
# feature of Indian city traffic and the main reason PCU matters.
DEFAULT_FLEET_MIX = {
    "two_wheeler": 0.62,
    "car": 0.22,
    "auto_rickshaw": 0.10,
    "bus": 0.02,
    "truck": 0.02,
    "bicycle": 0.02,
}

# Speed never drops to zero, or travel time would be infinite and the router
# would refuse a jammed but passable road. 5 km/h is roughly walking pace,
# which is what a severe Hyderabad jam actually looks like.
MIN_SPEED_KPH = 5.0

# Congestion is capped just below 1.0 for the same reason.
MAX_CONGESTION = 0.98


def fleet_pcu_per_vehicle(mix=None):
    """Average PCU of one vehicle drawn from the fleet mix."""
    mix = mix or DEFAULT_FLEET_MIX
    return sum(share * PCU_FACTORS[v] for v, share in mix.items())


@dataclass
class CongestionModel:
    """Greenshields congestion model. Stateless — safe to share across threads."""

    min_speed_kph: float = MIN_SPEED_KPH
    max_congestion: float = MAX_CONGESTION
    fleet_mix: dict = None

    def __post_init__(self):
        self.fleet_mix = self.fleet_mix or DEFAULT_FLEET_MIX
        self.pcu_per_vehicle = fleet_pcu_per_vehicle(self.fleet_mix)

    # ------------------------------------------------------------- physics
    def jam_density(self, data):
        """kj = 4 * capacity / vf   (PCU/km), derived from Greenshields."""
        vf = float(data.get("free_flow_speed_kph", 25.0) or 25.0)
        capacity = float(data.get("capacity_pcu_h", 1600.0) or 1600.0)
        if vf <= 0:
            return 1.0
        return max(4.0 * capacity / vf, 1.0)

    def congestion_from_density(self, data, density_pcu_km):
        """congestion = k / kj, clipped to [0, max]."""
        kj = self.jam_density(data)
        return min(max(density_pcu_km / kj, 0.0), self.max_congestion)

    def congestion_from_vehicle_count(self, data, vehicle_count):
        """
        Convert a raw mixed-vehicle count on the segment into congestion.
        This is the path the YOLO module would feed if it is ever built.
        """
        length_km = max(float(data.get("length_m", 0.0) or 0.0) / 1000.0, 1e-6)
        density_pcu_km = (vehicle_count * self.pcu_per_vehicle) / length_km
        return self.congestion_from_density(data, density_pcu_km)

    def density_for_congestion(self, data, congestion):
        """Inverse: the density that produces a target congestion level."""
        return min(max(congestion, 0.0), self.max_congestion) * self.jam_density(data)

    def vehicles_for_congestion(self, data, congestion):
        """Inverse: a plausible vehicle count for a target congestion level."""
        length_km = float(data.get("length_m", 0.0) or 0.0) / 1000.0
        density = self.density_for_congestion(data, congestion)
        return int(round(density * length_km / self.pcu_per_vehicle))

    def speed(self, data, congestion):
        """v = vf * (1 - congestion), floored so travel time stays finite."""
        vf = float(data.get("free_flow_speed_kph", 25.0) or 25.0)
        return max(vf * (1.0 - congestion), self.min_speed_kph)

    def travel_time_s(self, data, congestion):
        length_m = float(data.get("length_m", 0.0) or 0.0)
        v_kph = self.speed(data, congestion)
        return length_m / (v_kph * 1000.0 / 3600.0) if v_kph > 0 else math.inf

    def flow_pcu_h(self, data, congestion):
        """q = k*v — reported for the fundamental-diagram plots."""
        k = self.density_for_congestion(data, congestion)
        return k * self.speed(data, congestion)

    # -------------------------------------------------------------- apply
    def apply_edge(self, data, congestion):
        """Write the derived state onto one edge, in place."""
        congestion = min(max(float(congestion), 0.0), self.max_congestion)
        data["congestion"] = congestion
        data["current_speed_kph"] = self.speed(data, congestion)
        data["current_time_s"] = self.travel_time_s(data, congestion)
        return data

    def apply(self, G, congestion_by_edge, reset_missing=True):
        """
        Apply a {(u, v, key): congestion} mapping to the graph.

        With reset_missing=True every edge not named in the mapping returns to
        free flow, so a scenario is a complete description of the network state
        rather than a diff. That is what makes runs reproducible.
        """
        touched = 0
        for u, v, k, data in G.edges(keys=True, data=True):
            c = congestion_by_edge.get((u, v, k))
            if c is None:
                if reset_missing:
                    self.apply_edge(data, 0.0)
            else:
                self.apply_edge(data, c)
                touched += 1
        return touched

    # ------------------------------------------------------------ reading
    @staticmethod
    def level(congestion):
        """The four bands used by the map legend and the alert engine."""
        if congestion < 0.30:
            return "low"
        if congestion < 0.50:
            return "moderate"
        if congestion < 0.70:
            return "heavy"
        return "severe"

    def describe_edge(self, data):
        c = float(data.get("congestion", 0.0) or 0.0)
        return {
            "congestion": round(c, 4),
            "level": self.level(c),
            "speed_kph": round(float(data.get("current_speed_kph", 0.0) or 0.0), 1),
            "free_flow_kph": round(float(data.get("free_flow_speed_kph", 0.0) or 0.0), 1),
            "density_pcu_km": round(self.density_for_congestion(data, c), 1),
            "jam_density_pcu_km": round(self.jam_density(data), 1),
            "flow_pcu_h": round(self.flow_pcu_h(data, c), 1),
            "delay_s": round(
                float(data.get("current_time_s", 0.0) or 0.0)
                - float(data.get("free_flow_time_s", 0.0) or 0.0), 1),
        }
