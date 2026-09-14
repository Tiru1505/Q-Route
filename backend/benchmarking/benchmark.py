"""
The benchmark harness.

FAIRNESS IS THE WHOLE POINT
---------------------------
A comparison is worthless unless every algorithm gets identical conditions. We
enforce that structurally rather than by good intentions:

  same problem object   one MultiStopProblem instance, shared. Same graph, same
                        traffic, same stops, same objective function.
  same encoding         random keys in [0,1]^D for all three.
  same budget           equal population x iterations, so equal fitness
                        evaluations. Reported, so a reader can check.
  same seeds            trial k uses seed base+k for every algorithm, so they
                        face the same random draws.
  same bound handling   reflection at the box edges in all three.

Stochastic algorithms are run over many trials and reported as mean, standard
deviation, best and worst — a single run of a stochastic algorithm is an
anecdote, not a result.

Where an exact optimum is computable (brute force, up to ~9 stops) it is
included, so the gap is measured rather than assumed.
"""
import math
import statistics
import time
from dataclasses import dataclass, field

from optimization.genetic_algorithm import GAConfig, GeneticAlgorithm
from optimization.problem import RunStats
from optimization.pso import PSO, PSOConfig
from optimization.qpso import QPSO, QPSOConfig


@dataclass
class AlgorithmSummary:
    name: str
    best: float = math.inf
    worst: float = math.inf
    mean: float = math.inf
    std: float = 0.0
    median: float = math.inf
    mean_runtime_ms: float = 0.0
    mean_iterations: float = 0.0
    mean_evaluations: float = 0.0
    mean_iteration_of_best: float = 0.0
    optimal_hits: int = 0
    trials: int = 0
    convergence_curves: list = field(default_factory=list)
    best_solution: object = None

    @property
    def optimal_rate(self):
        return self.optimal_hits / self.trials if self.trials else 0.0

    def gap_vs(self, optimum):
        if optimum is None or not math.isfinite(optimum) or optimum <= 0:
            return None
        return (self.mean / optimum - 1.0) * 100.0


def qpso_runner(problem, budget, seed):
    cfg = QPSOConfig(n_particles=budget.population, max_iterations=budget.iterations,
                     stagnation_limit=budget.stagnation, seed=seed)
    res = QPSO(problem=problem, config=cfg).run(seed=seed)
    return RunStats(
        algorithm="QPSO", best_fitness=res.best_fitness, best_vector=res.best_vector,
        best_solution=res.route, convergence=res.convergence,
        mean_fitness=res.mean_fitness, evaluations=res.evaluations,
        iterations=res.iterations_run, iteration_of_best=res.iteration_of_best,
        runtime_ms=res.runtime_ms,
    )


def pso_runner(problem, budget, seed):
    cfg = PSOConfig(n_particles=budget.population, max_iterations=budget.iterations,
                    stagnation_limit=budget.stagnation, seed=seed)
    return PSO(problem, cfg).run(seed=seed)


def ga_runner(problem, budget, seed):
    cfg = GAConfig(population_size=budget.population, max_generations=budget.iterations,
                   stagnation_limit=budget.stagnation, seed=seed)
    return GeneticAlgorithm(problem, cfg).run(seed=seed)


RUNNERS = {"QPSO": qpso_runner, "PSO": pso_runner, "GA": ga_runner}


@dataclass
class Budget:
    """Identical for every algorithm. This is what makes the comparison fair."""
    population: int = 40
    iterations: int = 120
    stagnation: int = 80

    @property
    def max_evaluations(self):
        return self.population * self.iterations

    def describe(self):
        return (f"population {self.population} x {self.iterations} iterations "
                f"= {self.max_evaluations:,} evaluations per trial (identical "
                f"for all algorithms)")


def run_benchmark(problem, trials=30, budget=None, seed_base=1000,
                  algorithms=("QPSO", "PSO", "GA"), optimum=None, verbose=True):
    """Run every algorithm over `trials` independent seeds."""
    budget = budget or Budget()
    summaries = {}

    for name in algorithms:
        runner = RUNNERS[name]
        fitnesses, runtimes, iters, evals, iob = [], [], [], [], []
        curves, best_solution, best_fit = [], None, math.inf

        t0 = time.perf_counter()
        for k in range(trials):
            stats = runner(problem, budget, seed_base + k)
            fitnesses.append(stats.best_fitness)
            runtimes.append(stats.runtime_ms)
            iters.append(stats.iterations)
            evals.append(stats.evaluations)
            iob.append(stats.iteration_of_best)
            curves.append(stats.convergence)
            if stats.best_fitness < best_fit:
                best_fit = stats.best_fitness
                best_solution = stats.best_solution
        wall = time.perf_counter() - t0

        finite = [f for f in fitnesses if math.isfinite(f)]
        hits = 0
        if optimum is not None and math.isfinite(optimum):
            hits = sum(1 for f in finite if f <= optimum * (1 + 1e-9))

        summaries[name] = AlgorithmSummary(
            name=name,
            best=min(finite) if finite else math.inf,
            worst=max(finite) if finite else math.inf,
            mean=statistics.mean(finite) if finite else math.inf,
            std=statistics.pstdev(finite) if len(finite) > 1 else 0.0,
            median=statistics.median(finite) if finite else math.inf,
            mean_runtime_ms=statistics.mean(runtimes),
            mean_iterations=statistics.mean(iters),
            mean_evaluations=statistics.mean(evals),
            mean_iteration_of_best=statistics.mean(iob),
            optimal_hits=hits,
            trials=trials,
            convergence_curves=curves,
            best_solution=best_solution,
        )
        if verbose:
            print(f"  {name:<5} done in {wall:5.1f}s   "
                  f"mean {summaries[name].mean:.6f}  best {summaries[name].best:.6f}")

    return summaries


def print_table(summaries, optimum=None, budget=None, title=""):
    if title:
        print(f"\n{title}")
    if budget:
        print(budget.describe())
    if optimum is not None and math.isfinite(optimum):
        print(f"exact optimum (brute force) = {optimum:.6f}")

    print("\n" + "-" * 104)
    print(f"{'algorithm':<8}{'best':>11}{'mean':>11}{'worst':>11}{'std':>10}"
          f"{'gap%':>9}{'optimal':>10}{'iters':>8}{'conv@':>8}{'ms':>10}")
    print("-" * 104)

    ranked = sorted(summaries.values(), key=lambda s: s.mean)
    for s in ranked:
        gap = s.gap_vs(optimum)
        gap_txt = f"{gap:+.3f}" if gap is not None else "--"
        opt_txt = f"{s.optimal_hits}/{s.trials}" if optimum is not None else "--"
        print(f"{s.name:<8}{s.best:11.6f}{s.mean:11.6f}{s.worst:11.6f}{s.std:10.6f}"
              f"{gap_txt:>9}{opt_txt:>10}{s.mean_iterations:8.1f}"
              f"{s.mean_iteration_of_best:8.1f}{s.mean_runtime_ms:10.1f}")
    print("-" * 104)

    winner = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None
    if runner_up and math.isfinite(winner.mean) and winner.mean > 0:
        margin = (runner_up.mean / winner.mean - 1) * 100
        print(f"Best mean: {winner.name}, ahead of {runner_up.name} by {margin:.2f}%.")
    print("'conv@' is the mean iteration at which the best solution was found — "
          "lower means faster convergence.")
    return ranked
