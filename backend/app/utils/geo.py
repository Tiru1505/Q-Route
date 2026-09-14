"""Geographic utility functions."""

import math
from datetime import datetime, timezone

_EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in kilometres between two points."""
    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return _EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def estimate_travel_minutes(distance_km: float, speed_kmh: float = 30.0) -> float:
    """Estimate travel time in minutes given distance and average speed."""
    if speed_kmh <= 0:
        return 0.0
    return round(distance_km / speed_kmh * 60, 2)


def estimate_eta(travel_minutes: float, departure: datetime | None = None) -> str:
    """Return an ISO-8601 ETA string."""
    base = departure or datetime.now(timezone.utc)
    from datetime import timedelta
    eta = base + timedelta(minutes=travel_minutes)
    return eta.isoformat()


def interpolate_coordinates(
    lat1: float, lon1: float, lat2: float, lon2: float, steps: int = 4,
) -> list[tuple[float, float]]:
    """Generate intermediate (lat, lon) waypoints between two points (linear)."""
    points: list[tuple[float, float]] = [(lat1, lon1)]
    for i in range(1, steps):
        frac = i / steps
        points.append((
            round(lat1 + (lat2 - lat1) * frac, 6),
            round(lon1 + (lon2 - lon1) * frac, 6),
        ))
    points.append((lat2, lon2))
    return points
