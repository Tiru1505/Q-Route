"""
Build your own real traffic time-series for an Indian city, one poll at a time.

No open historical traffic dataset exists for Hyderabad (or any Indian city).
The only way to get real congestion data is to collect it yourself. This polls
TomTom's Flow Segment Data endpoint on a fixed list of road points and appends
every observation to a Parquet dataset partitioned by date.

    setx TOMTOM_API_KEY "your-key"          # Windows, once
    python scripts/collect_tomtom.py --once            # smoke test
    python scripts/collect_tomtom.py --interval 900    # run forever, 15-min polls

Get a free key at https://developer.tomtom.com (free tier ~2,500 requests/day,
no credit card). Budget:  2500 / (86400/interval) = max segments you can poll.
    interval=900s (15 min) -> 96 polls/day -> ~26 segments continuously
    interval=900s, 06:00-22:00 only        -> ~39 segments
Use --start-hour/--end-hour to spend the budget on waking hours only.

Every row is one (segment, timestamp) observation:
    ts_utc, ts_local, name, corridor, lat, lon, frc,
    current_speed_kph, free_flow_speed_kph, current_travel_time_s,
    free_flow_travel_time_s, confidence, road_closure,
    congestion_ratio, speed_ratio

congestion_ratio is the field the dynamic edge-weight layer consumes:
    0.0 = free flow, 1.0 = fully stopped.
"""
import argparse
import datetime as dt
import os
import random
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ENDPOINT = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/{zoom}/json"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def poll_one(session, key, lat, lon, zoom=10, timeout=20):
    """Return a dict of flow fields for one point, or None on failure."""
    try:
        r = session.get(
            ENDPOINT.format(zoom=zoom),
            params={"key": key, "point": "%s,%s" % (lat, lon), "unit": "KMPH"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return {"error": "request:%s" % type(exc).__name__}

    if r.status_code == 403:
        return {"error": "403-forbidden (bad or over-quota key)"}
    if r.status_code == 429:
        return {"error": "429-rate-limited"}
    if r.status_code != 200:
        return {"error": "http-%d" % r.status_code}

    try:
        fsd = r.json()["flowSegmentData"]
    except (ValueError, KeyError):
        return {"error": "unparseable-body"}

    cur = fsd.get("currentSpeed")
    free = fsd.get("freeFlowSpeed")
    cur_t = fsd.get("currentTravelTime")
    free_t = fsd.get("freeFlowTravelTime")

    speed_ratio = (cur / free) if (cur and free) else None
    return {
        "frc": fsd.get("frc"),
        "current_speed_kph": cur,
        "free_flow_speed_kph": free,
        "current_travel_time_s": cur_t,
        "free_flow_travel_time_s": free_t,
        "confidence": fsd.get("confidence"),
        "road_closure": fsd.get("roadClosure"),
        "speed_ratio": speed_ratio,
        # 0 = free flow, 1 = stopped. Clamped because TomTom occasionally
        # reports current > free-flow on quiet motorway segments.
        "congestion_ratio": None if speed_ratio is None
        else max(0.0, min(1.0, 1.0 - speed_ratio)),
        "error": None,
    }


def sweep(segments, key, zoom, jitter=0.25):
    """Poll every segment once; return a DataFrame of observations."""
    now = dt.datetime.now(dt.timezone.utc)
    rows, session = [], requests.Session()
    ok = fail = 0
    for seg in segments.itertuples(index=False):
        obs = poll_one(session, key, seg.lat, seg.lon, zoom=zoom)
        if obs.get("error"):
            fail += 1
            if "403" in str(obs["error"]) or "429" in str(obs["error"]):
                print("[stop] %s -- halting sweep" % obs["error"], file=sys.stderr)
                break
        else:
            ok += 1
        rows.append(dict(
            ts_utc=now,
            ts_local=now.astimezone(IST),
            name=seg.name,
            corridor=getattr(seg, "corridor", None),
            lat=seg.lat, lon=seg.lon,
            **obs,
        ))
        # Space requests out slightly; avoids tripping burst limits.
        time.sleep(random.uniform(0, jitter))
    print("[sweep] %s  ok=%d fail=%d" % (now.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"), ok, fail))
    return pd.DataFrame(rows)


def append(df, out_dir):
    """Append-only, one Parquet file per local date. Safe to interrupt."""
    if df.empty:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    day = df["ts_local"].iloc[0].strftime("%Y-%m-%d")
    path = out_dir / ("date=%s.parquet" % day)
    if path.exists():
        df = pd.concat([pd.read_parquet(path), df], ignore_index=True)
    df.to_parquet(path, index=False)
    print("[write] %d rows -> %s (%d total)" % (len(df), path, len(df)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", default="data/raw/india/hyderabad_segments.csv")
    ap.add_argument("--out", default="data/raw/india/tomtom_hyderabad")
    ap.add_argument("--interval", type=int, default=900, help="seconds between sweeps")
    ap.add_argument("--zoom", type=int, default=10)
    ap.add_argument("--limit", type=int, default=None, help="only poll first N segments")
    ap.add_argument("--start-hour", type=int, default=0, help="IST hour to start polling")
    ap.add_argument("--end-hour", type=int, default=24, help="IST hour to stop polling")
    ap.add_argument("--once", action="store_true", help="single sweep then exit")
    args = ap.parse_args()

    key = os.environ.get("TOMTOM_API_KEY")
    if not key:
        sys.exit("TOMTOM_API_KEY is not set. Get a free key at "
                 "https://developer.tomtom.com then:  setx TOMTOM_API_KEY \"your-key\"")

    segments = pd.read_csv(args.segments)
    if args.limit:
        segments = segments.head(args.limit)

    polls_per_day = 86400 / args.interval * ((args.end_hour - args.start_hour) / 24)
    budget = len(segments) * polls_per_day
    print("[plan]  %d segments x %.0f polls/day = %.0f requests/day (free tier = 2500)"
          % (len(segments), polls_per_day, budget))
    if budget > 2500:
        print("[warn]  over the free-tier budget. Reduce --limit, or raise --interval, "
              "or narrow --start-hour/--end-hour.")

    out_dir = Path(args.out)
    if args.once:
        append(sweep(segments, key, args.zoom), out_dir)
        return

    print("[run]   polling every %ds, %02d:00-%02d:00 IST. Ctrl-C to stop."
          % (args.interval, args.start_hour, args.end_hour))
    while True:
        hour = dt.datetime.now(IST).hour
        if args.start_hour <= hour < args.end_hour:
            try:
                append(sweep(segments, key, args.zoom), out_dir)
            except Exception as exc:                      # never let the loop die
                print("[error] sweep failed: %r" % exc, file=sys.stderr)
        else:
            print("[idle]  %02d:00 IST outside collection window" % hour)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
