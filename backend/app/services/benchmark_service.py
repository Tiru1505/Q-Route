"""Benchmark service — orchestrates multi-algorithm benchmarking with persistence."""

from uuid import uuid4

from app.core.logging import get_logger
from app.integrations.benchmark_adapter import BaseBenchmarkAdapter, MockBenchmarkAdapter
from app.models.benchmark_models import BenchmarkRequest, BenchmarkResult, ConvergenceResult
from app.utils.time_helpers import utc_now_iso

_logger = get_logger("services.benchmark")


class BenchmarkService:
    """Service for benchmarking route optimization algorithms."""

    def __init__(self, adapter: BaseBenchmarkAdapter | None = None):
        self.adapter = adapter or MockBenchmarkAdapter()

    def run(self, request: BenchmarkRequest) -> BenchmarkResult:
        """Execute a benchmark run across the specified algorithms."""
        benchmark_id = str(uuid4())

        results = self.adapter.run(request.route, request.algorithms, request.repetitions)

        benchmark = BenchmarkResult(
            benchmark_id=benchmark_id,
            results=results,
            metadata={"data_source": "mock"},
        )

        self._persist(benchmark)
        _logger.info(
            "Benchmark %s completed: %d algorithms × %d reps",
            benchmark_id, len(request.algorithms), request.repetitions,
        )
        return benchmark

    def get_results(self, limit: int = 50) -> list[dict]:
        """Retrieve recent benchmark results from MongoDB."""
        try:
            from app.database.collections import get_benchmark_results_col
            cursor = (
                get_benchmark_results_col()
                .find()
                .sort("created_at", -1)
                .limit(limit)
            )
            results = []
            for doc in cursor:
                doc.pop("_id", None)
                results.append(doc)
            return results
        except Exception as exc:
            _logger.warning("DB benchmark lookup failed: %s", exc)
            return []

    def get_convergence(self, algorithm: str = "qpso") -> ConvergenceResult:
        """Return convergence data for the specified algorithm."""
        raw = self.adapter.get_convergence(algorithm)
        return ConvergenceResult(
            algorithm=raw["algorithm"],
            iterations=raw["iterations"],
            fitness_values=raw["fitness_values"],
            metadata={"data_source": "mock"},
        )

    def _persist(self, result: BenchmarkResult) -> None:
        """Best-effort persistence of benchmark results."""
        try:
            from app.database.collections import get_benchmark_results_col
            doc = result.model_dump()
            doc["created_at"] = utc_now_iso()
            get_benchmark_results_col().insert_one(doc)
        except Exception as exc:
            _logger.warning("Failed to persist benchmark result: %s", exc)
