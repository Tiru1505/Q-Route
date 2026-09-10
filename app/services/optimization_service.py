"""Optimization service — dispatches to the correct algorithm adapter."""

from time import perf_counter
from uuid import uuid4

from app.core.errors import InvalidAlgorithmError, NoRouteFoundError, OptimizationError
from app.core.logging import get_logger
from app.integrations.graph_adapter import MockGraphAdapter, BaseGraphAdapter, get_graph_adapter
from app.integrations.qpso_adapter import get_optimization_adapter
from app.models.optimization_models import OptimizationRequest, OptimizationResponse
from app.models.route_models import RouteResponse, RouteSummary
from graph.errors import UnknownGraphError
from app.utils.time_helpers import utc_now_iso

_logger = get_logger("services.optimization")

_VALID_ALGORITHMS = {"qpso", "pso", "ga", "dijkstra"}


class OptimizationService:
    """Service for running individual optimization algorithms."""

    def __init__(self, graph_adapter: BaseGraphAdapter | None = None):
        self.graph = graph_adapter or get_graph_adapter()

    def run(self, algorithm: str, request: OptimizationRequest) -> OptimizationResponse:
        """Execute the specified optimization algorithm."""
        if algorithm not in _VALID_ALGORITHMS:
            raise InvalidAlgorithmError(algorithm)

        started = perf_counter()
        request_id = str(uuid4())

        try:
            baseline = self.graph.calculate_route(request)
            adapter = get_optimization_adapter(algorithm)
            opt_result = adapter.optimize(
                request, baseline,
                iterations=request.iterations,
                particles=request.particles,
            )
        except (InvalidAlgorithmError, UnknownGraphError, NoRouteFoundError):
            # Both are the caller naming something that does not exist. As an
            # "optimization failed" 500 they read as the optimiser breaking.
            raise
        except Exception as exc:
            _logger.error("Optimization failed (%s): %s", algorithm, exc)
            raise OptimizationError(f"{algorithm} optimization failed: {exc}") from exc

        elapsed_ms = (perf_counter() - started) * 1000
        route = opt_result.route

        route_response = RouteResponse(
            request_id=request_id,
            algorithm=algorithm,
            route=RouteSummary(
                coordinates=route.coordinates,
                nodes=route.nodes,
                distance_km=route.distance_km,
                travel_time_minutes=route.travel_time_minutes,
            ),
            fitness=opt_result.fitness,
            execution_time_ms=round(elapsed_ms, 3),
            metadata={
                "data_source": getattr(adapter, "data_source", "unknown"),
                "optimization_status": "completed",
            },
        )

        response = OptimizationResponse(
            result=route_response,
            status="completed",
            best_fitness=opt_result.fitness,
            iterations_used=opt_result.iterations_used,
            convergence_history=opt_result.convergence_history or None,
        )

        _logger.info(
            "Optimization %s (%s): fitness=%.4f, %d iters, %.1f ms",
            request_id, algorithm,
            opt_result.fitness or 0, opt_result.iterations_used or 0, elapsed_ms,
        )
        return response
