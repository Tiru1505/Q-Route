"""Benchmark adapter — interface boundary for the benchmarking module.

╔══════════════════════════════════════════════════════════════════════╗
║  TEAM INTEGRATION POINT — Person 4 (Benchmarking & Research)       ║
║                                                                     ║
║  Replace ``MockBenchmarkAdapter`` with your real implementation.    ║
║  Your class MUST inherit from ``BaseBenchmarkAdapter``.             ║
║                                                                     ║
║  Expected responsibilities:                                         ║
║    - Run Dijkstra, PSO, GA, QPSO on the same route                 ║
║    - Collect execution time, solution quality, convergence data     ║
║    - Return structured results per algorithm                        ║
║    - Support multiple repetitions for statistical analysis          ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from abc import ABC, abstractmethod

from app.core.logging import get_logger
from app.models.benchmark_models import BenchmarkAlgorithmResult
from app.models.route_models import RouteRequest

_logger = get_logger("integrations.benchmark")


class BaseBenchmarkAdapter(ABC):
    """Abstract interface that the benchmarking module must follow."""

    @abstractmethod
    def run(
        self,
        request: RouteRequest,
        algorithms: list[str],
        repetitions: int,
    ) -> list[BenchmarkAlgorithmResult]:
        """Execute benchmarks and return structured results per algorithm."""
        ...

    @abstractmethod
    def get_convergence(self, algorithm: str) -> dict:
        """Return convergence data for the given algorithm from the last run."""
        ...


class MockBenchmarkAdapter(BaseBenchmarkAdapter):
    """Development-only placeholder — returns synthetic benchmark data.

    This is NOT real benchmarking output.
    """

    def __init__(self) -> None:
        self._last_results: list[BenchmarkAlgorithmResult] = []

    def run(
        self,
        request: RouteRequest,
        algorithms: list[str],
        repetitions: int,
    ) -> list[BenchmarkAlgorithmResult]:
        from dataio.mock_provider import mock_benchmark_algorithm_result

        results = []
        for algo in algorithms:
            raw = mock_benchmark_algorithm_result(algo, repetitions)
            results.append(BenchmarkAlgorithmResult(**raw))
        self._last_results = results
        _logger.debug("MockBenchmarkAdapter: generated %d mock results", len(results))
        return results

    def get_convergence(self, algorithm: str) -> dict:
        from dataio.mock_provider import mock_convergence
        return mock_convergence(algorithm)


# Default adapter instance
BenchmarkAdapter = MockBenchmarkAdapter
