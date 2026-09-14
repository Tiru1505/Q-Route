"""Mock data provider for development and testing.

╔══════════════════════════════════════════════════════════════════╗
║  WARNING: This module provides SYNTHETIC / MOCK data only.     ║
║  It does NOT represent real traffic conditions or road data.   ║
║  It exists solely so the backend can run and be tested while   ║
║  waiting for real modules from other team members.             ║
╚══════════════════════════════════════════════════════════════════╝
"""

import random
from datetime import datetime, timedelta, timezone

from app.models.route_models import Coordinate


# ---------------------------------------------------------------------------
# Hyderabad-area bounding box for realistic-looking coordinates
# ---------------------------------------------------------------------------

_HYD_LAT_MIN, _HYD_LAT_MAX = 17.30, 17.55
_HYD_LON_MIN, _HYD_LON_MAX = 78.30, 78.60

_ROAD_NAMES = [
    "Mehdipatnam Road", "Jubilee Hills Road No. 36", "Banjara Hills Road No. 12",
    "Tank Bund Road", "Necklace Road", "PVNR Expressway", "NH 65",
    "Begumpet Road", "Secunderabad Station Road", "Ameerpet Main Road",
    "Kukatpally Housing Board Road", "Gachibowli ORR", "Hitech City Main Road",
    "Madhapur Road", "LB Nagar Ring Road", "Charminar Road",
]


def random_coordinate() -> Coordinate:
    """Generate a random coordinate within the Hyderabad bounding box."""
    return Coordinate(
        lat=round(random.uniform(_HYD_LAT_MIN, _HYD_LAT_MAX), 6),
        lon=round(random.uniform(_HYD_LON_MIN, _HYD_LON_MAX), 6),
    )


def mock_traffic_records(count: int = 10) -> list[dict]:
    """Return *count* mock traffic records."""
    now = datetime.now(timezone.utc)
    records = []
    for i in range(count):
        coord = random_coordinate()
        records.append({
            "location": {"lat": coord.lat, "lon": coord.lon},
            "congestion": round(random.uniform(0.05, 0.95), 2),
            "speed_kmh": round(random.uniform(5, 80), 1),
            "segment_id": f"seg-{i:04d}",
            "road_name": random.choice(_ROAD_NAMES),
            "recorded_at": (now - timedelta(minutes=random.randint(0, 30))).isoformat(),
        })
    return records


def mock_graph_nodes(count: int = 6) -> list[dict]:
    """Return a chain of mock graph nodes for testing."""
    nodes = []
    base_lat, base_lon = 17.385, 78.4867
    for i in range(count):
        nodes.append({
            "id": f"node-{i:04d}",
            "lat": round(base_lat + i * 0.008, 6),
            "lon": round(base_lon - i * 0.012, 6),
        })
    return nodes


def mock_route_coordinates(source: Coordinate, destination: Coordinate, waypoints: int = 4) -> list[Coordinate]:
    """Interpolate waypoints between source and destination."""
    coords = [source]
    for i in range(1, waypoints + 1):
        frac = i / (waypoints + 1)
        coords.append(Coordinate(
            lat=round(source.lat + (destination.lat - source.lat) * frac + random.uniform(-0.003, 0.003), 6),
            lon=round(source.lon + (destination.lon - source.lon) * frac + random.uniform(-0.003, 0.003), 6),
        ))
    coords.append(destination)
    return coords


def mock_benchmark_algorithm_result(algorithm: str, repetitions: int = 1) -> dict:
    """Return a mock benchmark result for one algorithm."""
    return {
        "algorithm": algorithm,
        "status": "mock_completed",
        "repetitions": repetitions,
        "execution_time_ms": round(random.uniform(20, 500), 2),
        "distance_km": round(random.uniform(5, 25), 2),
        "travel_time_minutes": round(random.uniform(10, 60), 1),
        "fitness": round(random.uniform(0.5, 0.99), 4),
        "convergence_data": [round(random.uniform(0.3, 1.0) - i * 0.02, 4) for i in range(10)],
    }


def mock_convergence(algorithm: str, iterations: int = 50) -> dict:
    """Return mock convergence data for a single algorithm."""
    fitness = 1.0
    values = []
    for _ in range(iterations):
        fitness = max(0.01, fitness - random.uniform(0.005, 0.03))
        values.append(round(fitness, 4))
    return {
        "algorithm": algorithm,
        "iterations": list(range(1, iterations + 1)),
        "fitness_values": values,
    }
