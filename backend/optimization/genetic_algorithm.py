"""
Genetic Algorithm — the second metaheuristic baseline.

A different search philosophy from the swarm methods. PSO and QPSO keep a
population that MOVES through the space; a GA keeps a population that BREEDS,
recombining pieces of good solutions and occasionally mutating them.

COMPONENTS (all required by the project brief)
---------------------------------------------
    population      random keys in [0,1]^D, same encoding as QPSO and PSO
    selection       tournament, size 3 — standard, and keeps selection pressure
                    independent of how fitness values are scaled
    crossover       BLX-alpha blend, which is the natural real-valued analogue
                    of one-point crossover and preserves the random-key
                    representation
    mutation        Gaussian perturbation per gene, at a fixed rate
    elitism         the best few individuals pass through untouched, so the
                    best-so-far can never get worse

WHY BLX-alpha RATHER THAN ORDER CROSSOVER
-----------------------------------------
A tour GA would normally use a permutation-specific operator such as OX or PMX.
We deliberately do not: those operate on permutations directly, which would
give the GA a DIFFERENT search space from QPSO and PSO and make the comparison
meaningless. Keeping every algorithm on identical random keys is worth more
than giving the GA a specialised operator.

Parameters are standard textbook values, not tuned to disadvantage the GA.
"""
import math
import time
from dataclasses import dataclass

import numpy as np

from optimization.problem import RunStats


@dataclass
class GAConfig:
    population_size: int = 40
    max_generations: int = 120
    crossover_rate: float = 0.85
    mutation_rate: float = 0.15      # per gene
    mutation_sigma: float = 0.15
    tournament_size: int = 3
    elite_count: int = 2
    blx_alpha: float = 0.5
    stagnation_limit: int = 80
    seed: int = 42


class GeneticAlgorithm:
    def __init__(self, problem, config=None):
        self.problem = problem
        self.cfg = config or GAConfig()
        self.D = problem.dimensions

    def _tournament(self, fitness, rng):
        idx = rng.integers(0, len(fitness), self.cfg.tournament_size)
        return idx[np.argmin(fitness[idx])]

    def _crossover(self, a, b, rng):
        """BLX-alpha: sample each gene from an interval spanning both parents."""
        lo = np.minimum(a, b)
        hi = np.maximum(a, b)
        span = hi - lo
        low = lo - self.cfg.blx_alpha * span
        high = hi + self.cfg.blx_alpha * span
        child = rng.uniform(low, high)
        return np.clip(child, 0.0, 1.0)

    def _mutate(self, individual, rng):
        mask = rng.random(self.D) < self.cfg.mutation_rate
        if mask.any():
            individual = individual.copy()
            individual[mask] += rng.normal(0.0, self.cfg.mutation_sigma, mask.sum())
            np.clip(individual, 0.0, 1.0, out=individual)
        return individual

    def run(self, seed=None, verbose=False):
        cfg = self.cfg
        rng = np.random.default_rng(cfg.seed if seed is None else seed)
        t0 = time.perf_counter()

        population = rng.random((cfg.population_size, self.D))
        fitness = np.full(cfg.population_size, math.inf)
        solutions = [None] * cfg.population_size

        best_fitness = math.inf
        best_vector = population[0].copy()
        best_solution = None
        iteration_of_best = 0

        convergence, mean_fitness = [], []
        evaluations = 0
        stagnant = 0

        for generation in range(cfg.max_generations):
            improved = False
            for i in range(cfg.population_size):
                res = self.problem.evaluate(population[i])
                evaluations += 1
                fitness[i] = res.fitness
                solutions[i] = res.solution
                if res.fitness < best_fitness:
                    best_fitness = res.fitness
                    best_vector = population[i].copy()
                    best_solution = res.solution
                    iteration_of_best = generation
                    improved = True

            convergence.append(best_fitness)
            finite = fitness[np.isfinite(fitness)]
            mean_fitness.append(float(finite.mean()) if len(finite) else math.inf)

            stagnant = 0 if improved else stagnant + 1
            if stagnant >= cfg.stagnation_limit:
                break

            # --- elitism: carry the best through unchanged ---------------
            order = np.argsort(fitness)
            next_gen = [population[i].copy() for i in order[:cfg.elite_count]]

            # --- selection, crossover, mutation --------------------------
            while len(next_gen) < cfg.population_size:
                p1 = population[self._tournament(fitness, rng)]
                p2 = population[self._tournament(fitness, rng)]
                child = (self._crossover(p1, p2, rng)
                         if rng.random() < cfg.crossover_rate else p1.copy())
                next_gen.append(self._mutate(child, rng))

            population = np.array(next_gen)

            if verbose and generation % 20 == 0:
                print(f"  GA  gen {generation:3d}  best {best_fitness:.6f}")

        return RunStats(
            algorithm="GA",
            best_fitness=best_fitness,
            best_vector=best_vector,
            best_solution=best_solution,
            convergence=convergence,
            mean_fitness=mean_fitness,
            evaluations=evaluations,
            iterations=len(convergence),
            iteration_of_best=iteration_of_best,
            runtime_ms=(time.perf_counter() - t0) * 1000,
        )
