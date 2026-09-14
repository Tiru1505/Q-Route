"""Tests for adapter interface contracts."""

from app.integrations.graph_adapter import MockGraphAdapter, GraphRoute
from app.integrations.qpso_adapter import (
    MockQpsoAdapter, MockPsoAdapter, MockGaAdapter, MockDijkstraAdapter,
    get_optimization_adapter, OptimizationResult,
)
from app.integrations.traffic_adapter import MockTrafficAdapter
from app.integrations.prediction_adapter import MockPredictionAdapter
from app.integrations.benchmark_adapter import MockBenchmarkAdapter
from app.models.route_models import Coordinate, RouteRequest


def _make_request() -> RouteRequest:
    return RouteRequest(
        source=Coordinate(lat=17.385, lon=78.4867),
        destination=Coordinate(lat=17.450, lon=78.380),
        algorithm="qpso",
    )


class TestGraphAdapter:
    def test_calculate_route_returns_graph_route(self):
        adapter = MockGraphAdapter()
        result = adapter.calculate_route(_make_request())
        assert isinstance(result, GraphRoute)
        assert result.distance_km > 0
        assert len(result.coordinates) >= 2

    def test_get_nearest_node(self):
        adapter = MockGraphAdapter()
        node = adapter.get_nearest_node(Coordinate(lat=17.385, lon=78.486))
        assert isinstance(node, str)

    def test_get_graph_info(self):
        adapter = MockGraphAdapter()
        info = adapter.get_graph_info()
        assert info["status"] == "mock"


class TestOptimizationAdapters:
    def test_qpso_returns_optimization_result(self):
        adapter = MockQpsoAdapter()
        baseline = MockGraphAdapter().calculate_route(_make_request())
        result = adapter.optimize(_make_request(), baseline)
        assert isinstance(result, OptimizationResult)
        assert result.fitness is not None

    def test_pso_adapter(self):
        adapter = MockPsoAdapter()
        baseline = MockGraphAdapter().calculate_route(_make_request())
        result = adapter.optimize(_make_request(), baseline)
        assert isinstance(result, OptimizationResult)

    def test_ga_adapter(self):
        adapter = MockGaAdapter()
        baseline = MockGraphAdapter().calculate_route(_make_request())
        result = adapter.optimize(_make_request(), baseline)
        assert isinstance(result, OptimizationResult)

    def test_dijkstra_adapter(self):
        adapter = MockDijkstraAdapter()
        baseline = MockGraphAdapter().calculate_route(_make_request())
        result = adapter.optimize(_make_request(), baseline)
        assert isinstance(result, OptimizationResult)
        assert result.iterations_used == 1

    def test_get_optimization_adapter_factory(self):
        for algo in ["qpso", "pso", "ga", "dijkstra"]:
            adapter = get_optimization_adapter(algo)
            assert adapter.algorithm == algo

    def test_get_optimization_adapter_invalid(self):
        import pytest
        from app.core.errors import InvalidAlgorithmError
        with pytest.raises(InvalidAlgorithmError):
            get_optimization_adapter("nonexistent")

    def test_convergence_history(self):
        adapter = MockQpsoAdapter()
        baseline = MockGraphAdapter().calculate_route(_make_request())
        result = adapter.optimize(_make_request(), baseline, iterations=20)
        assert len(result.convergence_history) > 0
        assert result.convergence_history == adapter.get_convergence()


class TestTrafficAdapter:
    def test_current_returns_list(self):
        adapter = MockTrafficAdapter()
        result = adapter.current()
        assert isinstance(result, list)

    def test_update_returns_count(self):
        from app.models.traffic_models import TrafficRecord
        adapter = MockTrafficAdapter()
        records = [
            TrafficRecord(location=Coordinate(lat=17.385, lon=78.486), congestion=0.5),
        ]
        count = adapter.update(records)
        assert count == 1

    def test_get_congestion(self):
        adapter = MockTrafficAdapter()
        val = adapter.get_congestion(Coordinate(lat=17.385, lon=78.486))
        assert 0 <= val <= 1


class TestPredictionAdapter:
    def test_predict_returns_dict(self):
        adapter = MockPredictionAdapter()
        result = adapter.predict(Coordinate(lat=17.385, lon=78.486), 30)
        assert "predicted_congestion" in result
        assert "confidence" in result
        assert result["data_source"] == "mock"


class TestBenchmarkAdapter:
    def test_run_returns_list(self):
        adapter = MockBenchmarkAdapter()
        results = adapter.run(_make_request(), ["qpso", "dijkstra"], 1)
        assert len(results) == 2
        assert results[0].algorithm == "qpso"

    def test_get_convergence(self):
        adapter = MockBenchmarkAdapter()
        conv = adapter.get_convergence("qpso")
        assert conv["algorithm"] == "qpso"
        assert len(conv["iterations"]) == len(conv["fitness_values"])
