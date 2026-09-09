#!/usr/bin/env python
"""
Train an LSTM traffic forecaster on Indian junction data.

WHY THIS AND NOT THE METR-LA MODEL
----------------------------------
METR-LA is Los Angeles freeway speeds. This is an Indian junction counted every
15 minutes for 31 continuous days, and it is a better fit for this project in
two ways:

  1. It is Indian traffic, with the bike-heavy mix Indian roads actually have.
  2. Its features are vehicle COUNTS by class, which is exactly what a YOLO
     detector produces. Counts -> PCU -> density -> Greenshields is the
     pipeline the congestion model already uses, so a forecast here flows
     through machinery that is already built and already defended, instead of
     needing a new set of invented thresholds.

DELIBERATELY LOCATION-BLIND
---------------------------
No junction id, no coordinates, no city are given to the model. It sees only
recent counts and the clock. That is what lets the trained model be applied to
a road it has never seen — the aim is a forecaster for any Indian city, not one
tied to the junction it was fitted on.

The honest limit of that: the model has observed ONE junction over 31 days. It
learns the daily rhythm of Indian traffic, which generalises; it has not been
validated anywhere else, and applying it to another city is an extrapolation,
not a demonstrated result.

THE SPLIT IS BY DAY, NOT RANDOM
-------------------------------
This matters more than anything else in the file. Neighbouring 15-minute rows
are almost identical, so a random split puts near-duplicates on both sides and
reports a score that cannot be reproduced on genuinely unseen time. Days 1-24
train, 25-27 validate, 28-31 test — the model is always predicting a future it
has not seen.

Normalisation statistics come from the training days alone, for the same reason.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import time

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV = ROOT / "data/raw/india/indian_junction_traffic.csv"
OUT = ROOT / "results" / "lstm_india"

COUNTS = ["CarCount", "BikeCount", "BusCount", "TruckCount"]
SITUATIONS = ["low", "normal", "high", "heavy"]
LOOKBACK = 12                       # 3 hours of history
HORIZONS = {"15 min": 1, "30 min": 2, "60 min": 4}
STEPS = 4                           # predict up to +4 steps (60 min)


def load_frame() -> pd.DataFrame:
    df = pd.read_csv(CSV)
    df["minute_of_day"] = (
        pd.to_datetime(df["Time"], format="%I:%M:%S %p").dt.hour * 60
        + pd.to_datetime(df["Time"], format="%I:%M:%S %p").dt.minute
    )
    dow = {d: i for i, d in enumerate(
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])}
    df["dow"] = df["Day of the week"].map(dow)
    df["situation"] = df["Traffic Situation"].str.strip().str.lower().map(
        {s: i for i, s in enumerate(SITUATIONS)})
    return df.sort_values(["Date"]).reset_index(drop=True)


def build_windows(df: pd.DataFrame):
    """Sliding windows over the contiguous series."""
    counts = df[COUNTS].to_numpy("float32")
    # The clock is cyclical: 23:45 is adjacent to 00:00, and a raw 0-1439 value
    # tells the model the opposite. sin/cos keeps that adjacency.
    ang = 2 * np.pi * df["minute_of_day"].to_numpy("float32") / 1440.0
    dang = 2 * np.pi * df["dow"].to_numpy("float32") / 7.0
    clock = np.stack([np.sin(ang), np.cos(ang), np.sin(dang), np.cos(dang)], axis=1)
    sit = df["situation"].to_numpy("int64")
    day = df["Date"].to_numpy()

    X, Yc, Ys, D, last = [], [], [], [], []
    for i in range(LOOKBACK, len(df) - STEPS):
        X.append(np.concatenate([counts[i - LOOKBACK:i], clock[i - LOOKBACK:i]], axis=1))
        Yc.append(counts[i:i + STEPS])          # future counts, 4 steps x 4 classes
        Ys.append(sit[i:i + STEPS])             # future situation class
        D.append(day[i])
        last.append(counts[i - 1])              # persistence baseline
    return (np.asarray(X, "float32"), np.asarray(Yc, "float32"),
            np.asarray(Ys, "int64"), np.asarray(D), np.asarray(last, "float32"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=120)
    ap.add_argument("--hidden", type=int, default=32)
    ap.add_argument("--layers", type=int, default=1)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=8e-4)
    args = ap.parse_args()

    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    torch.manual_seed(0)
    np.random.seed(0)
    OUT.mkdir(parents=True, exist_ok=True)

    df = load_frame()
    X, Yc, Ys, D, last = build_windows(df)
    print(f"windows: {len(X)}  features {X.shape[-1]}  horizon {STEPS} steps")

    tr, va, te = D <= 24, (D >= 25) & (D <= 27), D >= 28
    print(f"  train {tr.sum()} (days 1-24)   val {va.sum()} (25-27)   test {te.sum()} (28-31)")

    # Statistics from the training days only — validation and test must stay unseen.
    mu, sd = X[tr].mean((0, 1)), X[tr].std((0, 1)) + 1e-6
    cmu, csd = Yc[tr].mean((0, 1)), Yc[tr].std((0, 1)) + 1e-6
    Xn = (X - mu) / sd
    Ycn = (Yc - cmu) / csd

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(X.shape[-1], args.hidden, args.layers, batch_first=True)
            self.drop = nn.Dropout(0.3)
            self.count = nn.Linear(args.hidden, STEPS * len(COUNTS))
            self.sit = nn.Linear(args.hidden, STEPS * len(SITUATIONS))

        def forward(self, x):
            h, _ = self.lstm(x)
            h = self.drop(h[:, -1, :])
            return (self.count(h).view(-1, STEPS, len(COUNTS)),
                    self.sit(h).view(-1, STEPS, len(SITUATIONS)))

    model = Net()
    opt = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=8, factor=0.5)
    l1, ce = nn.L1Loss(), nn.CrossEntropyLoss()

    T = lambda a: torch.from_numpy(a)
    loader = DataLoader(TensorDataset(T(Xn[tr]), T(Ycn[tr]), T(Ys[tr])),
                        batch_size=args.batch, shuffle=True)
    Xva, Ycva, Ysva = T(Xn[va]), T(Ycn[va]), T(Ys[va])

    print(f"\ntraining up to {args.epochs} epochs …")
    best, best_state, stale = float("inf"), None, 0
    t0 = time.time()
    for ep in range(1, args.epochs + 1):
        model.train()
        for xb, yc, ys in loader:
            opt.zero_grad()
            pc, ps = model(xb)
            loss = l1(pc, yc) + 0.3 * ce(ps.reshape(-1, len(SITUATIONS)), ys.reshape(-1))
            loss.backward()
            opt.step()

        model.eval()
        with torch.no_grad():
            pc, ps = model(Xva)
            vloss = (l1(pc, Ycva) + 0.3 * ce(ps.reshape(-1, len(SITUATIONS)),
                                             Ysva.reshape(-1))).item()
        sched.step(vloss)
        if vloss < best - 1e-4:
            best, best_state, stale = vloss, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            stale += 1
        if ep % 10 == 0 or ep == 1:
            print(f"  epoch {ep:3d}  val {vloss:.4f}{'  <- best' if vloss <= best else ''}", flush=True)
        if stale >= 30:
            print(f"  early stop at epoch {ep}")
            break

    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        pc, ps = model(T(Xn[te]))
    pred_counts = pc.numpy() * csd + cmu
    pred_sit = ps.numpy().argmax(-1)

    print(f"\ntrained in {(time.time()-t0)/60:.1f} min\n")

    # --- regression: total vehicles, against persistence -------------------
    print("Total vehicles per 15 min — mean absolute error")
    print(f"{'horizon':9s} {'persistence':>12s} {'LSTM':>8s} {'better by':>10s}")
    print("-" * 43)
    report = {}
    truth_all, base_all = Yc[te], last[te]
    for name, h in HORIZONS.items():
        t_tot = truth_all[:, h - 1].sum(1)
        p_tot = pred_counts[:, h - 1].sum(1)
        b_tot = base_all.sum(1)
        naive, mae = float(np.abs(t_tot - b_tot).mean()), float(np.abs(t_tot - p_tot).mean())
        acc = float((pred_sit[:, h - 1] == Ys[te][:, h - 1]).mean())
        report[name] = {"persistence_mae": naive, "lstm_mae": mae,
                        "situation_accuracy": acc}
        print(f"{name:9s} {naive:12.2f} {mae:8.2f} {100*(naive-mae)/naive:9.1f}%")

    # A classifier's accuracy means nothing without knowing what costs nothing.
    # Two free baselines: always say the commonest class, and assume the class
    # does not change. On a slowly-varying series the second is surprisingly
    # strong, and beating it is the only result worth reporting.
    now_class = df["situation"].to_numpy("int64")[LOOKBACK - 1:len(df) - STEPS - 1][te]
    majority = int(np.bincount(Ys[tr].reshape(-1)).argmax())

    print("\nCongestion class - accuracy against free baselines")
    print(f"{'horizon':9s} {'majority':>9s} {'persistence':>12s} {'LSTM':>8s}")
    print("-" * 42)
    for name, h in HORIZONS.items():
        truth = Ys[te][:, h - 1]
        maj = float((truth == majority).mean())
        per = float((truth == now_class).mean())
        acc = report[name]["situation_accuracy"]
        report[name].update({"majority_accuracy": maj, "persistence_accuracy": per})
        print(f"{name:9s} {maj*100:8.1f}% {per*100:11.1f}% {acc*100:7.1f}%")

    torch.save({"state_dict": model.state_dict(), "mu": mu, "sd": sd,
                "cmu": cmu, "csd": csd, "counts": COUNTS,
                "situations": SITUATIONS, "lookback": LOOKBACK, "steps": STEPS,
                "hidden": args.hidden, "layers": args.layers},
               OUT / "india_traffic_lstm.pt")
    (OUT / "metrics.json").write_text(json.dumps({
        "dataset": "Indian junction, 15-min counts, 31 contiguous days",
        "location_blind": True,
        "split": "by day — train 1-24, val 25-27, test 28-31",
        "windows": {"train": int(tr.sum()), "val": int(va.sum()), "test": int(te.sum())},
        "horizons": report,
    }, indent=2))
    print(f"\nsaved {OUT/'india_traffic_lstm.pt'} and metrics.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
