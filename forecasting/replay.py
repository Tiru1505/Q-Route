"""
Replay of held-out traffic, so the forecaster has something real to forecast.

WHY REPLAY RATHER THAN LIVE DATA
--------------------------------
The model needs three hours of recent vehicle counts for whichever road it is
asked about. The app has that for no road: the routing graph carries simulated
congestion, not counted vehicles over time, and there is no camera feed yet.

Three ways to fill that gap, and only one is honest:

  replay held-out days   the model predicts days 28-31, which it never saw in
                         training, and the real outcome is known — so the app
                         can show forecast and truth side by side. This is what
                         this module does.
  a camera through YOLO  the real pipeline, and the eventual answer, but it
                         needs three hours of footage before a first forecast.
  the traffic simulator  rejected. congestion_model can invert congestion back
                         into vehicle counts, so this would be easy to wire and
                         would look like it worked — but the model would be
                         forecasting the output of our own equation. That is
                         circular, and it would not survive being asked what
                         the model was trained on.

WHAT "NOW" MEANS HERE
---------------------
Replay advances on the wall clock so the dashboard moves while you watch it:
one 15-minute traffic step every `SECONDS_PER_STEP` real seconds, wrapping at
the end of the held-out period. Nothing about the data is invented — only the
choice of which real moment to call "now".
"""

from __future__ import annotations

import pathlib
import time

import numpy as np
import pandas as pd

from forecasting.model import COUNTS, LOOKBACK, SITUATIONS, STEPS, pcu_of

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV = ROOT / "data/raw/india/indian_junction_traffic.csv"

# Days 28-31 were held out of training and validation entirely.
TEST_DAYS = (28, 31)
SECONDS_PER_STEP = 6.0

_DOW = {d: i for i, d in enumerate(
    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])}


class ReplaySource:
    """The held-out days, addressable by step."""

    def __init__(self, csv: pathlib.Path | None = None):
        path = pathlib.Path(csv or CSV)
        if not path.exists():
            raise FileNotFoundError(f"No traffic series at {path}")

        df = pd.read_csv(path)
        t = pd.to_datetime(df["Time"], format="%I:%M:%S %p")
        df["minute_of_day"] = t.dt.hour * 60 + t.dt.minute
        df["dow"] = df["Day of the week"].map(_DOW)
        df["situation"] = (df["Traffic Situation"].str.strip().str.lower()
                           .map({s: i for i, s in enumerate(SITUATIONS)}))
        self.df = df.reset_index(drop=True)

        # A cursor may sit anywhere that leaves a full history behind it and a
        # full horizon ahead, and whose "now" falls inside the held-out days.
        lo, hi = TEST_DAYS
        day = self.df["Date"].to_numpy()
        valid = [i for i in range(LOOKBACK, len(self.df) - STEPS)
                 if lo <= day[i - 1] <= hi]
        if not valid:
            raise ValueError("no held-out window available in this series")
        self.cursors = valid
        self._t0 = time.monotonic()

    # ------------------------------------------------------------ position
    def auto_cursor(self) -> int:
        """Which held-out moment is 'now', advanced by the wall clock."""
        elapsed = time.monotonic() - self._t0
        return self.cursors[int(elapsed / SECONDS_PER_STEP) % len(self.cursors)]

    def resolve(self, offset: int | None) -> int:
        if offset is None:
            return self.auto_cursor()
        return self.cursors[offset % len(self.cursors)]

    # ------------------------------------------------------------ windows
    def history(self, cursor: int):
        """The 12 steps the model consumes, plus what they looked like."""
        window = self.df.iloc[cursor - LOOKBACK:cursor]
        counts = window[COUNTS].to_numpy("float32")
        clock = np.stack([
            window["minute_of_day"].to_numpy("float32"),
            window["dow"].to_numpy("float32"),
        ], axis=-1)
        return counts, clock, window

    def truth(self, cursor: int) -> list[dict]:
        """
        What actually happened next.

        Available only because this is replay of recorded data — it is what
        makes the forecast checkable on screen rather than merely plausible.
        """
        out = []
        for i in range(STEPS):
            row = self.df.iloc[cursor + i]
            out.append({
                "minutesAhead": (i + 1) * 15,
                "pcu": round(pcu_of(row[COUNTS].to_numpy("float32")), 1),
                "situation": SITUATIONS[int(row["situation"])],
                "total": int(row["Total"]),
            })
        return out

    def clock_label(self, cursor: int) -> dict:
        row = self.df.iloc[cursor - 1]
        return {
            "time": str(row["Time"]),
            "day": str(row["Day of the week"]),
            "dayOfMonth": int(row["Date"]),
        }
