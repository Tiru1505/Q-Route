"""Traffic adapter — interface boundary for the traffic data module.

╔══════════════════════════════════════════════════════════════════════╗
║  TEAM INTEGRATION POINT — Person 3 (Traffic & Prediction Engineer) ║
║                                                                     ║
║  Replace ``MockTrafficAdapter`` with your real implementation.      ║
║  Your class MUST inherit from ``BaseTrafficAdapter``.               ║
║                                                                     ║
║  Expected responsibilities:                                         ║
║    - Fetch current traffic density / congestion data                ║
║    - Accept traffic data updates (from sensors, APIs, etc.)         ║
║    - Provide congestion values for specific road segments           ║
║    - Update dynamic graph weights based on traffic conditions       ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from abc import ABC, abstractmethod

from app.core.logging import get_logger
from app.models.route_models import Coordinate
from app.models.traffic_models import TrafficRecord

_logger = get_logger("integrations.traffic")


class BaseTrafficAdapter(ABC):
    """Abstract interface that the traffic module implementation must follow."""

    @abstractmethod
    def current(self) -> list[TrafficRecord]:
        """Return the latest traffic records."""
        ...

    @abstractmethod
    def update(self, records: list[TrafficRecord]) -> int:
        """Ingest new traffic records. Return the count of records accepted."""
        ...

    @abstractmethod
    def get_congestion(self, coord: Coordinate) -> float:
        """Return the congestion index (0–1) nearest to the given coordinate."""
        ...


class MockTrafficAdapter(BaseTrafficAdapter):
    """Development-only placeholder — returns synthetic Hyderabad-area traffic data.

    This is NOT real traffic data.
    """

    def __init__(self) -> None:
        self._records: list[TrafficRecord] = []

    def current(self) -> list[TrafficRecord]:
        if self._records:
            return self._records
        # Return sample data when no updates have been pushed
        from dataio.mock_provider import mock_traffic_records
        return [TrafficRecord(**r) for r in mock_traffic_records(8)]

    def update(self, records: list[TrafficRecord]) -> int:
        self._records.extend(records)
        _logger.debug("MockTrafficAdapter: accepted %d records", len(records))
        return len(records)

    def get_congestion(self, coord: Coordinate) -> float:
        import random
        _logger.debug("MockTrafficAdapter: returning random congestion for (%.4f, %.4f)", coord.lat, coord.lon)
        return round(random.uniform(0.1, 0.9), 2)


# See the note in graph_adapter.py — resolved lazily to avoid a circular import.
TrafficAdapter = MockTrafficAdapter


def get_traffic_adapter() -> BaseTrafficAdapter:
    """Real simulator-backed adapter, falling back to the mock."""
    try:
        from app.integrations.engine_bridge import RealTrafficAdapter
        return RealTrafficAdapter()
    except Exception as exc:
        _logger.warning("Falling back to MockTrafficAdapter: %s", exc)
        return MockTrafficAdapter()
