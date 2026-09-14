"""Pydantic models for traffic data."""

from pydantic import BaseModel, Field

from app.models.route_models import Coordinate


class TrafficRecord(BaseModel):
    location: Coordinate
    congestion: float = Field(..., ge=0, le=1, description="Congestion index 0-1")
    speed_kmh: float | None = Field(default=None, ge=0, description="Current speed on segment")
    segment_id: str | None = Field(default=None, description="Road segment identifier")
    road_name: str | None = None
    recorded_at: str | None = None


class TrafficUpdate(BaseModel):
    records: list[TrafficRecord] = Field(..., min_length=1)


class TrafficSnapshot(BaseModel):
    """A timestamped collection of traffic records."""
    records: list[TrafficRecord]
    timestamp: str
    metadata: dict[str, str] = Field(default_factory=lambda: {"data_source": "mock"})


class TrafficPrediction(BaseModel):
    location: Coordinate
    horizon_minutes: int = Field(default=30, gt=0, le=1440)
    predicted_congestion: float = Field(..., ge=0, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    metadata: dict[str, str] = Field(default_factory=lambda: {"data_source": "mock"})
