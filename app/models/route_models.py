"""Pydantic models for route requests and responses."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Coordinate(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    lon: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")


class Algorithm(str, Enum):
    qpso = "qpso"
    pso = "pso"
    ga = "ga"
    dijkstra = "dijkstra"


class RouteConstraints(BaseModel):
    avoid_tolls: bool = False
    avoid_highways: bool = False
    max_distance_km: float | None = Field(default=None, gt=0)


class RouteRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    source: Coordinate
    destination: Coordinate
    algorithm: Algorithm = Algorithm.qpso
    constraints: RouteConstraints | None = None
    departure_time: str | None = Field(
        default=None, description="ISO-8601 departure time for ETA calculation"
    )
    # What the user actually typed. Routing works purely on coordinates, but
    # without these the history page can only show a pair of lat/lons — and
    # since endpoints are now free text rather than a fixed list of landmarks,
    # there is no lookup table to recover the name from afterwards.
    source_name: str | None = Field(default=None, max_length=200)
    destination_name: str | None = Field(default=None, max_length=200)
    user_id: str | None = None
    # Which road network to route on. "hyderabad" has every street but stops at
    # the ORR; "india" reaches the whole country but only along motorway, trunk
    # and primary roads, so it cannot deliver to an address. Neither contains
    # the other, so the caller chooses and nothing here guesses. Omitted means
    # the default city graph, which keeps every existing client working.
    graph: str | None = Field(
        default=None,
        description="Road network: 'hyderabad' (all streets, one city) or "
                    "'india' (national highways). Defaults to 'hyderabad'.",
    )

    @model_validator(mode="after")
    def locations_must_differ(self) -> "RouteRequest":
        if self.source == self.destination:
            raise ValueError("source and destination must be different")
        return self


class RerouteRequest(BaseModel):
    """
    Ask whether a better route exists from where the driver is now.

    Rerouting is only meaningful part-way through a journey — the road already
    travelled cannot be re-decided — so `progress` says how far along the driver
    is. `spike` congests the road *ahead* of that point, which is what gives the
    demo something real to react to: without it the network is unchanged since
    the route was planned, and the honest answer is always "no better route".
    """

    progress: float = Field(
        default=0.4, ge=0.0, le=1.0,
        description="Fraction of the planned route already driven",
    )
    spike: bool = Field(
        default=True,
        description="Congest the road ahead before evaluating (demo trigger)",
    )
    spike_level: float = Field(
        default=0.92, ge=0.0, le=1.0,
        description="Congestion level to apply to the road ahead",
    )
    force: bool = Field(
        default=False,
        description="Evaluate even when the route has not degraded past the threshold",
    )


class RouteSummary(BaseModel):
    coordinates: list[Coordinate]
    nodes: list[str]
    distance_km: float
    travel_time_minutes: float


class RouteResponse(BaseModel):
    success: bool = True
    request_id: str
    algorithm: str
    route: RouteSummary
    congestion: float | None = None
    fitness: float | None = None
    execution_time_ms: float | None = None
    eta: str | None = Field(default=None, description="Estimated time of arrival (ISO-8601)")
    alternative_routes: list[RouteSummary] | None = None
    prediction: dict[str, Any] | None = Field(
        default=None, description="Traffic prediction attached to this route"
    )
    alerts: list[dict[str, Any]] | None = Field(
        default=None, description="Active alerts along this route"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
