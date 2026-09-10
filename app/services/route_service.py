"""Route service — orchestrates graph + optimization + traffic for route requests."""

from time import perf_counter
from uuid import uuid4

from app.core.errors import GraphUnavailableError, NoRouteFoundError, OptimizationError
from app.core.logging import get_logger
from app.integrations.graph_adapter import GraphRoute, MockGraphAdapter, BaseGraphAdapter, get_graph_adapter
from app.integrations.qpso_adapter import get_optimization_adapter
from app.integrations.traffic_adapter import MockTrafficAdapter, BaseTrafficAdapter, get_traffic_adapter
from app.models.route_models import RouteRequest, RouteResponse, RouteSummary, Coordinate
from app.utils.geo import estimate_eta
from app.utils.time_helpers import utc_now_iso

_logger = get_logger("services.route")


class RouteService:
    """Central service for route optimization requests.

    Delegates to graph, optimization, and traffic adapters.
    """

    def __init__(
        self,
        graph_adapter: BaseGraphAdapter | None = None,
        traffic_adapter: BaseTrafficAdapter | None = None,
    ):
        self.graph = graph_adapter or get_graph_adapter()
        self.traffic = traffic_adapter or get_traffic_adapter()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def optimize(self, request: RouteRequest) -> RouteResponse:
        """Run end-to-end route optimization and return a RouteResponse."""
        started = perf_counter()
        request_id = str(uuid4())

        try:
            # 1. Graph baseline
            baseline = self.graph.calculate_route(request)
        except Exception as exc:
            _logger.error("Graph adapter failed: %s", exc)
            raise GraphUnavailableError(str(exc)) from exc

        try:
            # 2. Optimization
            adapter = get_optimization_adapter(request.algorithm)
            opt_result = adapter.optimize(request, baseline)
            route = opt_result.route
        except GraphUnavailableError:
            raise
        except Exception as exc:
            _logger.warning("Optimization failed, falling back to baseline: %s", exc)
            route = baseline
            opt_result = None

        # 3. Congestion
        try:
            congestion = self.traffic.get_congestion(request.source)
        except Exception:
            congestion = None

        elapsed_ms = (perf_counter() - started) * 1000

        # 4. ETA
        eta = estimate_eta(route.travel_time_minutes)

        response = RouteResponse(
            request_id=request_id,
            algorithm=request.algorithm,
            route=RouteSummary(
                coordinates=route.coordinates,
                nodes=route.nodes,
                distance_km=route.distance_km,
                travel_time_minutes=route.travel_time_minutes,
            ),
            congestion=congestion,
            fitness=opt_result.fitness if opt_result else None,
            execution_time_ms=round(elapsed_ms, 3),
            eta=eta,
            iterations_used=getattr(opt_result, "iterations_used", None) if opt_result else None,
            convergence_history=(
                getattr(opt_result, "convergence_history", None) if opt_result else None
            ),
            metadata={
                # Reported from the adapter actually in use, not hardcoded: the
                # services default to the real OSM engine now, and labelling
                # genuine engine output "mock" is worse than saying nothing.
                "data_source": getattr(self.graph, "data_source", "unknown"),
                "optimization_status": "completed" if opt_result else "fallback_baseline",
            },
        )

        # 5. Persist to MongoDB (best-effort)
        self._persist(request, response)

        _logger.info(
            "Route %s optimized: %.2f km in %.1f min (algo=%s, %.1f ms)",
            request_id, route.distance_km, route.travel_time_minutes,
            request.algorithm, elapsed_ms,
        )
        return response

    def get_alternatives(self, request: RouteRequest, count: int = 3) -> list[RouteResponse]:
        """
        Generate alternative routes.

        Preferred: ask the graph adapter for genuinely different CORRIDORS.
        Running the same request through different algorithms (the fallback
        below) returns identical paths once every optimiser converges on the
        same optimum, which makes the "alternatives" list useless to the user.
        """
        if hasattr(self.graph, "alternative_routes"):
            try:
                primary = self.optimize(request)
                out = [primary]
                for alt in self.graph.alternative_routes(request, count)[: count - 1]:
                    resp = primary.model_copy(deep=True)
                    resp.request_id = str(uuid4())
                    resp.route = RouteSummary(
                        coordinates=alt.coordinates,
                        nodes=alt.nodes,
                        distance_km=alt.distance_km,
                        travel_time_minutes=alt.travel_time_minutes,
                    )
                    resp.eta = estimate_eta(alt.travel_time_minutes)
                    out.append(resp)
                if len(out) > 1:
                    return out
            except Exception as exc:
                _logger.warning("Corridor alternatives failed, falling back: %s", exc)

        alternatives: list[RouteResponse] = []
        algorithms = ["dijkstra", "pso", "qpso"]
        for algo in algorithms[:count]:
            alt_request = request.model_copy(update={"algorithm": algo})
            try:
                alternatives.append(self.optimize(alt_request))
            except Exception as exc:
                _logger.warning("Alternative route (%s) failed: %s", algo, exc)
        if not alternatives:
            raise NoRouteFoundError("Could not generate any alternative routes")
        return alternatives

    def get_by_id(self, request_id: str) -> RouteResponse | None:
        """Retrieve a stored route result from MongoDB by request_id."""
        try:
            from app.database.collections import get_optimization_results_col
            doc = get_optimization_results_col().find_one({"request_id": request_id})
            if doc is None:
                return None
            doc.pop("_id", None)
            return RouteResponse(**doc)
        except Exception as exc:
            _logger.warning("DB lookup failed for %s: %s", request_id, exc)
            return None

    def reroute(self, request) -> dict:
        """
        Is a better route available from where the driver is now?

        Delegates to the graph adapter when it can actually do this. The mock
        adapter cannot — it has no notion of a trip in progress — so rather than
        inventing a saving, we say plainly that rerouting is unavailable.
        """
        if not hasattr(self.graph, "reroute"):
            raise NoRouteFoundError(
                "Rerouting needs the real routing engine; the active graph "
                "adapter does not support it."
            )
        try:
            return self.graph.reroute(
                progress=request.progress,
                spike=request.spike,
                spike_level=request.spike_level,
                force=request.force,
            )
        except ValueError as exc:
            raise NoRouteFoundError(str(exc)) from exc

    def get_history(self, user_id: str | None = None, limit: int = 50) -> list[dict]:
        """Return recent route results from MongoDB."""
        try:
            from app.database.collections import get_optimization_results_col
            query: dict = {}
            if user_id:
                query["user_id"] = user_id
            cursor = (
                get_optimization_results_col()
                .find(query)
                .sort("created_at", -1)
                .limit(limit)
            )
            results = []
            for doc in cursor:
                doc.pop("_id", None)
                results.append(doc)
            return results
        except Exception as exc:
            _logger.warning("DB history lookup failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist(self, request: RouteRequest, response: RouteResponse) -> None:
        """Best-effort persistence — does not raise on failure."""
        try:
            from app.database.collections import get_optimization_results_col
            doc = response.model_dump()
            doc["created_at"] = utc_now_iso()
            doc["user_id"] = request.user_id
            doc["source"] = request.source.model_dump()
            doc["destination"] = request.destination.model_dump()
            doc["source_name"] = request.source_name
            doc["destination_name"] = request.destination_name
            get_optimization_results_col().update_one(
                {"request_id": response.request_id},
                {"$set": doc},
                upsert=True,
            )
        except Exception as exc:
            _logger.warning("Failed to persist route result: %s", exc)
