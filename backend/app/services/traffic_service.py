"""Traffic service — wraps the traffic adapter with persistence and error handling."""

from app.core.errors import TrafficDataUnavailableError
from app.core.logging import get_logger
from app.integrations.traffic_adapter import (
    BaseTrafficAdapter, MockTrafficAdapter, get_traffic_adapter,
)
from app.models.traffic_models import TrafficRecord, TrafficSnapshot
from app.utils.time_helpers import utc_now_iso

_logger = get_logger("services.traffic")


class TrafficService:
    """Service for traffic data operations."""

    def __init__(self, adapter: BaseTrafficAdapter | None = None):
        self.adapter = adapter or get_traffic_adapter()

    def get_current(self) -> TrafficSnapshot:
        """Fetch current traffic data from the adapter."""
        try:
            records = self.adapter.current()
            return TrafficSnapshot(
                records=records,
                timestamp=utc_now_iso(),
                metadata={"data_source": getattr(self.adapter, "data_source", "unknown")},
            )
        except Exception as exc:
            _logger.error("Failed to fetch traffic data: %s", exc)
            raise TrafficDataUnavailableError(str(exc)) from exc

    def update(self, records: list[TrafficRecord]) -> int:
        """Ingest new traffic records and persist to MongoDB."""
        try:
            count = self.adapter.update(records)
            self._persist_records(records)
            _logger.info("Accepted %d traffic records", count)
            return count
        except Exception as exc:
            _logger.error("Traffic update failed: %s", exc)
            raise TrafficDataUnavailableError(str(exc)) from exc

    def _persist_records(self, records: list[TrafficRecord]) -> None:
        """Best-effort persistence of traffic records to MongoDB."""
        try:
            from app.database.collections import get_traffic_records_col
            docs = []
            now = utc_now_iso()
            for rec in records:
                doc = rec.model_dump()
                doc.setdefault("recorded_at", now)
                docs.append(doc)
            if docs:
                get_traffic_records_col().insert_many(docs)
        except Exception as exc:
            _logger.warning("Failed to persist traffic records: %s", exc)
