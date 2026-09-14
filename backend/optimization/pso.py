"""
Particle Swarm Optimization — the direct comparator for QPSO.

WHY THIS IS THE MOST IMPORTANT BASELINE
---------------------------------------
Dijkstra answers "is our optimiser finding good routes?". PSO answers the
question the project is actually about: "does the QUANTUM-INSPIRED variant
help?" QPSO and PSO differ in exactly one thing — how a particle moves — so any
difference in results is attributable to that and nothing else.

THE CLASSICAL UPDATE
--------------------
    v = w*v + c1*r1*(pbest - x) + c2*r2*(gbest - x)
    x = x + v

    w   inertia weight, decayed 0.9 -> 0.4 across the run
    c1  cognitive pull, toward this particle's own best
    c2  social pull, toward the swarm's best

Contrast with QPSO, which has NO velocity term at all: it samples a new
position directly from a probability cloud. That is the entire difference, and
it is why PSO needs three tuned parameters where QPSO needs one.

The known weakness this exposes: because PSO moves in steps, a particle must
traverse worse regions to reach a better basin. On a multimodal landscape —
and tour ordering is intensely multimodal, since swapping two stops usually
makes things worse before it makes them better — the swarm tends to collapse
onto whichever optimum it found first.

FAIRNESS
--------
Same problem object, same encoding, same evaluation budget as QPSO and GA.
Parameters are the standard textbook values (Shi & Eberhart), not values tuned
to make PSO look bad.
"""
import math
import time
from dataclasses import dataclass

import numpy as np

from optimization.problem import RunStats


@dataclass
class PSOConfig:
    n_particles: int = 40
    max_iterations: int = 120
    w_start: float = 0.9          # standard Shi & Eberhart decay
    w_end: float = 0.4
    c1: float = 1.49445           # standard constriction values
    c2: float = 1.49445
    v_max: float = 0.25           # fraction of the [0,1] range per step
    stagnation_limit: int = 80
    seed: int = 42

    def inertia(self, iteration):
        if self.max_iterations <= 1:
            return self.w_end
        t = iteration / (self.max_iterations - 1)
        return self.w_start + (self.w_end - self.w_start) * t


class PSO:
    def __init__(self, problem, config=None):
        self.problem = problem
        self.cfg = config or PSOConfig()
        self.D = problem.dimensions

    def run(self, seed=None, verbose=False):
        cfg = self.cfg
        rng = np.random.default_rng(cfg.seed if seed is None else seed)
        t0 = time.perf_counter()

        X = rng.random((cfg.n_particles, self.D))
        V = rng.uniform(-cfg.v_max, cfg.v_max, (cfg.n_particles, self.D))

        pbest = X.copy()
        pbest_fitness = np.full(cfg.n_particles, math.inf)
        gbest = X[0].copy()
        gbest_fitness = math.inf
        gbest_solution = None
        iteration_of_best = 0

        convergence, mean_fitness = [], []
        evaluations = 0
        stagnant = 0

        for iteration in range(cfg.max_iterations):
            improved = False
            iter_fitness = np.empty(cfg.n_particles)

            for i in range(cfg.n_particles):
                res = self.problem.evaluate(X[i])
                evaluations += 1
                iter_fitness[i] = res.fitness

                if res.fitness < pbest_fitness[i]:
                    pbest_fitness[i] = res.fitness
                    pbest[i] = X[i].copy()
                if res.fitness < gbest_fitness:
                    gbest_fitness = res.fitness
                    gbest = X[i].copy()
                    gbest_solution = res.solution
                    iteration_of_best = iteration
                    improved = True

            convergence.append(gbest_fitness)
            finite = iter_fitness[np.isfinite(iter_fitness)]
            mean_fitness.append(float(finite.mean()) if len(finite) else math.inf)

            stagnant = 0 if improved else stagnant + 1
            if stagnant >= cfg.stagnation_limit:
                break

            w = cfg.inertia(iteration)
            r1 = rng.random((cfg.n_particles, self.D))
            r2 = rng.random((cfg.n_particles, self.D))
            V = (w * V
                 + cfg.c1 * r1 * (pbest - X)
                 + cfg.c2 * r2 * (gbest - X))
            np.clip(V, -cfg.v_max, cfg.v_max, out=V)
            X = X + V

            # Reflect at the boundary, matching QPSO's handling so neither
            # algorithm gains an edge from how it treats the box edges.
            X = np.where(X < 0.0, -X, X)
            X = np.where(X > 1.0, 2.0 - X, X)
            np.clip(X, 0.0, 1.0, out=X)

            if verbose and iteration % 20 == 0:
                print(f"  PSO iter {iteration:3d}  best {gbest_fitness:.6f}  w {w:.2f}")

        return RunStats(
            algorithm="PSO",
            best_fitness=gbest_fitness,
            best_vector=gbest,
            best_solution=gbest_solution,
            convergence=convergence,
            mean_fitness=mean_fitness,
            evaluations=evaluations,
            iterations=len(convergence),
            iteration_of_best=iteration_of_best,
            runtime_ms=(time.perf_counter() - t0) * 1000,
        )
