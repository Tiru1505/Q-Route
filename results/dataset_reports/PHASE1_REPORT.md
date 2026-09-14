# Phase 1 — Dataset Inspection Report

Every source inspected on disk before any modelling decision. Machine-readable
stats in `inspection.json`; reproduce with `python backend/scripts/inspect_datasets.py`.

## Verdict summary

| Dataset | Kind | Trainable? | Assigned module |
|---|---|---|---|
| OSM Hyderabad (metro) | graph | no — it *is* the problem instance | Road network |
| OSM Hyderabad (city) | graph | no | Scalability sweeps |
| Mendeley Ahmedabad flow | **documents only** | **no** | Congestion model *(calibration reference)* |
| Indore congestion | tabular | **no — too small** | Congestion model *(threshold sanity check)* |
| IDD Lite | segmentation | yes — **but not for detection** | Vision: road/vehicle occupancy |
| DATS_2022 | detection | yes | Vision: YOLO detection — **not yet downloaded** |
| METR-LA | time series | **yes** | Traffic predictor (primary) |
| PEMS-BAY | time series | **yes** | Traffic predictor (secondary) |
| TomTom Hyderabad | time series | pending | Traffic predictor (fine-tune) — **collecting** |

**Three of your six listed sources cannot do what the spec assigns them.** Details below.

---

## 1. OpenStreetMap — Hyderabad road network ✅

| | Metro | City |
|---|---|---|
| Nodes | 286,603 | 137,046 |
| Edges | 741,203 | 356,420 |
| Road length | 52,309 km | 20,371 km |
| Extent | 63.6 × 61.0 km | 40.5 × 28.2 km |
| Strongly connected | yes | yes |

Road mix (metro): residential 661,216 · tertiary 40,278 · secondary 15,112 ·
unclassified 7,749 · primary 5,322 · living_street 4,653.

**Contains:** geometry, `highway` class, `oneway`, lanes, length, bearing, plus
the derived `free_flow_speed_kph`, `free_flow_time_s`, `capacity_pcu_h`, and the
mutable `congestion` / `current_speed_kph` / `current_time_s` / `road_status`.

**Does NOT contain:** any observed traffic. OSM `maxspeed` is very sparse in
India — most speeds are imputed from `INDIA_URBAN_SPEEDS_KPH`, a documented
assumption, not data.

**Module:** road network (§1) — this is the problem instance every algorithm
solves, not training data.

**Known trap, already fixed.** `graph_from_place("Hyderabad")` returns the city
polygon only and silently excludes RGIA airport, Medchal, Shamirpet and
Patancheru; `nearest_nodes` snaps out-of-bounds destinations to the city edge
and still returns a route. First build gave Secunderabad → RGIA as 20.5 km,
*shorter than the 22.9 km straight line*. Fixed with a metro bbox. All 50
collection points now fall inside, and detour ratios sit at 1.14–1.57.

---

## 2. Mendeley "Data for Traffic Flow Analysis in Emerging Country (India)" ⚠️

**This dataset contains no data.**

The Mendeley record (`2dg8xgw622`) holds exactly one file, `Data in Brief.ZIP`,
2.168 MB, and inside it two Word documents — nothing else. Confirmed against the
Mendeley API across all versions.

| File | Embedded images | EMF chart objects | Data tables | Rows of data |
|---|---|---|---|---|
| COTATU_META_DATA.docx | 20 | 8 | no | **0** |
| Datainbrief_CODATU.docx | 3 | 2 | yes (paper's spec table) | **0** |

The "data" is an appendix of *chart pictures* — k–q curves, k–v curves, volume
and velocity by time zone — rendered as EMF vector images inside a Word file.
There are no numeric rows to parse.

**What it actually documents** (Tsuboi & Yoshikawa, 2019): Ahmedabad, 10 camera
locations, ~1.7 M measurement points over two months (June 2015 appendix),
variables traffic volume q (PCU/h), density k (PCU/km), velocity v (km/h).
VMS #1, #2, #4 missing due to system trouble.

**What it is genuinely worth — and this is not nothing.** The paper supplies:

1. **The fundamental-diagram model form** with named parameters — `vf` free-flow
   speed, `kj` jam density, `kc` critical density, `qc` critical volume, `vc`
   critical speed. That is the functional form the congestion model should use.
2. **A congestion definition**: the ratio of average speed to free speed. This
   independently justifies the `congestion = 1 − v_avg/v_free` formulation
   already used in the TomTom collector, and it is citable.
3. **PCU as the unit of flow**, which is the correct choice for heterogeneous
   Indian traffic.

**Module:** congestion model (§4) — as a *calibration and citation reference*.
**Not** a training set, and not mappable onto Hyderabad roads.

**Assumption to document if you use it:** transferring Ahmedabad fundamental-
diagram parameters to Hyderabad assumes comparable fleet mix and lane
discipline. Defensible for arterials, weak for the old city.

---

## 3. Indore Traffic Congestion Prediction Dataset (Mendeley) ⚠️

```
437 rows · 4 road segments (R1–R4) · 13.1 days · CC BY 4.0
event_log.xlsx   437×4   0 duplicates   spans 13.14 days
ml_dataset.xlsx  437×5  24 duplicates   no usable timestamp column
raw_traffic.xlsx 437×5   0 duplicates   spans 13.14 days
classes: FREE 283 / LIGHT 82 / MODERATE 53 / HEAVY 19
```

Four segments and ~8 irregular observations per road per day is not a time
series. There is no sequence for an LSTM to learn, and 19 HEAVY samples cannot
support a classifier either.

**Module:** congestion model — threshold sanity check only. Its delay→class
cut points are a second opinion on your own thresholds. Nothing more.

*(Correcting my earlier recommendation in `DATA.md`: I suggested this before
inspecting it. Having inspected it, it is not a usable training source.)*

---

## 4. IDD Lite ⚠️ — cannot train the detector the spec describes

```
train  1380 images / 1380 semantic + 1380 instance labels
val     204 images /  204 + 204
test    399 images /    0 labels
image size: 320 × 227 RGB (uniform)
annotation: per-pixel semantic mask (PNG)
bounding boxes: NONE
```

Class presence across 300 sampled frames — **7 coarse classes only**:

| id | class | frames |
|---|---|---|
| 0 | drivable | 100.0% |
| 1 | non-drivable | 63.7% |
| 2 | living things | 95.3% |
| 3 | **vehicles** | 99.7% |
| 4 | road-side objects | 100.0% |
| 5 | far objects | 99.7% |
| 6 | sky | 98.7% |
| 255 | ignore/unlabelled | 61.7% |

**The problem:** §6 asks for detection of cars, buses, trucks, motorcycles,
auto-rickshaws, bicycles, pedestrians and animals as separate classes. IDD Lite
merges *every* vehicle into a single `vehicles` class (id 3) and every person or
animal into `living things` (id 2). There are no boxes, no per-vehicle
instances, and 320×227 is too small for reliable detection anyway. The
`_inst_label.png` files are not true instance IDs — values top out at 6 (class
ids) or 255 (ignore).

**So: IDD Lite cannot train a multi-class vehicle detector, and cannot produce
vehicle *counts*.** Forcing it would mean fabricating labels.

**What it CAN do, and it maps cleanly onto your pipeline.** The `vehicles` mask
gives **road occupancy fraction** directly:

```
occupancy = area(vehicles ∩ drivable) / area(drivable)
```

That is a density measure — arguably a *better* congestion proxy than a vehicle
count, because it is invariant to the vehicle-size heterogeneity that makes
Indian traffic hard to count. It feeds the congestion model at exactly the point
§16 puts vehicle count:

```
frame → segmentation → occupancy fraction → density → congestion → edge weight
```

**Module:** vision — occupancy estimation (not detection). Trainable: yes, for
7-class segmentation. **Licence:** IDD research licence, non-commercial —
attribute IIIT Hyderabad.

---

## 5. DATS_2022 — required for the YOLO module, not yet present ❌

`data/vision/dats_2022` does not exist. This is the **only** source in your list
with real bounding boxes, and it is what §6 actually needs: >10,000 Indian road
images with annotations in Pascal VOC (.xml), YOLO (.txt) and Create ML (.json),
CC BY 4.0, at https://data.mendeley.com/datasets/nfc34n8svj/2

I could not fetch it programmatically — the Mendeley file API returns an empty
listing for this record and the page is a JavaScript app, so it needs a browser
download. **This one is yours to download**, same as the others.

⚠️ **Verify coverage before planning around it.** The Mendeley description says
annotations exist for *"a small set of images"*, which contradicts the "45
classes over 10,000 images" figure that circulates in summaries. Drop it into
`data/vision/dats_2022/` and `backend/scripts/inspect_datasets.py` will report the real
image count, annotation coverage percentage, and per-class box counts before you
commit to training.

---

## 6. METR-LA ✅ and PEMS-BAY ✅ — the only genuinely trainable time series

| | METR-LA | PEMS-BAY |
|---|---|---|
| Shape | 34,272 × 207 sensors | 52,116 × 325 sensors |
| Span | 2012-03-01 → 2012-06-27 | 2017-01-01 → 2017-06-30 |
| Interval | 300 s, perfectly regular | 300 s, perfectly regular |
| Observations | 7,094,304 | 16,937,700 |
| Speed min/mean/max | 0.0 / 53.7 / 70.0 mph | 0.0 / 62.6 / 85.1 mph |
| Zeros (missing sentinel) | **8.09%** | 0.00% |
| NaNs | 0% | 0% |
| Sensor geometry | 207 with lat/lon | 325 with lat/lon |

Both are regular, dense, multi-sensor and long enough for sequence models —
the only sources here that satisfy §5's precondition.

**Preprocessing required:** METR-LA's zeros are a *missing-data sentinel, not
zero speed*. Mask them; do not let them enter the loss or the normaliser.
PEMS-BAY needs no masking.

**Module:** traffic predictor (§5). Train here, report MAE/RMSE against
published DCRNN-era baselines, then transfer the architecture to Hyderabad.

**Honest caveat for the report:** these are US freeway loop detectors. A model
trained on them does not "predict Hyderabad traffic". The defensible claim is
that the *architecture* is validated on standard benchmarks and then fine-tuned
on the collected Hyderabad series.

---

## 7. Effective Area Parameters dataset — not located ❓

Not on disk, and I could not identify a single canonical dataset by that name.
The literature it appears to refer to is the **dynamic-PCU** work, where a
vehicle's PCU is derived from its projected ground area and speed ratio relative
to a standard car:

```
PCU_i = (v_car / v_i) / (A_car / A_i)
```

If that is what you mean, it is **not a dataset you train on** — it is a table
of per-vehicle-type area and speed constants that upgrades your capacity model
from "lanes × per-lane capacity" to a heterogeneity-aware PCU capacity. That
matters here, because `capacity_pcu_h` in the graph currently uses a crude
IRC-style ballpark.

**Please point me at the exact source** (URL or file) and I will inspect it and
wire it in. Until then it is registered but unused — per your instruction not to
use a dataset unnecessarily.

---

## 8. Excluded — `~/Downloads/archive.zip` (3.0 GB) 🚫

Worth flagging since it sits with your other downloads. Contents:

```
TrainData/img   3,799 × .h5   img  (128, 128, 14) float64
TrainData/mask  3,799 × .h5   mask (128, 128)     uint8, values {0,1}
TestData/img      800 × .h5   (no masks)
ValidData/img     245 × .h5   (no masks)
```

Fourteen float bands at 128×128 with binary masks is multispectral satellite
imagery for binary segmentation — Sentinel-2-shaped. **This is a remote-sensing
dataset, not traffic data.** Excluded from the registry. If you downloaded it
expecting IDD, the real IDD Lite is the separate `archive (1).zip`.

---

## What this means for the build

**Unblocked now** — nothing missing:
- §1 road network ✅ done
- §3 synthetic traffic generator (needs only the graph)
- §4 congestion model (Ahmedabad fundamental-diagram form + your own thresholds)
- §8 dynamic edge weights
- §9–§13 QPSO, Dijkstra, PSO, GA, benchmarking, convergence, scalability ✅ **the core contribution**
- §14–§15 rerouting and alerts

**Blocked on you:**
- §6 YOLO detection → download DATS_2022
- §7 → point me at the Effective Area Parameters source
- §5 Hyderabad fine-tuning → start the TomTom collector (`TOMTOM_API_KEY`)

**Reassigned from the original spec:**
- Mendeley Ahmedabad: training data → calibration reference
- Indore: training data → threshold sanity check
- IDD Lite: YOLO detection → occupancy segmentation
- METR-LA / PEMS-BAY: added, because they are the only trainable time series here
