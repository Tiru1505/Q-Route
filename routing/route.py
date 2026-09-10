"""
The Route object — the common currency of the whole system.

Dijkstra, QPSO, PSO and GA all return one of these, the benchmark compares them,
the validator checks them, and the API serialises them. Keeping one shape means
no algorithm can quietly report its results differently from another.
"""
import math
from dataclasses import dataclass, field

from graph.edge_weights import is_closed


def _sq(a, b):
    """Squared distance between two (lat, lon) points — ordering only."""
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


@dataclass
class Route:
    nodes: list                       # ordered OSM node ids, source .. target
    algorithm: str = "unknown"

    # raw totals, in real units
    time_s: float = 0.0
    distance_m: float = 0.0
    congested_m: float = 0.0

    fitness: float = math.inf         # normalised objective value; lower is better
    runtime_ms: float = 0.0
    iterations: int = 0               # 0 for exact algorithms
    valid: bool = True
    violations: list = field(default_factory=list)
    convergence: list = field(default_factory=list)   # best fitness per iteration

    # ------------------------------------------------------------ readable
    @property
    def distance_km(self):
        return self.distance_m / 1000.0

    @property
    def time_min(self):
        return self.time_s / 60.0

    @property
    def mean_congestion(self):
        """Length-weighted mean congestion over the route, 0..1."""
        return self.congested_m / self.distance_m if self.distance_m > 0 else 0.0

    @property
    def avg_speed_kph(self):
        return (self.distance_m / 1000.0) / (self.time_s / 3600.0) if self.time_s > 0 else 0.0

    @property
    def hops(self):
        return max(len(self.nodes) - 1, 0)

    def edge_pairs(self):
        return list(zip(self.nodes, self.nodes[1:]))

    # ------------------------------------------------------------- output
    def coordinates(self, G):
        """
        [[lat, lon], ...] for the map, FOLLOWING THE ROAD.

        Joining node positions with straight lines is wrong and it shows: OSMnx
        simplifies a graph by collapsing a curved road between two junctions
        into one edge, storing the bend in the edge's `geometry`. About a third
        of Hyderabad's edges carry such geometry, averaging ~4.6 points each.
        Ignoring it makes the drawn route cut corners and sit visibly off the
        road — overlapping buildings on the map instead of tracing the street.

        So we walk the edge geometry where it exists and fall back to the node
        positions where it does not.
        """
        if len(self.nodes) < 2:
            return [[float(G.nodes[n]["y"]), float(G.nodes[n]["x"])] for n in self.nodes]

        out = []
        for u, v in zip(self.nodes, self.nodes[1:]):
            pu = (float(G.nodes[u]["y"]), float(G.nodes[u]["x"]))
            pv = (float(G.nodes[v]["y"]), float(G.nodes[v]["x"]))

            geom = None
            if G.has_edge(u, v):
                # Parallel edges may differ; take the one actually routed on,
                # i.e. the cheapest by length, matching best_edge().
                data = min(G[u][v].values(),
                           key=lambda d: float(d.get("length_m", d.get("length", 0)) or 0))
                geom = data.get("geometry")

            if geom is not None and hasattr(geom, "coords"):
                # Shapely stores (lon, lat); Leaflet wants (lat, lon).
                pts = [(y, x) for x, y in geom.coords]
                # Geometry is stored in the underlying way's direction, which is
                # not always u -> v. Flip it when it starts nearer to v.
                if pts and (_sq(pts[0], pv) < _sq(pts[0], pu)):
                    pts.reverse()
            else:
                pts = [pu, pv]

            if not out:
                out.append([pts[0][0], pts[0][1]])
            for p in pts[1:]:
                out.append([p[0], p[1]])

        return out

    def to_dict(self, G=None):
        d = {
            "algorithm": self.algorithm,
            "hops": self.hops,
            "distance_km": round(self.distance_km, 3),
            "time_min": round(self.time_min, 2),
            "mean_congestion": round(self.mean_congestion, 4),
            "avg_speed_kph": round(self.avg_speed_kph, 1),
            "fitness": round(self.fitness, 6),
            "runtime_ms": round(self.runtime_ms, 2),
            "iterations": self.iterations,
            "valid": self.valid,
            "violations": self.violations,
        }
        if G is not None:
            d["path"] = self.coordinates(G)
        return d

    def summary(self):
        flag = "" if self.valid else "  [INVALID]"
        return (
            f"{self.algorithm:<18} {self.distance_km:6.2f} km  {self.time_min:6.1f} min  "
            f"cong {self.mean_congestion * 100:5.1f}%  fitness {self.fitness:.5f}  "
            f"{self.runtime_ms:7.1f} ms{flag}"
        )


def evaluate_route(G, nodes, cost_model, algorithm="unknown", **kwargs):
    """
    Measure a node sequence against the cost model and package it as a Route.

    This is the ONLY place route totals are computed. Every algorithm scores its
    candidates through here, so no algorithm can accidentally use a different
    objective from the others.
    """
    time_s = distance_m = congested_m = 0.0
    violations = []

    for u, v in zip(nodes, nodes[1:]):
        if not G.has_edge(u, v):
            violations.append(f"no edge {u} -> {v}")
            continue
        data, _cost = cost_model.best_edge(G, u, v)
        if data is None or is_closed(data):
            # best_edge skips anything costed at infinity, so this covers a
            # closed road and one this vehicle may not use alike.
            violations.append(f"no usable road {u} -> {v}")
            continue
        t, d, c = cost_model.components(data)
        time_s += t
        distance_m += d
        congested_m += c

    route = Route(
        nodes=list(nodes),
        algorithm=algorithm,
        time_s=time_s,
        distance_m=distance_m,
        congested_m=congested_m,
        fitness=cost_model.fitness(time_s, distance_m, congested_m) if not violations else math.inf,
        valid=not violations,
        violations=violations,
        **kwargs,
    )
    return route
