# Dataset links — every source this project needs

Status legend: ✅ already on disk · ⬇ download needed · 🔑 free registration required
· ❓ unresolved

---

## 1. Road network — Module §1

| Source | Link | Status |
|---|---|---|
| **OpenStreetMap via OSMnx** | no manual download — `python backend/preprocessing/osm_processor.py --metro` | ✅ built |
| Geofabrik India extract (bulk/offline alternative) | https://download.geofabrik.de/asia/india.html | optional |
| Overpass Turbo (ad-hoc queries) | https://overpass-turbo.eu/ | optional |

Licence ODbL 1.0 — attribute "© OpenStreetMap contributors".

---

## 2. Traffic time series — Module §5 (the LSTM/GRU)

These are the **only genuinely trainable time series** available. Nothing
comparable exists for any Indian city.

| Dataset | Link | Status |
|---|---|---|
| **METR-LA** (207 sensors, 5-min, 2012) | https://huggingface.co/datasets/jimmygao3218/METRLA | ✅ downloaded |
| **PEMS-BAY** (325 sensors, 5-min, 2017) | https://huggingface.co/datasets/jimmygao3218/PEMSBAY | ✅ downloaded |
| Same, with sensor lat/lon + distances | https://huggingface.co/datasets/witgaw/METR-LA · https://huggingface.co/datasets/witgaw/PEMS-BAY | ✅ downloaded |
| Zenodo original (CSV) | https://zenodo.org/records/5146275 | ⚠️ 403s file downloads from many networks |
| DCRNN reference repo | https://github.com/liyaguang/DCRNN | reference |
| PeMS raw source (register, free) | https://pems.dot.ca.gov/ | 🔑 optional |
| LargeST (8,600 CA sensors, 2017–2021) | https://github.com/liuxu77/LargeST | optional, for scale |

Other open agencies if you want more: [Chicago Traffic
Tracker](https://data.cityofchicago.org/Transportation/Chicago-Traffic-Tracker-Historical-Congestion-Esti/77hq-huss)
· [UK National Highways WebTRIS](https://webtris.nationalhighways.co.uk/)

---

## 3. Real Hyderabad traffic — self-collection (Module §5 fine-tune)

No open dataset exists. You collect it. Free tiers, no credit card:

| Provider | Link | Notes |
|---|---|---|
| **TomTom** (recommended) | https://developer.tomtom.com/ | ~2,500 req/day. Flow Segment Data returns current + free-flow speed |
| HERE | https://developer.here.com/ | backup key |
| Mapbox | https://account.mapbox.com/ | backup key |
| ~~Uber Movement~~ | — | **discontinued**, only archives remain |

🚫 **Google Maps Platform is excluded.** Its ToS prohibits storing, caching or
deriving datasets from its traffic responses — a real disqualification risk.

Collector is written and waiting on a key: `backend/scripts/collect_tomtom_hyderabad.py`

---

## 4. Vision — object detection (Module §6, YOLO)

Ranked by how well they actually serve this project.

| Dataset | Size / classes | Link | Status |
|---|---|---|---|
| **DriveIndia** ⭐ best | 66,986 images, **YOLO format**, 24 classes, fog/rain/night | https://tihan.iith.ac.in/tiand-datasets/ · paper https://arxiv.org/abs/2507.19912 | ⬇ |
| **IDD-Detection** | 31,569 train + 10,225 val, instance masks → boxes | https://idd.insaan.iiit.ac.in/ | 🔑 |
| **DATS_2022** | >10,000 images; XML + YOLO + JSON | https://data.mendeley.com/datasets/nfc34n8svj/2 | ⬇ |
| IITM-HeTra | 1,417 frames, 6,319 vehicles, Chennai | https://www.kaggle.com/datasets/deepak242424/iitmhetra | ⬇ small but clean |
| Indistreet2K25 | ~5,000 images, weather variety | https://data.mendeley.com/datasets/s5hm86nyn6/1 | optional |
| ITD (Indian Traffic Dataset) | — | https://github.com/teg-iitr/ITD-Indian-traffic-dataset | optional |

**Recommendation: DriveIndia.** It is YOLO-native (no conversion), 6× larger
than DATS_2022, covers adverse weather, publishes a mAP50 = 78.7% baseline you
can compare against, and comes from TiHAN at IIT Hyderabad — so its scenes match
your target city. DATS_2022's own Mendeley page says annotations cover only
*"a small set of images"*, which is why it is third here despite the spec naming it.

Drop whichever you pick into `data/vision/<name>/` and run
`python backend/scripts/inspect_datasets.py` — it reports real image count, annotation
coverage %, and per-class box counts before you commit to training.

---

## 5. Vision — segmentation (Module §6 alternate: occupancy)

| Dataset | Link | Status |
|---|---|---|
| **IDD Lite** (7 coarse classes, 320×227) | https://www.kaggle.com/datasets/sayantandas30011998/indian-driving-dataset-lite | ✅ on disk |
| IDD full segmentation (26 classes) | https://idd.insaan.iiit.ac.in/ | 🔑 |

IDD Lite merges every vehicle into one class and has no boxes — it **cannot**
train a multi-class detector. It *can* give road occupancy fraction, which feeds
the congestion model directly. See the Phase 1 report.

---

## 6. Calibration references — Module §4 / §7 (not training data)

| Source | Link | Use |
|---|---|---|
| **Ahmedabad flow analysis** (Tsuboi & Yoshikawa 2019) | https://data.mendeley.com/datasets/2dg8xgw622/1 | ✅ on disk. Fundamental-diagram form (vf, kj, kc, qc, vc) + speed-ratio congestion definition. **Contains no data rows** |
| Indore congestion | https://data.mendeley.com/datasets/3dng3j76y9/1 | ✅ on disk. Threshold sanity check only (4 roads, 437 rows) |
| IRC:106-1990 — urban road capacity | https://archive.org/details/gov.in.irc.106.1990 | PCU capacity per road class |
| IRC:64-1990 — capacity of roads in rural areas | https://archive.org/details/gov.in.irc.064.1990 | ORR / highway segments |
| TRB circular — PCU for heterogeneous traffic | https://onlinepubs.trb.org/onlinepubs/circulars/ec018/22_44.pdf | dynamic-PCU method |
| Area-occupancy characteristics of heterogeneous traffic | https://www.researchgate.net/publication/232932696 | area-based density |
| UAV trajectory data, Indian urban midblocks | https://arxiv.org/abs/2512.11898 | vehicle dimensions + speeds |

### ❓ "Effective Area Parameters dataset" — not located

I could not find a canonical dataset by this name on Mendeley, Zenodo, Figshare
or Kaggle. **Please send me the exact URL or file you have.**

If you mean the dynamic-PCU / area-occupancy method, it is a *constants table*,
not a trainable dataset:

```
PCU_i = (v_car / v_i) / (A_car / A_i)      A = projected ground area (L × W)
```

That would genuinely improve `capacity_pcu_h`, which currently uses a crude
IRC-style ballpark of per-lane capacity × lanes. The TRB circular and IRC:106
above cover the same ground if your source turns out to be a paper rather than
a dataset.

---

## 7. Hyderabad context — planning and calibration

| Source | Link | Use |
|---|---|---|
| **HMDA Comprehensive Transportation Study** | https://www.hmda.gov.in/cts/ | Junction volume counts (3-arm 2,470–76,193 PCU/12h; 4-arm 5,810–74,705). Calibrate synthetic peaks against these |
| UMTA Hyderabad operations doc (MoHUA) | https://mohua.gov.in/upload/uploadfiles/files/UMTA_Hyderabad_v13.pdf | CTS survey summaries |
| Telangana Open Data Portal | https://data.telangana.gov.in/ | RTA vehicle registrations → fleet mix |
| Hyderabad GTFS (Metro + MMTS) | https://groups.google.com/g/telangana-open-data-community/c/JqBmRLRDndY | transit overlay (email request) |

⚠️ The portal's *"Hyderabad Domestic Traffic Data 2017"* is **airport passenger
traffic, not road traffic**. Don't build on the title.

---

## 8. Simulation — Module §3 scalability

| Tool | Link |
|---|---|
| **SUMO** (Eclipse) — imports your OSM graph, ground-truth flows | https://eclipse.dev/sumo/ |
| SUMO osmWebWizard | https://sumo.dlr.de/docs/Tutorials/OSMWebWizard.html |
| MATSim (agent-based alternative) | https://matsim.org/ |

---

## Minimum set to unblock everything

1. **DriveIndia** → https://tihan.iith.ac.in/tiand-datasets/ *(replaces DATS_2022 for §6)*
2. **TomTom key** → https://developer.tomtom.com/ *(start collecting today)*
3. **Your Effective Area Parameters URL** → send it to me

Everything else is already on disk. Phases 3–10 — Dijkstra, congestion model,
QPSO, PSO, GA, benchmarking, convergence, scalability, rerouting, alerts — need
none of the above and can start now.
