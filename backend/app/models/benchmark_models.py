"""Pydantic models for benchmarking endpoints."""

from pydantic import BaseModel, Field

from app.models.route_models import RouteRequest


class BenchmarkAlgorithmResult(BaseModel):
    """Structured result for a single algorithm in a benchmark run."""
    algorithm: str
    status: str = "adapter_placeholder"
    repetitions: int = 1
    execution_time_ms: float | None = None
    distance_km: float | None = None
    travel_time_minutes: float | None = None
    fitness: float | None = None
    convergence_data: list[float] | None = None


class BenchmarkRequest(BaseModel):
    route: RouteRequest
    algorithms: list[str] = Field(default=["dijkstra", "pso", "qpso", "ga"], min_length=1)
    repetitions: int = Field(default=1, gt=0, le=100)


class BenchmarkResult(BaseModel):
    benchmark_id: str
    results: list[BenchmarkAlgorithmResult]
    metadata: dict[str, str] = Field(default_factory=lambda: {"data_source": "mock"})


class ConvergenceResult(BaseModel):
    """Convergence data for a specific algorithm across iterations."""
    algorithm: str
    iterations: list[int]
    fitness_values: list[float]
    metadata: dict[str, str] = Field(default_factory=lambda: {"data_source": "mock"})
