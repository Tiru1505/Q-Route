"""Graph adapter — interface boundary for the NetworkX/OSMnx module.

╔══════════════════════════════════════════════════════════════════════╗
║  TEAM INTEGRATION POINT — Person 2 (Graph & Routing Engineer)      ║
║                                                                     ║
║  Replace ``MockGraphAdapter`` with your real implementation.        ║
║  Your class MUST inherit from ``BaseGraphAdapter`` and implement    ║
║  all abstract methods listed below.                                 ║
║                                                                     ║
║  Expected inputs:                                                   ║
║    - RouteRequest with source/destination Coordinates               ║
║  Expected outputs:                                                  ║
║    - GraphRoute dataclass with coordinates, nodes, distance, time   ║
║                                                                     ║
║  Your implementation should:                                        ║
║    1. Load the OSMnx road network graph                             ║
║    2. Find nearest nodes to source/destination                      ║
║    3. Compute shortest path (Dijkstra or other)                     ║
║    4. Return the full route with real coordinates and node IDs      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.logging import get_logger
from app.models.route_models import Coordinate, RouteRequest
from app.utils.geo import haversine_km, estimate_travel_minutes

_logger = get_logger("integrations.graph")


@dataclass
class GraphRoute:
    """Data transfer object returned by graph adapters."""
    coordinates: list[Coordinate]
    nodes: list[str]
    distance_km: float
    travel_time_minutes: float


class BaseGraphAdapter(ABC):
    """Abstract interface that all graph/routing implementations must follow."""

    @abstractmethod
    def calculate_route(self, request: RouteRequest) -> GraphRoute:
        """Compute a route between request.source and request.destination."""
        ...

    @abstractmethod
    def get_nearest_node(self, coord: Coordinate) -> str:
        """Return the graph node ID nearest to the given coordinate."""
        ...

    @abstractmethod
    def get_graph_info(self) -> dict:
        """Return metadata about the loaded graph (node count, edge count, etc.)."""
        ...


class MockGraphAdapter(BaseGraphAdapter):
    """Development-only placeholder — uses straight-line distance, not a real road graph.

    This adapter is clearly marked as mock data.  It will be replaced by
    Person 2's OSMnx-based implementation.
    """

    data_source = "mock"

    def calculate_route(self, request: RouteRequest) -> GraphRoute:
        src, dst = request.source, request.destination
        distance = haversine_km(src.lat, src.lon, dst.lat, dst.lon)
        travel_time = estimate_travel_minutes(distance, speed_kmh=30.0)

        # Generate a few intermediate waypoints for a more realistic mock
        steps = 4
        coords: list[Coordinate] = [src]
        for i in range(1, steps):
            frac = i / steps
            coords.append(Coordinate(
                lat=round(src.lat + (dst.lat - src.lat) * frac, 6),
                lon=round(src.lon + (dst.lon - src.lon) * frac, 6),
            ))
        coords.append(dst)

        nodes = [f"mock-{i:04d}" for i in range(len(coords))]
        _logger.debug("MockGraphAdapter: %.2f km, %.1f min", distance, travel_time)

        return GraphRoute(
            coordinates=coords,
            nodes=nodes,
            distance_km=round(distance, 3),
            travel_time_minutes=round(travel_time, 2),
        )

    def get_nearest_node(self, coord: Coordinate) -> str:
        return "mock-nearest"

    def get_graph_info(self) -> dict:
        return {"status": "mock", "nodes": 0, "edges": 0, "data_source": "mock"}


# NOTE: the real implementation lives in app/integrations/engine_bridge.py.
# It is NOT imported here — engine_bridge imports this module for its base
# classes, so an import back would be circular. Services resolve the real
# adapter lazily via get_graph_adapter() below.
GraphAdapter = MockGraphAdapter


def get_graph_adapter() -> BaseGraphAdapter:
    """Real OSM adapter, falling back to the mock if the graph is unavailable."""
    try:
        from app.integrations.engine_bridge import OsmGraphAdapter
        return OsmGraphAdapter()
    except Exception as exc:                      # graph missing, deps absent
        _logger.warning("Falling back to MockGraphAdapter: %s", exc)
        return MockGraphAdapter()
