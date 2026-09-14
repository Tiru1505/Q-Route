"""
Convergence analysis — iteration vs best fitness, for QPSO, PSO and GA.

This is where a swarm method's behaviour becomes visible: not just WHERE it
ends up, but how fast it gets there and whether it stalls. Two algorithms can
reach similar final values while behaving completely differently, and the curve
is what shows it.

Curves are averaged over all trials, with a shaded band for the spread, because
a single stochastic run tells you nothing reliable.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                      # no display on a build machine
import matplotlib.pyplot as plt            # noqa: E402
import numpy as np                         # noqa: E402

COLORS = {"QPSO": "#e879f9", "PSO": "#2dd4bf", "GA": "#fb923c"}
PLOTS = Path(__file__).resolve().parents[2] / "results" / "plots"


def _pad(curves):
    """Pad early-stopped runs with their final value so trials can be averaged."""
    longest = max(len(c) for c in curves)
    out = np.empty((len(curves), longest))
    for i, c in enumerate(curves):
        out[i, :len(c)] = c
        if len(c) < longest:
            out[i, len(c):] = c[-1]
    return out


def plot_convergence(summaries, optimum=None, title="Convergence", filename=None,
                     logscale=False):
    fig, ax = plt.subplots(figsize=(9, 5.2))

    for name, s in summaries.items():
        if not s.convergence_curves:
            continue
        arr = _pad(s.convergence_curves)
        mean = arr.mean(axis=0)
        lo = np.percentile(arr, 10, axis=0)
        hi = np.percentile(arr, 90, axis=0)
        x = np.arange(len(mean))
        color = COLORS.get(name, "#888")
        ax.plot(x, mean, label=f"{name} (mean of {s.trials})", color=color, lw=2)
        ax.fill_between(x, lo, hi, color=color, alpha=0.13)

    if optimum is not None and np.isfinite(optimum):
        ax.axhline(optimum, color="#34d399", ls="--", lw=1.4,
                   label="exact optimum (brute force)")

    ax.set_xlabel("Iteration")
    ax.set_ylabel("Best fitness so far (lower is better)")
    ax.set_title(title)
    if logscale:
        ax.set_yscale("log")
    ax.legend(frameon=False)
    ax.grid(alpha=0.22)
    fig.tight_layout()

    PLOTS.mkdir(parents=True, exist_ok=True)
    out = PLOTS / (filename or "convergence.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_scalability(rows, filename="scalability.png"):
    """
    Two panels: runtime and solution quality against the number of stops.

    The runtime panel is the one that matters — it shows brute force falling
    off a cliff while the metaheuristics stay flat.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    stops = [r["stops"] for r in rows]

    for name in ("QPSO", "PSO", "GA"):
        ax1.plot(stops, [r[name]["runtime_ms"] for r in rows],
                 marker="o", label=name, color=COLORS[name], lw=2)
    brute = [r.get("brute_ms") for r in rows]
    if any(b for b in brute):
        xs = [s for s, b in zip(stops, brute) if b]
        ys = [b for b in brute if b]
        ax1.plot(xs, ys, marker="s", ls="--", color="#f43f5e",
                 label="brute force (exact)", lw=2)

    ax1.set_xlabel("Number of stops")
    ax1.set_ylabel("Runtime (ms)")
    ax1.set_yscale("log")
    ax1.set_title("Runtime vs problem size")
    ax1.legend(frameon=False)
    ax1.grid(alpha=0.22)

    for name in ("QPSO", "PSO", "GA"):
        gaps = [r[name].get("gap_pct") for r in rows]
        xs = [s for s, g in zip(stops, gaps) if g is not None]
        ys = [g for g in gaps if g is not None]
        if xs:
            ax2.plot(xs, ys, marker="o", label=name, color=COLORS[name], lw=2)

    ax2.axhline(0, color="#34d399", ls="--", lw=1.2, label="exact optimum")
    ax2.set_xlabel("Number of stops")
    ax2.set_ylabel("Mean gap above optimum (%)")
    ax2.set_title("Solution quality vs problem size")
    ax2.legend(frameon=False)
    ax2.grid(alpha=0.22)

    fig.tight_layout()
    PLOTS.mkdir(parents=True, exist_ok=True)
    out = PLOTS / filename
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_boxplot(summaries, optimum=None, filename="distribution.png"):
    """Spread across trials — consistency matters as much as the best result."""
    fig, ax = plt.subplots(figsize=(7.5, 5))
    names, data = [], []
    for name, s in summaries.items():
        curves = s.convergence_curves
        if curves:
            names.append(name)
            data.append([c[-1] for c in curves])

    bp = ax.boxplot(data, labels=names, patch_artist=True, widths=0.55)
    for patch, name in zip(bp["boxes"], names):
        patch.set_facecolor(COLORS.get(name, "#888"))
        patch.set_alpha(0.42)
    for median in bp["medians"]:
        median.set_color("#111")

    if optimum is not None and np.isfinite(optimum):
        ax.axhline(optimum, color="#34d399", ls="--", lw=1.4, label="exact optimum")
        ax.legend(frameon=False)

    ax.set_ylabel("Final fitness (lower is better)")
    ax.set_title("Result distribution across trials")
    ax.grid(alpha=0.22, axis="y")
    fig.tight_layout()

    PLOTS.mkdir(parents=True, exist_ok=True)
    out = PLOTS / filename
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
