"""
The common interface every optimiser searches.

QPSO, PSO and GA all operate on the same thing: a box-constrained continuous
vector in [0,1]^D, scored by one evaluate() call. Because the problem object is
shared, the three algorithms provably search an identical space with an
identical objective — which is the precondition for the benchmark to mean
anything.
"""
import math
from dataclasses import dataclass, field


@dataclass
class EvalResult:
    """What one fitness evaluation returns."""
    fitness: float = math.inf
    solution: object = None          # decoded form (a Route, an order, ...)
    feasible: bool = True


class Problem:
    """
    Minimal contract.

    Subclasses provide `dimensions` and `evaluate(vector) -> EvalResult`.
    Vectors are always in [0,1]^D, so every algorithm can use the same bound
    handling and no algorithm gets an encoding advantage.
    """

    name = "problem"
    dimensions = 0

    def evaluate(self, vector):
        raise NotImplementedError

    def describe(self):
        return f"{self.name} (D={self.dimensions})"


@dataclass
class RunStats:
    """Uniform result record, so the benchmark can compare like with like."""

    algorithm: str = ""
    best_fitness: float = math.inf
    best_vector: object = None
    best_solution: object = None
    convergence: list = field(default_factory=list)   # best-so-far per iteration
    mean_fitness: list = field(default_factory=list)  # population mean per iteration
    evaluations: int = 0
    iterations: int = 0
    iteration_of_best: int = 0
    runtime_ms: float = 0.0
    feasible: bool = True

    def summary(self):
        return (f"{self.algorithm:<8} fitness {self.best_fitness:.6f}  "
                f"evals {self.evaluations:5d}  iters {self.iterations:4d}  "
                f"{self.runtime_ms:8.1f} ms")
