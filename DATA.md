# Data sources

Everything the project trains and runs on, where it came from, and what it is
actually good for. Read the **Verdict** column before you build on anything.

---

## 1. Road network — OpenStreetMap (primary, solved)

| | |
|---|---|
| Source | OpenStreetMap via OSMnx / Overpass |
| Script | `scripts/build_city_graph.py` |
| Output | `data/processed/<slug>/<slug>_drive.graphml` + nodes/edges Parquet |
| Licence | ODbL 1.0 — attribution required ("© OpenStreetMap contributors") |
| Verdict | **Use it.** Complete, free, and the only road-geometry source you need. |

Parameterised by city, so the same pipeline serves Hyderabad, Bengaluru, Delhi:

```bash
python scripts/build_city_graph.py --city "Hyderabad, Telangana, India" --metro
```

Two graphs are built and kept:

| Graph | Nodes | Edges | Road km | Extent | Use |
|---|---|---|---|---|---|
| `hyderabad/` (**--metro**) | 286,603 | 741,203 | 52,309 | 64 × 61 km | **Primary.** ORR, RGIA, Medchal, Patancheru |
| `hyderabad-city/` | 137,046 | 356,420 | 20,371 | 40 × 28 km | Smaller instance for scalability sweeps |

Both are strongly connected, so any ordered (source, destination) pair is solvable.

### ⚠️ `graph_from_place("Hyderabad")` is a trap

Nominatim's Hyderabad polygon is the **city proper**, about 40 × 28 km. It
excludes RGIA airport (Shamshabad), Medchal, Shamirpet, Patancheru, Narsingi
and Bachupally. 7 of the 50 seed collection points fell outside it, up to 9.5 km
away.

The failure is silent and nasty: `nearest_nodes` happily snaps an
out-of-bounds destination to the nearest city-edge node, and you get a route
back. On the first build, Secunderabad → RGIA returned 20.5 km — **shorter than
the 22.9 km straight-line distance**, which is geometrically impossible. That
ratio check is the cheapest way to catch a truncated graph, and it is now part
of the verification.

Fixed by `--metro`, which uses the `METRO_BBOX` presets (ORR + margin).
After the rebuild, all 50 seed points are inside the graph and every route has
a detour ratio between 1.14 and 1.57 — exactly the 1.2–1.5 band you expect for
real urban road networks:

```
Hitec City    -> Charminar       18.8 km road /  13.8 straight (1.36)  19.6 min free-flow
Secunderabad  -> RGIA Airport    31.0 km road /  22.9 straight (1.35)  35.1 min free-flow
Miyapur       -> LB Nagar        30.4 km road /  26.5 straight (1.14)  31.2 min free-flow
Gachibowli    -> Uppal           27.3 km road /  22.7 straight (1.20)  28.5 min free-flow
Patancheru    -> Medchal         39.8 km road /  25.4 straight (1.57)  26.0 min free-flow
Hitec City    -> RGIA Airport    34.1 km road /  23.3 straight (1.47)  28.1 min free-flow
```

**Speed limits are the other catch.** Indian OSM data has very sparse
`maxspeed` tags, so most edges get an imputed speed. `INDIA_URBAN_SPEEDS_KPH`
in the build script overrides OSMnx's Western defaults with values calibrated
for Indian urban roads (primary 45 km/h, not 60). This single dict is the most
important realism knob in the graph — tune it, and say in the report that you did.

**Load the `.pkl`, not the `.graphml`.** GraphML stringifies every attribute
and takes ~47 s to reload at this size; the pickle keeps native floats and
loads in ~8 s. Both are written on every build.

Every edge carries the fields the traffic layer and QPSO fitness expect:

```
length_m  free_flow_speed_kph  free_flow_time_s  capacity_pcu_h  bearing
congestion (0..1)  current_speed_kph  current_time_s  road_status (open|closed|restricted)
```

---

## 2. Traffic time series for model training — open benchmarks

No open traffic time-series exists for any Indian city (see §4). Train and
validate the LSTM/GRU here first, so you can report error metrics against
published baselines instead of against traffic you invented yourself.

| Dataset | Shape | Interval | Period | Verdict |
|---|---|---|---|---|
| **METR-LA** | 207 sensors, LA highways | 5 min | Mar–Jun 2012 | **Primary.** Field standard, noisier, harder |
| **PEMS-BAY** | 325 sensors, Bay Area | 5 min | Jan–May 2017 | **Secondary.** Cleaner, higher baseline scores |

Downloaded to `data/raw/benchmarks/`:

```
metr-la/metr-la.h5                     57.0 MB   raw speed matrix (source of truth)
metr-la/adj_mx.pkl                      0.7 MB   precomputed adjacency
metr-la/train|val|test.parquet        223   MB   pre-windowed (12 steps in), ready to train
metr-la/sensor_graph/sensor_locations.csv        207 sensors with lat/lon
metr-la/sensor_graph/distances.csv               pairwise road-network distances
pems-bay/pems-bay.h5                  135.9 MB
pems-bay/adj_mx_bay.pkl                 1.7 MB
pems-bay/sensor_graph/...                        325 sensors with lat/lon
```

The Parquet splits are pre-windowed into sliding sequences
(`x_t-11_d0 … x_t0_d1`, where `d0` = speed, `d1` = time-of-day). Convenient,
but opinionated — use the `.h5` if you want a different window length.

Note: these were pulled from HuggingFace mirrors (`jimmygao3218/*`,
`witgaw/*`), not Zenodo. **Zenodo returns HTTP 403 for file downloads from
many networks** including this one; `scripts/fetch_benchmarks.sh` uses the
mirrors, which serve byte-identical data.

---

## 3. Hyderabad traffic — you have to collect it yourself

This is the part that cannot be downloaded, and the reason to start now:
data accrues in wall-clock time, not compute time.

| | |
|---|---|
| Source | TomTom Traffic API — Flow Segment Data |
| Script | `scripts/collect_tomtom.py` |
| Seed points | `data/raw/india/hyderabad_segments.csv` — 50 points across 11 corridors |
| Cost | Free tier, ~2,500 requests/day, no credit card |
| Verdict | **The only route to real Hyderabad congestion data.** Start it today. |

Each poll returns `currentSpeed`, `freeFlowSpeed`, `currentTravelTime`,
`freeFlowTravelTime`, `confidence`, `roadClosure` — from which the collector
derives `congestion_ratio` (0 = free flow, 1 = stopped), which is exactly what
the dynamic edge-weight layer consumes.

```bash
setx TOMTOM_API_KEY "your-key"                  # once, from developer.tomtom.com
python scripts/collect_tomtom.py --once         # smoke test
python scripts/collect_tomtom.py --interval 900 --start-hour 6 --end-hour 22
```

**Budget arithmetic.** 2,500 requests/day ÷ polls-per-day = segments you can
afford. At 15-minute intervals over a 16-hour window that's 64 polls/day, so
~39 segments. The script prints the budget and warns if you exceed it. Use
`--limit` to trim the seed list.

Four weeks of this gives you a genuine Hyderabad traffic series with real
diurnal and weekday/weekend structure. Nobody else in the competition will
have one.

HERE and Mapbox have comparable free tiers — register backup keys.

---

## 4. Indian open data — what exists, and what it's worth

### Indore congestion dataset (Mendeley) — downloaded, but **do not train on it**

`data/raw/india/indore-congestion/` — CC BY 4.0, three XLSX files.

I recommended this earlier as the one useful tabular Indian dataset. Having
pulled and inspected it, that was wrong, and the correction matters:

```
rows            437
road segments   4          (R1, R2, R3, R4)
time span       13 days    (2026-01-26 -> 2026-02-08)
sampling        irregular, ~8 observations per road per day
classes         FREE 283 / LIGHT 82 / MODERATE 53 / HEAVY 19
columns         road_id, hour, day, delay, congestion
```

Four road segments and 437 irregularly-spaced observations is not a time
series. It cannot train an LSTM — there is no sequence to learn. Its only
honest uses are as a sanity check on your congestion-class thresholds, or as a
cited example of how thin Indian open traffic data actually is.

Every other "Indian traffic dataset" on Mendeley is **image data for computer
vision** — DATS_2022, Indistreet2K25, Indian Traffic VQA. Useful only if you
build the optional YOLO layer; useless for flow prediction. The project spec's
assumption that a Mendeley Indian traffic-flow dataset exists does not hold.

### Telangana Open Data Portal — `data.telangana.gov.in`

One of India's better state portals, updated monthly. Has RTA vehicle
registration and online-sales data (useful for realistic fleet composition in
SUMO) and GTFS for HMRL Metro and MMTS via an email-request form.

⚠️ The dataset listed as *"Hyderabad Domestic Traffic Data 2017"* is airport
passenger traffic, not road traffic. Do not build on the title alone.

### HMDA Comprehensive Transportation Study — calibration ground truth

The 2011 CTS (consultants: LEA Associates South Asia) ran exactly the surveys
you need: traffic volume counts at mid-blocks *and* intersections, speed-and-
delay studies, road inventory, across Secunderabad, Mehdipatnam, Kukatpally,
Vanasthalipuram and Malkajgiri. Published junction volumes: three-arm
2,470–76,193 PCU/12h, four-arm 5,810–74,705 PCU/12h.

Dated and PDF-bound. An earlier version of this file suggested the report say
*"synthetic peak-hour volumes are calibrated to HMDA CTS observed PCU ranges"*.
Do not: nothing fits the simulator to these figures, and measured against them
(`scripts/measure_simulated_volumes.py`) it runs high. What the report can say:

> Simulated junction volumes — median 53,957 PCU/12h at three-arm and 59,366
> at four-arm junctions — fall inside the range the HMDA CTS observed at 93%
> and 85% of junctions respectively. They sit toward the busy end, exceed the
> observed maximum at 7% and 15%, and include none as quiet as the quietest
> junction observed.

That is a plausibility check on magnitude, not a calibration. The CTS also
published mid-block counts, which would be the right comparison for per-road
volumes; only the junction ranges above are to hand.

- https://www.hmda.gov.in/cts/
- UMTA Hyderabad operations document (MoHUA) — contains CTS survey summaries

### Uber Movement — dead

Had zone-to-zone travel times for several Indian cities and is cited in many
older tutorials. **Discontinued.** Only archived mirrors remain. Don't build
on it.

---

## 5. Synthetic and simulated traffic

Two distinct things, and the distinction matters in the report:

| | Purpose |
|---|---|
| **Synthetic layer** (`traffic/` module, to build) | Controlled, reproducible scenarios — the 8 test cases: peak hour, sudden congestion, road closure, etc. Calibrated to HMDA PCU ranges. |
| **SUMO** (Eclipse, optional) | Microscopic simulation on the real OSM network with ground-truth flows. The legitimate way to generate 5k/10k-node scalability experiments. |

Synthetic traffic is not a weakness *provided you say so plainly*. The
contribution is the optimiser, not the data feed. What would be a weakness is
training a predictor on traffic you generated and reporting its accuracy as
evidence about the real world.

---

## ⚠️ Licensing — read before adding a source

**Do not train on or store Google Maps data.** The Distance Matrix / Routes
APIs return excellent traffic-aware durations, and the Terms of Service
prohibit storing, caching, or using them to create derived datasets or train
models. In a competition submission this is a real disqualification risk, not
a theoretical one.

| Source | Licence | Attribution required |
|---|---|---|
| OpenStreetMap | ODbL 1.0 | Yes — "© OpenStreetMap contributors" |
| METR-LA / PEMS-BAY | Research use, from Caltrans PeMS | Cite Li et al. 2018 (DCRNN) |
| Indore congestion | CC BY 4.0 | Yes |
| TomTom free tier | Developer ToS — check current terms for redistribution | Yes |
| Google Maps | **Prohibited for this use** | — |

---

## Reproducing everything

```bash
bash scripts/fetch_benchmarks.sh                              # METR-LA + PEMS-BAY
python scripts/build_city_graph.py --city "Hyderabad, Telangana, India"
python scripts/collect_tomtom.py --once                       # needs TOMTOM_API_KEY
```
