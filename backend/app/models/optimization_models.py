"""Pydantic models for optimization endpoints."""

from pydantic import BaseModel, Field

from app.models.route_models import RouteRequest, RouteResponse


class OptimizationRequest(RouteRequest):
    iterations: int = Field(default=100, gt=0, le=10000, description="Max iterations for the optimizer")
    particles: int = Field(default=30, gt=0, le=500, description="Swarm / population size")


class OptimizationResponse(BaseModel):
    result: RouteResponse
    status: str = "adapter_placeholder"
    best_fitness: float | None = None
    iterations_used: int | None = None
    convergence_history: list[float] | None = Field(
        default=None, description="Fitness value at each iteration"
    )
