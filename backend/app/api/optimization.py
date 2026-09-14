"""Optimization API endpoints — per-algorithm access."""

from fastapi import APIRouter

from app.models.optimization_models import OptimizationRequest, OptimizationResponse
from app.services.optimization_service import OptimizationService

router = APIRouter(prefix="/optimization", tags=["optimization"])
_service = OptimizationService()


@router.post(
    "/{algorithm}",
    response_model=OptimizationResponse,
    summary="Run a specific optimization algorithm",
    description=(
        "Execute route optimization using the specified algorithm "
        "(qpso, pso, ga, or dijkstra). Returns the optimized route, "
        "fitness score, convergence data, and execution metrics."
    ),
    responses={
        200: {"description": "Optimization completed successfully"},
        422: {"description": "Unsupported algorithm or invalid request"},
        500: {"description": "Optimization algorithm failed"},
    },
)
def optimize(algorithm: str, request: OptimizationRequest) -> OptimizationResponse:
    return _service.run(algorithm, request)
