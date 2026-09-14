"""
Turning a continuous vector into a real road route.

THE PROBLEM
-----------
QPSO searches a continuous space: a particle is a list of decimal numbers, and
the quantum update nudges those numbers around. But a route is discrete — an
ordered list of road segments. The two do not obviously fit together, and how
you bridge them decides whether the whole project works.

WHAT DOESN'T WORK
-----------------
The obvious encoding is "particle = sequence of node ids". It fails here:
286,603 nodes means an enormous search space, almost every random vector
decodes to a disconnected mess, and you spend all your time repairing garbage
instead of searching.

WHAT WE DO INSTEAD: WAYPOINT ENCODING
-------------------------------------
A particle proposes a few WAYPOINTS, not a whole route:

    particle = [0.31, 0.78, 0.12, 0.55, 0.60]     5 numbers in [0, 1]

Read it as a driver's intent: "at the first third of the journey swing left, at
the halfway point cut right, ..." Each number picks how far to one side the
route should bend at that stage of the trip.

The route is then the cheapest path linking them:

    source -> w1 -> w2 -> w3 -> w4 -> w5 -> target

Because each leg is itself a shortest path, EVERY particle decodes to a
connected, valid route. There is nothing to repair. That is the main reason to
prefer this encoding.

It also keeps the search space small — 5 dimensions instead of 286,603 — which
is what makes QPSO's quantum update meaningful rather than lost in noise.

HOW THE NUMBERS BECOME PLACES
-----------------------------
1. Cut the map down to a CORRIDOR: an ellipse with the source and target as its
   two focal points. Any sensible route lives inside it; the rest of the city is
   irrelevant and only slows the search.
2. Measure each corridor node on two axes:
      progress  — how far along the source->target direction it lies (0 to 1)
      offset    — how far to the left or right of the straight line it sits
3. Slice the corridor into bands by progress. Waypoint i is chosen from band i.
4. Within a band, the particle's number picks the node by offset:
   0.0 = far left, 0.5 = on the straight line, 1.0 = far right.

KNOWN LIMITATION — READ BEFORE QUOTING RESULTS
----------------------------------------------
This encoding restricts the search space. A route can only be built from paths
between sampled band candidates, so routes that need a waypoint we did not
sample are unreachable — no matter how well the optimiser searches.

Measured on Hitec City -> Charminar, mean optimality gap vs Dijkstra:

    free flow    +0.17%   (reaches the proven optimum in 93% of trials)
    peak_hour    +9.8%    (never reaches it)

Under congestion the optimum is a specific detour, and the discretised
waypoint grid cannot express it exactly. This is a plateau, not a tuning
problem — it was confirmed by sweeping the parameters:

    5 waypoints / 60 candidates -> 10.18%      9 / 40 -> 10.38%
    7 waypoints / 45 candidates ->  9.80%      7 / 80 -> 11.51%

Adding waypoints or candidates does not close it; it only costs setup time.

Why this is still sound:
  * QPSO, PSO and GA all share this decoder, so the metaheuristic comparison
    — the actual experiment — is unaffected.
  * Dijkstra remains the reference for how good a route could have been, and
    the gap is reported rather than hidden.
  * For the constrained problem (a hard congestion budget) Dijkstra cannot
    produce a feasible route at all, so an encoding that yields good feasible
    routes is what matters there.

State the gap in the report. Do not present QPSO as matching Dijkstra under
congestion, because it does not.

SPEED
-----
Decoding needs a shortest path per leg. Running Dijkstra fresh every time would
make a full QPSO run take minutes. Instead we precompute one shortest-path tree
from the source and from each candidate waypoint, once per problem instance,
each bounded to stop as soon as it has settled the next band.

Setup costs roughly 40 s on a free-flow network and 85 s under heavy
congestion (congested costs make each tree explore further). That is paid ONCE
per problem instance and reused by every algorithm and every trial, so in a
30-trial benchmark it is negligible. After setup, decoding a route is
pointer-walking — microseconds rather than milliseconds.
"""
import heapq
import math

import numpy as np

EARTH_R = 6371000.0


def _local_xy(G, nodes, origin_lat, origin_lon):
    """
    Project lat/lon to local metres (equirectangular).

    Accurate enough over a 60 km city and far cheaper than a proper projection,
    and we only ever use it for relative geometry.
    """
    lat = np.array([float(G.nodes[n]["y"]) for n in nodes])
    lon = np.array([float(G.nodes[n]["x"]) for n in nodes])
    x = np.radians(lon - origin_lon) * EARTH_R * math.cos(math.radians(origin_lat))
    y = np.radians(lat - origin_lat) * EARTH_R
    return x, y


def extract_corridor(G, source, target, slack=0.22, max_nodes=25000):
    """
    Nodes that could plausibly appear on a sensible route.

    An ellipse with the endpoints as foci: keep node n when

        dist(source, n) + dist(n, target) <= (1 + slack) * dist(source, target)

    slack controls how far the search may wander from the straight line.
    Measured: 0.22 gives the best results here. Widening it to 0.28 sounds
    safer but is worse — the node cap then truncates the ellipse, thinning
    candidate coverage exactly where the optimal route runs, and the optimality
    gap rose from 0.00% to 1.73%. Tighter and denser beats wider and sparser.

    Returns (node_list, progress, offset) where progress and offset are the two
    coordinates described in the module docstring.
    """
    nodes = list(G.nodes)
    s_lat, s_lon = float(G.nodes[source]["y"]), float(G.nodes[source]["x"])
    t_lat, t_lon = float(G.nodes[target]["y"]), float(G.nodes[target]["x"])

    x, y = _local_xy(G, nodes, s_lat, s_lon)
    tx = math.radians(t_lon - s_lon) * EARTH_R * math.cos(math.radians(s_lat))
    ty = math.radians(t_lat - s_lat) * EARTH_R

    d_total = math.hypot(tx, ty)
    if d_total < 1.0:
        raise ValueError("Source and target are effectively the same point.")

    d_from_source = np.hypot(x, y)
    d_to_target = np.hypot(x - tx, y - ty)
    inside = (d_from_source + d_to_target) <= (1.0 + slack) * d_total

    idx = np.flatnonzero(inside)
    if len(idx) > max_nodes:
        # Keep the ones closest to the straight line — a tighter ellipse.
        excess = (d_from_source + d_to_target)[idx]
        idx = idx[np.argsort(excess)[:max_nodes]]

    # progress: how far along the source->target axis (0..1)
    # offset:   signed perpendicular distance, normalised by the half-width
    ux, uy = tx / d_total, ty / d_total
    progress = (x[idx] * ux + y[idx] * uy) / d_total
    offset = x[idx] * (-uy) + y[idx] * ux

    corridor = [nodes[i] for i in idx]
    return corridor, progress, offset


class WaypointDecoder:
    """
    Converts particle vectors to routes, and back-fills the machinery that
    makes it fast.

    One decoder is built per problem instance (source, target, traffic state).
    Every algorithm that uses this encoding — QPSO, PSO, GA — shares one, so
    they search exactly the same space.
    """

    MAJOR_CLASSES = {
        "motorway", "motorway_link", "trunk", "trunk_link",
        "primary", "primary_link", "secondary", "secondary_link", "tertiary",
    }

    def __init__(self, G, source, target, cost_model, n_waypoints=5,
                 candidates_per_band=60, slack=0.30, major_only=True,
                 verbose=False):
        self.G = G
        self.source = source
        self.target = target
        self.cost_model = cost_model
        self.n_waypoints = n_waypoints
        self.dimensions = n_waypoints
        self._path_cache = {}
        self.decode_calls = 0

        corridor, progress, offset = extract_corridor(G, source, target, slack)
        self._major_cache = {}
        self.corridor = set(corridor)
        self.corridor_size = len(corridor)

        # Band i holds the candidates for waypoint i, taken from a slice of the
        # journey. Bands are evenly spaced strictly between the endpoints.
        self.bands = []
        for i in range(n_waypoints):
            centre = (i + 1) / (n_waypoints + 1)
            half = 0.5 / (n_waypoints + 1)
            in_band = np.flatnonzero(
                (progress >= centre - half) & (progress <= centre + half)
            )
            if len(in_band) == 0:
                self.bands.append([source])       # degenerate; harmless
                continue

            # Prefer junctions on significant roads.
            #
            # Measured: sampling candidates by pure geometry, only 1 of 120
            # sat on the congested optimal route, and QPSO stalled ~16% above
            # optimum. Restricting to major-road junctions and raising the
            # count to 60 lifts that to 8 of 300 — roughly 1.6 per band, which
            # is what QPSO needs to be able to assemble a good path at all.
            # It is also how a person gives directions: via named junctions,
            # not via arbitrary points in a residential grid.
            if major_only:
                major = [j for j in in_band if self._is_major(corridor[j])]
                if len(major) >= 4:                # keep geometry if too few
                    in_band = np.array(major)

            # Sort by lateral offset so the particle's number maps to
            # "how far left/right", then thin to a spread of candidates.
            in_band = in_band[np.argsort(offset[in_band])]
            if len(in_band) > candidates_per_band:
                pick = np.linspace(0, len(in_band) - 1, candidates_per_band).astype(int)
                in_band = in_band[pick]
            self.bands.append([corridor[j] for j in in_band])

        # One shortest-path tree per possible leg start, built once; after this
        # every decode is pointer-walking rather than searching.
        #
        # Crucially each tree is given the ONLY nodes it will ever be asked
        # about — the next band's candidates — and stops as soon as it has
        # settled them all. Without that bound each tree explores the whole
        # 40k-node corridor and setup takes ~44 s instead of a couple of
        # seconds. A leg only ever runs between consecutive bands, so nothing
        # is lost.
        self.trees = {}
        legs = [(source, self.bands[0])]
        for i in range(n_waypoints - 1):
            legs.extend((node, self.bands[i + 1]) for node in self.bands[i])
        legs.extend((node, [target]) for node in self.bands[-1])

        for root, targets in legs:
            if root not in self.trees:
                self.trees[root] = self._shortest_path_tree(root, set(targets))

        if verbose:
            sizes = [len(b) for b in self.bands]
            print(f"[encoding] corridor {self.corridor_size:,} nodes | "
                  f"{n_waypoints} waypoints | candidates/band {sizes} | "
                  f"{len(self.trees)} trees")

    # ------------------------------------------------------------ internals
    def _is_major(self, node):
        """True if any road meeting at this junction is a significant one."""
        if node not in self._major_cache:
            hit = False
            for _u, _v, d in self.G.edges(node, data=True):
                h = d.get("highway")
                h = h[0] if isinstance(h, list) else h
                if str(h) in self.MAJOR_CLASSES:
                    hit = True
                    break
            self._major_cache[node] = hit
        return self._major_cache[node]

    def _shortest_path_tree(self, root, targets=None):
        """
        Dijkstra from `root`, restricted to the corridor. Returns the
        predecessor map, which is all we need to reconstruct any path.

        `targets` bounds the work: once every target is settled their distances
        are final (all costs are non-negative), so the search can stop.
        """
        G, cm, corridor = self.G, self.cost_model, self.corridor
        dist = {root: 0.0}
        prev = {}
        heap = [(0.0, root)]
        settled = set()
        remaining = set(targets) - {root} if targets else None

        while heap:
            d, node = heapq.heappop(heap)
            if node in settled:
                continue
            settled.add(node)

            if remaining is not None:
                remaining.discard(node)
                if not remaining:
                    break

            for nbr in G.successors(node):
                if nbr not in corridor or nbr in settled:
                    continue
                _data, step = cm.best_edge(G, node, nbr)
                if not math.isfinite(step):
                    continue
                nd = d + step
                if nd < dist.get(nbr, math.inf):
                    dist[nbr] = nd
                    prev[nbr] = node
                    heapq.heappush(heap, (nd, nbr))
        return prev

    def _leg(self, a, b):
        """Node list from a to b using the precomputed tree. None if no path."""
        if a == b:
            return [a]
        key = (a, b)
        if key in self._path_cache:
            return self._path_cache[key]

        prev = self.trees.get(a)
        if prev is None or b not in prev:
            self._path_cache[key] = None
            return None

        out, cur = [b], b
        while cur != a:
            cur = prev[cur]
            out.append(cur)
            if len(out) > 20000:                  # pathological guard
                self._path_cache[key] = None
                return None
        out.reverse()
        self._path_cache[key] = out
        return out

    # -------------------------------------------------------------- decode
    def waypoints_for(self, vector):
        """Map a particle vector to its concrete waypoint nodes."""
        out = []
        for i, value in enumerate(vector):
            band = self.bands[i]
            j = int(min(max(value, 0.0), 0.999999) * len(band))
            out.append(band[j])
        return out

    def decode(self, vector):
        """
        Particle vector -> node sequence.

        Legs are stitched together and any loop is removed, so the result is a
        simple path. Returns None only if a leg is genuinely unreachable.
        """
        self.decode_calls += 1
        stops = [self.source] + self.waypoints_for(vector) + [self.target]

        nodes = [self.source]
        for a, b in zip(stops, stops[1:]):
            if a == b:
                continue
            leg = self._leg(a, b)
            if leg is None:
                return None
            nodes.extend(leg[1:])

        return self._strip_loops(nodes)

    @staticmethod
    def _strip_loops(nodes):
        """
        Remove revisits. Waypoints can send the route back on itself; cutting
        the loop out always shortens it, so this only ever improves the route.
        """
        seen = {}
        out = []
        for n in nodes:
            if n in seen:
                out = out[: seen[n] + 1]
                seen = {node: i for i, node in enumerate(out)}
            else:
                seen[n] = len(out)
                out.append(n)
        return out

    def random_vector(self, rng):
        return rng.random(self.dimensions)
