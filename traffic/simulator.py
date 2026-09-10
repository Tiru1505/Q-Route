"""
Synthetic dynamic traffic for Hyderabad.

WHY SYNTHETIC
-------------
No open historical traffic time-series exists for any Indian city (see
results/dataset_reports/PHASE1_REPORT.md). Real Hyderabad congestion has to be
collected day by day via scripts/collect_tomtom_hyderabad.py. Meanwhile the
optimiser needs traffic to optimise against, and the benchmark needs scenarios
that are *identical* for every algorithm and repeatable on demand.

So this module generates traffic. Say so plainly in the report: the contribution
is the optimiser, not the data feed. What would be dishonest is training a
predictor on traffic we generated and reporting its accuracy as evidence about
the real world.

WHAT MAKES IT REALISTIC RATHER THAN RANDOM
------------------------------------------
Three properties, because random per-edge noise looks obviously fake on a map
and gives the router nothing meaningful to solve:

1. TEMPORAL   A diurnal profile with a morning and a sharper evening peak,
              matching the shape reported for Indian cities.
2. STRUCTURAL Arterials congest before residential streets. A road's
              susceptibility is set by its OSM class.
3. SPATIAL    Congestion spreads along corridors. We seed hotspots at real
              Hyderabad junctions and diffuse outward through the graph with
              distance decay — so jams form connected queues, not confetti.

CALIBRATION — STALE, DO NOT QUOTE
---------------------------------
These 12-hour totals were measured under the PREVIOUS hand-fitted diurnal
curve, which has since been replaced by one derived from real Indian junction
counts (see MEASURED_DIURNAL below):

    primary     median 16,589 PCU/12h   (p5 15,420  p95 16,972)
    secondary   median 16,628 PCU/12h
    trunk       median 16,512 PCU/12h
    motorway    median 14,380 PCU/12h

The new curve carries 28.7% more mean intensity across 07:00-19:00 (0.824
against 0.640), because the old formula treated the whole morning build-up as
nearly empty. The totals above are therefore understated by roughly 29%, and
Greenshields flow is not linear in congestion so the true shift is not exactly
that. They must be re-measured before being quoted anywhere.

They are also not currently reproducible: the note below claimed
scripts/run_traffic.py regenerates them and it does not — nothing in the
repository computes PCU/12h. Whoever re-measures should add that script rather
than restore a number no one can check.

The comparison they were made against still stands: the HMDA Comprehensive
Transportation Study observed 2,470-76,193 PCU/12h at three-arm junctions and
5,810-74,705 at four-arm junctions. A ~29% increase stays inside that range.

REPRODUCIBILITY
---------------
Every scenario takes a fixed seed. Same seed, same graph, same traffic —
byte for byte. That is a requirement for a fair benchmark, not a nicety.
"""
from collections import deque
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from traffic.congestion_model import CongestionModel

# How readily each road class congests, relative to its own capacity.
# Arterials carry through-traffic and choke first; residential lanes rarely jam.
CLASS_SUSCEPTIBILITY = {
    "motorway": 0.55, "motorway_link": 0.70,
    "trunk": 0.75, "trunk_link": 0.85,
    "primary": 1.00, "primary_link": 1.00,
    "secondary": 0.90, "secondary_link": 0.90,
    "tertiary": 0.70, "tertiary_link": 0.70,
    "unclassified": 0.45,
    "residential": 0.35,
    "living_street": 0.25,
    "service": 0.20,
    "road": 0.50,
}

# Roads we treat as instrumented. Emitting a row for all 741k edges would give
# a 6M-row file nobody can open; real networks only have sensors on arterials.
MONITORED_CLASSES = {
    "motorway", "motorway_link", "trunk", "trunk_link",
    "primary", "primary_link", "secondary", "secondary_link",
}

# Real Hyderabad choke points, used as hotspot seeds. [lat, lon]
HOTSPOTS = {
    "mehdipatnam":   [17.3950, 78.4360],
    "panjagutta":    [17.4256, 78.4500],
    "ameerpet":      [17.4374, 78.4487],
    "lb_nagar":      [17.3457, 78.5522],
    "uppal":         [17.4020, 78.5590],
    "kukatpally":    [17.4849, 78.4138],
    "jubilee_hills": [17.4239, 78.4138],
    "dilsukhnagar":  [17.3687, 78.5247],
    "secunderabad":  [17.4344, 78.5013],
    "charminar":     [17.3616, 78.4747],
}

INCIDENT_TYPES = ("accident", "breakdown", "waterlogging", "roadwork", "closure")


# Mean PCU per hour across 31 days at an Indian junction, normalised to its
# own peak. Regenerate with: python scripts/derive_diurnal_profile.py --emit
#
# This replaced two Gaussians whose parameters were chosen by hand and asserted
# to match "the shape Indian metros show". They did not. Measured against this
# series the old curve was off by 0.302 on average across the day, and wrong in
# ways that matter: it treated 06:00 as nearly empty (0.11) when the real
# morning build-up is already at 0.94, put the evening peak at 18:30 when it
# measures at 17:00, and understated overnight traffic six-fold. A simulator
# driven by the wrong daily shape jams at the wrong hours, and every route
# optimised against it inherits that error.
MEASURED_DIURNAL = (
    0.367, 0.358, 0.369, 0.403,    # 00:00-03:00
    0.531, 0.577, 0.942, 0.932,    # 04:00-07:00
    0.948, 0.811, 0.783, 0.658,    # 08:00-11:00
    0.663, 0.763, 0.762, 0.699,    # 12:00-15:00
    0.998, 1.000, 0.943, 0.727,    # 16:00-19:00
    0.700, 0.732, 0.377, 0.370,    # 20:00-23:00
)


# Mean vehicles per hour at the same junction, from the same 31 days. Kept
# beside the profile because a normalised curve cannot answer "how many", and
# an invented constant was previously standing in for this in the analytics
# response. One junction — a city-wide total this is not, and the API says so.
MEASURED_HOURLY_VEHICLES = (
    172, 169, 171, 189,    # 00:00-03:00
    391, 458, 697, 690,    # 04:00-07:00
    697, 540, 493, 419,    # 08:00-11:00
    424, 521, 530, 489,    # 12:00-15:00
    723, 724, 672, 494,    # 16:00-19:00
    470, 490, 172, 169,    # 20:00-23:00
)


def diurnal_factor(hour):
    """
    Traffic intensity 0..1 by hour of day, measured rather than assumed.

    Interpolates between hourly means so a fractional hour moves smoothly, and
    wraps at midnight — 23:30 sits between the 23:00 and 00:00 values rather
    than falling off the end of the table.

    WHAT THIS CARRIES: the SHAPE of an Indian traffic day. Not its magnitude.
    The series is one junction, so its absolute volumes say nothing about a
    six-lane arterial versus a residential lane; per-edge volume is scaled by
    road class elsewhere, and this is only the curve that scales.
    """
    h = float(hour) % 24.0
    lo = int(h)
    frac = h - lo
    return (MEASURED_DIURNAL[lo] * (1.0 - frac)
            + MEASURED_DIURNAL[(lo + 1) % 24] * frac)


@dataclass
class TrafficState:
    """A complete, reproducible description of the network at one instant."""

    scenario_id: str
    timestamp: pd.Timestamp
    seed: int
    congestion: dict = field(default_factory=dict)   # (u,v,k) -> 0..1
    closures: set = field(default_factory=set)       # (u,v,k)
    incidents: list = field(default_factory=list)
    description: str = ""

    def summary(self):
        vals = np.array(list(self.congestion.values())) if self.congestion else np.zeros(1)
        # "Loaded" means carrying meaningful traffic. Nearly every edge picks up
        # some background load, so a raw count of entries says nothing.
        return {
            "scenario": self.scenario_id,
            "timestamp": str(self.timestamp),
            "seed": self.seed,
            "edges_loaded": int((vals >= 0.05).sum()),
            "mean_congestion": round(float(vals.mean()), 4),
            "p95_congestion": round(float(np.percentile(vals, 95)), 4),
            "max_congestion": round(float(vals.max()), 4),
            "moderate_edges": int((vals >= 0.30).sum()),
            "heavy_edges": int((vals >= 0.50).sum()),
            "severe_edges": int((vals >= 0.70).sum()),
            "closures": len(self.closures),
            "incidents": len(self.incidents),
        }


class TrafficSimulator:
    """Generates the eight scenarios required by the project spec."""

    def __init__(self, G, model=None, seed=42):
        self.G = G
        self.model = model or CongestionModel()
        self.base_seed = seed
        self._node_cache = {}
        self._edges = None
        self._susc = None

    def _edge_index(self):
        """
        Cache the edge list and per-edge susceptibility once.

        The background pass touches all 741k edges on every scenario; doing that
        in a Python loop with a per-edge RNG call cost ~15 s. Vectorised over
        NumPy it is well under a second.
        """
        if self._edges is None:
            self._edges = [(u, v, k) for u, v, k in self.G.edges(keys=True)]
            self._susc = np.array(
                [self._susceptibility(self.G[u][v][k]) for u, v, k in self._edges],
                dtype=float,
            )
        return self._edges, self._susc

    # ------------------------------------------------------------ helpers
    def _nearest_node(self, lat, lon):
        key = (round(lat, 5), round(lon, 5))
        if key not in self._node_cache:
            import osmnx as ox
            self._node_cache[key] = ox.nearest_nodes(self.G, lon, lat)
        return self._node_cache[key]

    @staticmethod
    def _klass(data):
        h = data.get("highway")
        h = h[0] if isinstance(h, list) else h
        return str(h)

    def _susceptibility(self, data):
        return CLASS_SUSCEPTIBILITY.get(self._klass(data), 0.5)

    def _diffuse(self, seed_node, intensity, radius_hops, rng, decay=0.94,
                 max_edges=4000):
        """
        Spread congestion outward from a junction along the road network.

        Breadth-first, multiplying intensity by `decay` per hop, so a jam forms
        a connected queue that fades with distance — which is how congestion
        actually propagates, and what makes the map look right.

        Two sizing notes learned the hard way:
          * Simplified OSM edges are only 50-200 m, so a "9 hop" blob covers
            well under a kilometre. Real corridor jams need tens of hops.
          * BFS fans out exponentially, so `max_edges` — not the hop radius —
            is what actually bounds the cost and keeps blob sizes comparable
            between scenarios.
        """
        out = {}
        queue = deque([(seed_node, 0)])
        seen = {seed_node}

        while queue and len(out) < max_edges:
            node, depth = queue.popleft()
            if depth >= radius_hops:
                continue
            level = intensity * (decay ** depth)
            if level < 0.04:
                continue

            for nbr in self.G.successors(node):
                for k, data in self.G[node][nbr].items():
                    # A hotspot is a queue that has physically formed, so road
                    # class matters less here than it does for background load —
                    # a blocked side street jams just like a blocked arterial.
                    # Blending toward 1.0 keeps class ordering without crushing
                    # a spike down to nothing on minor roads.
                    susceptibility = 0.5 + 0.5 * self._susceptibility(data)
                    edge_level = level * susceptibility
                    # jitter keeps a corridor from looking uniformly painted
                    edge_level *= rng.uniform(0.85, 1.15)
                    key = (node, nbr, k)
                    out[key] = max(out.get(key, 0.0), min(edge_level, 0.98))
                if nbr not in seen:
                    seen.add(nbr)
                    queue.append((nbr, depth + 1))
        return out

    def _background(self, hour, rng, scale=1.0):
        """Network-wide baseline congestion from the diurnal profile."""
        edges, susc = self._edge_index()
        intensity = diurnal_factor(hour) * scale
        vals = intensity * susc * rng.uniform(0.7, 1.25, size=len(susc))
        np.minimum(vals, 0.95, out=vals)
        # Below 5% is free flow for practical purposes; dropping it keeps the
        # state dict meaningful instead of listing every edge in the city.
        keep = vals >= 0.05
        return {edges[i]: float(vals[i]) for i in np.flatnonzero(keep)}

    @staticmethod
    def _merge(*maps):
        """Combine congestion maps, keeping the worst value per edge."""
        merged = {}
        for m in maps:
            for key, val in m.items():
                if val > merged.get(key, 0.0):
                    merged[key] = val
        return merged

    # ---------------------------------------------------------- scenarios
    def generate(self, scenario_id, seed=None, hour=None):
        """Build one TrafficState. Same (scenario_id, seed) -> same output."""
        if scenario_id not in SCENARIOS:
            raise ValueError(f"Unknown scenario '{scenario_id}'. "
                             f"Choose from {list(SCENARIOS)}")
        spec = SCENARIOS[scenario_id]
        seed = self.base_seed if seed is None else seed
        rng = np.random.default_rng(seed)
        hour = spec["hour"] if hour is None else hour

        congestion = self._background(hour, rng, scale=spec["background_scale"])
        closures, incidents = set(), []

        # hotspots
        chosen = spec["hotspots"]
        if chosen == "random":
            chosen = list(rng.choice(list(HOTSPOTS), size=spec["n_hotspots"], replace=False))
        for name in chosen:
            lat, lon = HOTSPOTS[name]
            node = self._nearest_node(lat, lon)
            blob = self._diffuse(
                node,
                intensity=spec["hotspot_intensity"] * rng.uniform(0.9, 1.1),
                radius_hops=spec["hotspot_radius"],
                rng=rng,
                max_edges=spec["hotspot_edges"],
            )
            congestion = self._merge(congestion, blob)

        # incidents (and the closures some of them cause)
        for name in spec["incidents"]:
            lat, lon = HOTSPOTS[name]
            node = self._nearest_node(lat, lon)
            itype = str(rng.choice(INCIDENT_TYPES[:3]))
            # An incident queues back hard but over a shorter reach than a
            # general peak-hour jam: high intensity, faster decay, fewer edges.
            blob = self._diffuse(node, intensity=0.96, radius_hops=28, rng=rng,
                                 decay=0.90, max_edges=1800)
            congestion = self._merge(congestion, blob)
            incidents.append({
                "type": itype, "location": name, "lat": lat, "lon": lon,
                "severity": "severe", "edges_affected": len(blob),
            })

        for name in spec["closures"]:
            lat, lon = HOTSPOTS[name]
            node = self._nearest_node(lat, lon)
            closed = self._close_around(node, rng, n_edges=spec["closure_edges"])
            closures |= closed
            incidents.append({
                "type": "closure", "location": name, "lat": lat, "lon": lon,
                "severity": "severe", "edges_affected": len(closed),
            })

        timestamp = pd.Timestamp("2026-08-27").normalize() + pd.Timedelta(hours=hour)
        return TrafficState(
            scenario_id=scenario_id, timestamp=timestamp, seed=seed,
            congestion=congestion, closures=closures, incidents=incidents,
            description=spec["description"],
        )

    def _close_around(self, node, rng, n_edges=6):
        """
        Close a short run of road at a junction.

        Deliberately small: closing a whole neighbourhood can disconnect the
        graph and make the instance unsolvable, which is not a useful test.
        """
        closed = set()
        for nbr in list(self.G.successors(node)):
            for k in self.G[node][nbr]:
                closed.add((node, nbr, k))
                if len(closed) >= n_edges:
                    return closed
        return closed

    # ------------------------------------------------- targeted disruption
    def congest_route(self, state, nodes, level=0.92, fraction=0.4, seed=None):
        """
        Spike congestion on a stretch of an EXISTING route.

        Fixed hotspots sit where real Hyderabad jams form, which is correct for
        scenario realism but means they often miss whichever route the optimiser
        happened to pick. Phase 9's rerouting demo needs the opposite: congestion
        that is guaranteed to hit the active route, so the system has a genuine
        reason to reroute.

        Congests the middle `fraction` of the route, since blocking the very
        start or end leaves no alternative to find.

        Returns a NEW TrafficState; the input is not modified.
        """
        import copy

        rng = np.random.default_rng(self.base_seed if seed is None else seed)
        n = len(nodes)
        if n < 4:
            return state

        lo = int(n * (0.5 - fraction / 2))
        hi = int(n * (0.5 + fraction / 2))
        segment = nodes[lo:hi]

        congestion = dict(state.congestion)
        affected = 0
        for u, v in zip(segment, segment[1:]):
            if not self.G.has_edge(u, v):
                continue
            for k in self.G[u][v]:
                congestion[(u, v, k)] = min(level * rng.uniform(0.92, 1.0), 0.98)
                affected += 1

        new_state = copy.copy(state)
        new_state.congestion = congestion
        new_state.incidents = list(state.incidents) + [{
            "type": "sudden_congestion", "location": "active route",
            "lat": float(self.G.nodes[segment[len(segment) // 2]]["y"]),
            "lon": float(self.G.nodes[segment[len(segment) // 2]]["x"]),
            "severity": "severe", "edges_affected": affected,
        }]
        return new_state

    # -------------------------------------------------------------- apply
    def apply(self, state):
        """Write a TrafficState onto the graph. Returns edges touched."""
        touched = self.model.apply(self.G, state.congestion, reset_missing=True)
        for u, v, k, data in self.G.edges(keys=True, data=True):
            data["road_status"] = "closed" if (u, v, k) in state.closures else "open"
        return touched

    # ------------------------------------------------------------ dataset
    def to_dataframe(self, state, monitored_only=True):
        """
        The tabular synthetic dataset, one row per monitored road segment.

        Columns are exactly those named in the project spec:
        scenario_id, timestamp, road_id, traffic_density, vehicle_count,
        average_speed, congestion_level, road_status, incident_type
        """
        incident_nodes = {}
        for inc in state.incidents:
            node = self._nearest_node(inc["lat"], inc["lon"])
            incident_nodes[node] = inc["type"]

        rows = []
        for u, v, k, data in self.G.edges(keys=True, data=True):
            if monitored_only and self._klass(data) not in MONITORED_CLASSES:
                continue

            c = state.congestion.get((u, v, k), 0.0)
            closed = (u, v, k) in state.closures
            rows.append({
                "scenario_id": state.scenario_id,
                "timestamp": state.timestamp,
                "road_id": f"{u}_{v}_{k}",
                "u": u, "v": v, "key": k,
                "road_type": self._klass(data),
                "length_m": round(float(data.get("length_m", 0.0) or 0.0), 1),
                "traffic_density": round(self.model.density_for_congestion(data, c), 2),
                "vehicle_count": self.model.vehicles_for_congestion(data, c),
                "average_speed": round(self.model.speed(data, c), 1),
                "free_flow_speed": round(float(data.get("free_flow_speed_kph", 0) or 0), 1),
                "congestion": round(c, 4),
                "congestion_level": self.model.level(c),
                "flow_pcu_h": round(self.model.flow_pcu_h(data, c), 1),
                "road_status": "closed" if closed else "open",
                "incident_type": incident_nodes.get(u, ""),
            })
        return pd.DataFrame(rows)


# The eight scenarios required by the spec.
SCENARIOS = {
    "normal": dict(
        description="Mid-afternoon, light background traffic and no incidents.",
        hour=14.0, background_scale=0.55, hotspots=[], n_hotspots=0,
        hotspot_intensity=0.0, hotspot_radius=0, hotspot_edges=0,
        incidents=[], closures=[], closure_edges=0),

    "peak_hour": dict(
        description="Evening peak. Heavy background load, all major junctions busy.",
        hour=18.5, background_scale=0.82,
        hotspots=["mehdipatnam", "panjagutta", "ameerpet", "kukatpally", "lb_nagar"],
        n_hotspots=5, hotspot_intensity=0.80, hotspot_radius=30, hotspot_edges=3000,
        incidents=[], closures=[], closure_edges=0),

    "heavy_congestion": dict(
        description="Sustained network-wide congestion across every corridor.",
        hour=18.5, background_scale=0.95, hotspots=list(HOTSPOTS), n_hotspots=10,
        hotspot_intensity=0.88, hotspot_radius=32, hotspot_edges=3500,
        incidents=[], closures=[], closure_edges=0),

    "sudden_congestion": dict(
        description="Normal traffic, then one corridor spikes without warning.",
        hour=15.0, background_scale=0.55, hotspots=["mehdipatnam"], n_hotspots=1,
        hotspot_intensity=0.96, hotspot_radius=40, hotspot_edges=5000,
        incidents=[], closures=[], closure_edges=0),

    "accident": dict(
        description="Accident at a major junction; severe congestion queues back.",
        hour=17.5, background_scale=0.75, hotspots=["panjagutta"], n_hotspots=1,
        hotspot_intensity=0.60, hotspot_radius=20, hotspot_edges=1500,
        incidents=["mehdipatnam"], closures=[], closure_edges=0),

    "road_closure": dict(
        description="Roadworks close a carriageway; traffic must detour.",
        hour=16.0, background_scale=0.65, hotspots=["ameerpet"], n_hotspots=1,
        hotspot_intensity=0.62, hotspot_radius=22, hotspot_edges=1800,
        incidents=[], closures=["panjagutta"], closure_edges=8),

    "multiple_congested": dict(
        description="Several unrelated corridors congested at once.",
        hour=18.0, background_scale=0.85,
        hotspots=["mehdipatnam", "uppal", "kukatpally", "dilsukhnagar"], n_hotspots=4,
        hotspot_intensity=0.86, hotspot_radius=30, hotspot_edges=2800,
        incidents=["lb_nagar"], closures=[], closure_edges=0),

    "clearing": dict(
        description="Late evening; the peak has passed and queues are dissipating.",
        hour=21.0, background_scale=0.45, hotspots=["panjagutta"], n_hotspots=1,
        hotspot_intensity=0.38, hotspot_radius=16, hotspot_edges=900,
        incidents=[], closures=[], closure_edges=0),
}

SCENARIO_IDS = list(SCENARIOS)
