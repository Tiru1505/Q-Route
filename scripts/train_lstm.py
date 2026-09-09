#!/usr/bin/env python
"""
Train an LSTM traffic-speed forecaster on METR-LA.

WHAT THIS PREDICTS, AND WHAT IT DOES NOT
----------------------------------------
METR-LA is 207 loop detectors on Los Angeles freeways, sampled every 5 minutes.
This model learns to predict the speed at those sensors 15, 30 and 60 minutes
ahead from the previous hour of readings.

It does NOT predict Hyderabad congestion, and must never be described as doing
so. The sensors are in California, and their ids do not correspond to anything
in our road graph. What it demonstrates is that the forecasting path works and
is measurable on a recognised public benchmark. Hyderabad ground truth needs
the TomTom collector, which accrues in wall-clock time.

THE DATA IS ALREADY WINDOWED
----------------------------
Each row is one training example: 12 past steps (`x_t-11_d0` .. `x_t+0_d0`) and
12 future steps (`y_t+1_d0` .. `y_t+12_d0`). The `_d1` columns carry time of
day as a fraction, which matters — traffic at 09:00 behaves nothing like 03:00
and the raw speeds alone cannot express that.

MISSING DATA IS ENCODED AS ZERO
-------------------------------
METR-LA marks a dead sensor as 0 mph, not NaN. Training on those teaches the
model to predict zeros, and scoring on them flatters whichever model predicts
low. Both are excluded here, which is what the published baselines do.

THE BASELINE THAT MATTERS
-------------------------
Persistence — "assume the speed does not change" — is the number to beat. A
forecaster that cannot beat it has learned nothing useful, however good its MAE
looks in isolation.
"""

from __future__ import annotations

import argparse
import pathlib
import time

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data/raw/benchmarks/metr-la"
OUT = ROOT / "results" / "lstm"

HORIZONS = {"15 min": 3, "30 min": 6, "60 min": 12}


class SpeedLSTM:
    """Thin wrapper so the training loop reads plainly."""

    def __init__(self, n_features: int, hidden: int = 64, layers: int = 2, horizon: int = 12):
        import torch.nn as nn

        class Net(nn.Module):
            def __init__(self):
                super().__init__()
                self.lstm = nn.LSTM(n_features, hidden, layers,
                                    batch_first=True, dropout=0.1 if layers > 1 else 0.0)
                self.head = nn.Linear(hidden, horizon)

            def forward(self, x):
                out, _ = self.lstm(x)
                return self.head(out[:, -1, :])      # last timestep -> all horizons

        self.net = Net()


def load_split(name: str, rows: int | None, seed: int = 0):
    df = pd.read_parquet(DATA / f"{name}.parquet")
    if rows and rows < len(df):
        df = df.sample(rows, random_state=seed)

    xs = [f"x_t-{i}_d0" for i in range(11, 0, -1)] + ["x_t+0_d0"]
    ts = [f"x_t-{i}_d1" for i in range(11, 0, -1)] + ["x_t+0_d1"]
    ys = [f"y_t+{h}_d0" for h in range(1, 13)]

    speed = df[xs].to_numpy("float32")
    tod = df[ts].to_numpy("float32")
    X = np.stack([speed, tod], axis=-1)          # (n, 12 steps, 2 features)
    y = df[ys].to_numpy("float32")
    return X, y, speed[:, -1]                    # last observed speed = persistence


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=400_000, help="training rows to sample")
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch", type=int, default=512)
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--layers", type=int, default=2)
    ap.add_argument("--lr", type=float, default=1e-3)
    args = ap.parse_args()

    import torch
    from torch.utils.data import DataLoader, TensorDataset

    torch.manual_seed(0)
    OUT.mkdir(parents=True, exist_ok=True)

    print("loading METR-LA …")
    Xtr, ytr, _ = load_split("train", args.rows)
    Xva, yva, va_last = load_split("val", min(args.rows // 4, 120_000))
    Xte, yte, te_last = load_split("test", 150_000)
    print(f"  train {Xtr.shape}  val {Xva.shape}  test {Xte.shape}")

    # Speeds are ~0-70 mph; scaling to roughly unit range keeps the LSTM stable.
    scale = 70.0
    model = SpeedLSTM(2, args.hidden, args.layers).net
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    lossf = torch.nn.L1Loss()          # L1 matches the MAE we report

    loader = DataLoader(
        TensorDataset(torch.from_numpy(Xtr / scale), torch.from_numpy(ytr / scale)),
        batch_size=args.batch, shuffle=True,
    )
    Xva_t = torch.from_numpy(Xva / scale)
    yva_t = torch.from_numpy(yva / scale)

    print(f"\ntraining {args.epochs} epochs on CPU …")
    best, best_state = float("inf"), None
    t0 = time.time()
    for ep in range(1, args.epochs + 1):
        model.train()
        run = 0.0
        for xb, yb in loader:
            opt.zero_grad()
            loss = lossf(model(xb), yb)
            loss.backward()
            opt.step()
            run += loss.item() * len(xb)
        model.eval()
        with torch.no_grad():
            vmae = lossf(model(Xva_t), yva_t).item() * scale
        flag = ""
        if vmae < best:
            best, best_state = vmae, {k: v.clone() for k, v in model.state_dict().items()}
            flag = "  <- best"
        print(f"  epoch {ep:2d}/{args.epochs}   train {run/len(Xtr)*scale:.3f}   "
              f"val MAE {vmae:.3f}{flag}", flush=True)

    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        pred = model(torch.from_numpy(Xte / scale)).numpy() * scale

    print(f"\ntrained in {(time.time()-t0)/60:.1f} min\n")
    print(f"{'horizon':9s} {'persistence':>12s} {'LSTM':>8s} {'better by':>10s}")
    print("-" * 43)
    report = {}
    for name, h in HORIZONS.items():
        truth = yte[:, h - 1]
        ok = truth > 0                       # 0 marks a dead sensor, not traffic
        naive = float(np.abs(truth[ok] - te_last[ok]).mean())
        mae = float(np.abs(truth[ok] - pred[ok, h - 1]).mean())
        rmse = float(np.sqrt(((truth[ok] - pred[ok, h - 1]) ** 2).mean()))
        report[name] = {"persistence_mae": naive, "lstm_mae": mae, "lstm_rmse": rmse}
        print(f"{name:9s} {naive:12.3f} {mae:8.3f} {100*(naive-mae)/naive:9.1f}%")

    torch.save({"state_dict": model.state_dict(), "scale": scale,
                "hidden": args.hidden, "layers": args.layers}, OUT / "metr_la_lstm.pt")
    import json
    (OUT / "metrics.json").write_text(json.dumps({
        "dataset": "METR-LA (Los Angeles freeway loop detectors)",
        "not_hyderabad": True,
        "train_rows": int(len(Xtr)), "epochs": args.epochs,
        "val_mae_best": best, "horizons": report,
    }, indent=2))
    print(f"\nsaved {OUT/'metr_la_lstm.pt'} and metrics.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
