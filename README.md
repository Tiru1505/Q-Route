# Q Route — Quantum-Inspired Traffic Route Optimization

> **SIH PS 26137** — Quantum-Inspired Intelligent Traffic Route Optimization in
> Transportation Systems Using Metaheuristic Optimization. Built on the real
> Hyderabad road network.

Three parts, one repository:

| Part | What it is | Where |
|---|---|---|
| **Optimisation engine** | QPSO, PSO, GA, Dijkstra + Lagrangian, traffic simulation, rerouting, alerts | `optimization/`, `graph/`, `traffic/`, `routing/`, `alerts/`, `engine.py` |
| **API** | FastAPI service over the engine, with MongoDB persistence | `app/` |
| **Web app** | React + Vite + Leaflet dashboard | `frontend/` |

The road graph is real: **286,603 nodes, 741,203 edges**, extracted from
OpenStreetMap across the Hyderabad metro area (ORR and a margin), with Indian
urban free-flow speeds rather than OSMnx's Western defaults.

---

## The headline result

The brief mandates QPSO. On **single-pair** routing with additively combined
weights, Dijkstra is provably optimal, so no metaheuristic can beat it — we say
so in the UI rather than hiding it. QPSO's genuine advantage is **multi-stop
routing**, which the brief also names and which Dijkstra cannot express at all:
it finds a path between two points and has no notion of ordering stops.

6-stop delivery round, peak-hour traffic, 30 independent trials per algorithm,
identical budget (population 40 × 120 iterations = 4,800 evaluations each),
measured against the exact optimum from brute force over all 720 orderings:

| Algorithm | Mean | Std | Gap vs optimum | Hit optimum | Runtime |
|---|---|---|---|---|---|
| **QPSO** | **4.093213** | **0.000000** | **+0.000 %** | **30 / 30** | 16.2 ms |
| GA | 4.117775 | 0.132271 | +0.600 % | 29 / 30 | 127.4 ms |
| PSO | 4.224006 | 0.262111 | +3.195 % | 24 / 30 | 14.4 ms |
| Dijkstra | — | — | cannot express the problem | — | — |

Reproduce it:

```bash
python scripts/run_multistop.py --stops 6 --trials 30
```

Fairness is enforced structurally, not by convention: all three metaheuristics
receive the same problem object, the same random-key encoding, the same
evaluation budget, the same seeds, and the same bound handling. Beyond 9 stops
brute force becomes intractable (3.6 M orderings) while the metaheuristics stay
flat — `--scalability` sweeps that.

---

## Quick start

### 1. Python environment

```bash
python -m venv .venv
```

```bash
.venv\Scripts\Activate.ps1
```

```bash
pip install -r requirements.txt
```

This now pulls **torch, ultralytics, opencv and lap** as well — the vehicle
detector and the traffic forecaster both load real trained weights, so they are
no longer optional extras.

### 2. Check what the clone is missing

```bash
python scripts/setup_check.py
```

Several things this system needs are too large for the repository: the road
graphs run to hundreds of megabytes and the country extract is 1.71 GB. A fresh
clone is therefore incomplete, and the failure is not obvious — the API boots,
the UI loads, and only one particular request reports that a graph is absent.

The check imports every package, stats every file and opens every model, then
prints one table. Nothing is assumed.

To install and build whatever is missing:

```bash
python scripts/setup_check.py --fix
```

Add `--download-extract` to also fetch the 1.71 GB country extract. That is
behind its own flag on purpose — it is a large transfer that only matters if
you intend to build the national or city-level graphs, and a setup script
should not start one on your behalf.

### 3. Road graphs

Seven networks are configured. **None are in the repository** — the smallest is
147 MB and GitHub refuses anything past 100 MB.

| Network | Covers | Build |
|---|---|---|
| `hyderabad` | every street inside the ORR | `python preprocessing/osm_processor.py --city "Hyderabad, Telangana, India" --metro` |
| `india` | national motorway/trunk/primary | `python scripts/build_india_highways.py` |
| `bengaluru`, `delhi`, `chennai`, `mumbai`, `pune` | every street in the metro | `python scripts/build_city_graphs.py` |

The `--metro` flag matters for Hyderabad: `graph_from_place("Hyderabad")`
returns only the municipal boundary, which silently excludes the airport,
Medchal and Patancheru and produces routes shorter than the straight-line
distance between their endpoints.

The national and city graphs are cut from one Geofabrik extract rather than
fetched from Overpass, which times out from most machines. The city builder
reads the extract twice and fills **every** city during the same sweep, so five
cities cost barely more than one.

A network that has not been built reports `available: false` from
`/api/graphs`, and the UI disables it rather than offering a route it cannot
compute.

### 4. Trained models

Both ship with the repository and need no training to run:

- **YOLO** — `results/yolo/dats_v8n/weights/best.pt`, 6.2 MB, 12 vehicle classes
- **LSTM** — `results/lstm_india/india_traffic_lstm.pt`, 30 KB

Retrain with `python scripts/train_yolo.py` and
`python scripts/train_lstm_india.py`.

### 5. MongoDB

Optional — the API degrades gracefully without it, losing only history.

```bash
docker compose up mongodb -d
```

### 6. Run the API

```bash
uvicorn app.main:app --reload --port 8010
```

Port 8010 rather than 8000 because another service commonly holds 8000; the
Vite proxy targets 8010 by default (override with `VITE_API_TARGET`).

**First-run timings, so a cold start is not mistaken for a hang:** the
Hyderabad graph takes ~30 s to load and `app/main.py` warms it at startup. The
India graph adds ~24 s the first time something routes on it. The first image
upload pays ~30 s while YOLO loads its weights. Every one of these is once per
process.

Swagger UI: `http://localhost:8010/docs`

### 7. Run the web app

```bash
cd frontend && npm install && npm run dev
```

Opens at `http://localhost:5173`. Set `VITE_USE_MOCK=true` in `frontend/.env`
to run the whole UI on bundled demo data with no backend at all.

### API keys

**None are required.** The entire system runs without a single key.

| Key | Needed for | Without it |
|---|---|---|
| `AI_API_KEY` | the natural-language assistant only | `/api/assistant/chat` returns 503; everything else works |
| `MONGODB_URI` | route history | defaults to `mongodb://localhost:27017` |
| `ALLOWED_ORIGINS` | deploying the frontend elsewhere | localhost origins are allowed by default |

There is **no authentication**. The login screen is a demo: it accepts any
email and password and stores the session in the browser. Every API endpoint is
unauthenticated. That is fine on localhost and is not fine on a public host.

---

## Using it

Type any place into **Start location** and **Destination** — they are free-text
search boxes, not a fixed list. Suggestions merge the curated Hyderabad
landmarks with live OpenStreetMap results, and anything more than 1.5 km from
the nearest road node in our extract is dropped, because routing from a point
that is not on the graph would silently start somewhere else.

Pages: Dashboard, Route Optimizer, Live Traffic, Analytics, Benchmark, Alerts,
History, Settings. **Demo Mode** plays a scripted scenario — optimise, then a
congestion spike, then a predictive alert, then an automatic reroute.

---

## Architecture

```
React + Vite + Leaflet  (frontend/)
          │  HTTP / JSON, proxied /api -> :8010
          ▼
      FastAPI  (app/)              Swagger at /docs
          │
    Service layer      route · optimization · traffic · prediction
          │            benchmark · alert
          ▼
    Adapter layer      abstract base + mock + REAL implementation
          │            app/integrations/engine_bridge.py
          ▼
    QROEngine  (engine.py)         one object, loaded once
          │
    ┌─────┴─────┬──────────┬──────────┬─────────┐
  graph/    optimization/  traffic/  routing/  alerts/
```

The adapter layer is why the backend could be built and tested before the
engine existed. `engine_bridge.py` implements the same abstract interfaces
against the real engine, so the API surface, models and tests never changed
when the numbers became real.

Two caches matter for latency: a KD-tree over all 286,603 nodes (osmnx rebuilds
its spatial index on *every* `nearest_nodes` call, and one request makes four),
and per-endpoint cost-model calibration. Together they take a cold
`/routes/optimize` from ~57 s to ~11 s, and a warm one to under 2 s.

---

## API

Base path `/api`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health`, `/status` | Liveness; `/status` reports which adapter backs each module |
| GET | `/places/search?q=` | Free-text place search, restricted to the metro box and the graph |
| POST | `/routes/optimize` | Optimise between two coordinates |
| POST | `/routes/alternatives` | Genuinely different corridors, via edge-penalty re-solve |
| POST | `/routes/reroute` | Re-evaluate the active trip from the driver's current position |
| GET | `/routes/history` | Past optimisations |
| GET | `/traffic/current` | Live congestion sample |
| POST | `/traffic/update` | Ingest observed congestion onto the graph |
| GET | `/traffic/predict` | Congestion forecast |
| GET | `/analytics`, `/analytics/scalability` | Dashboard aggregates |
| GET | `/benchmark/results` | Live algorithm comparison (`?source=stored` for saved runs) |
| GET | `/benchmark/convergence/all` | Convergence curves for QPSO, PSO, GA |
| GET | `/alerts/` | Active alerts |

### Natural-language route assistant

The dashboard assistant accepts open-ended requests and uses server-side LLM
tool calling to resolve places, calculate routes, inspect the current route and
traffic, and find alternatives. It never receives database access or a client
API key; every state change is returned as a controlled action from
`POST /api/assistant/chat`.

Configure the provider in the backend environment, using `.env.example` as a
starting point:

```bash
AI_API_KEY=your-server-side-key
AI_MODEL=gpt-4o-mini
AI_BASE_URL=https://api.openai.com/v1
```

Without `AI_API_KEY`, the endpoint returns a clear configuration error and the
frontend does not fall back to scripted answers.

Example:

```bash
curl -X POST http://localhost:8010/api/routes/optimize -H "Content-Type: application/json" -d '{"source":{"lat":17.4435,"lon":78.3772},"destination":{"lat":17.3616,"lon":78.4747},"algorithm":"qpso","source_name":"Hitec City","destination_name":"Charminar"}'
```

---

## Command-line experiments

| Script | What it does |
|---|---|
| `scripts/run_multistop.py` | **The headline experiment** — QPSO vs PSO vs GA vs brute force |
| `scripts/run_qpso.py` | Single-pair QPSO against Dijkstra |
| `scripts/run_dijkstra.py` | Shortest path, verified against NetworkX |
| `scripts/run_constrained.py` | Congestion-budget routing vs Lagrangian relaxation |
| `scripts/run_traffic.py` | Traffic scenarios on the network |
| `scripts/run_rerouting.py` | Mid-trip reroute on a congestion spike |
| `scripts/run_demo.py` | End-to-end scripted scenario |

---

## Tests

```bash
pytest tests/ -q
```

64 tests covering models, adapters, services and every endpoint.

---

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGODB_DATABASE` | Database name | `smartroute` |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins | `http://localhost:5173` |
| `APP_ENV` | `development` or `production` | `development` |
| `LOG_LEVEL` | Python log level | `INFO` |
| `AI_API_KEY` | Natural-language assistant only | *(unset — endpoint returns 503)* |
| `AI_MODEL` | Model for that assistant | `gpt-4o-mini` |
| `AI_BASE_URL` | Any OpenAI-compatible gateway | `https://api.openai.com/v1` |
| `QRO_GRAPH_PATH` | Point at a Hyderabad graph outside the repo | *(unset)* |
| `QRO_INDIA_GRAPH_PATH` | Point at a national graph outside the repo | *(unset)* |
| `TOMTOM_API_KEY` | Only `scripts/collect_tomtom_hyderabad.py`, which has never been run | *(unset)* |
| `VITE_USE_MOCK` | `true` runs the frontend with no backend | `false` |
| `VITE_API_TARGET` | Where the Vite proxy sends `/api` | `http://127.0.0.1:8010` |

`FCM_SERVER_KEY` appears in `app/core/config.py` and is read by nothing. Push
notifications are not implemented; the setting is a leftover.

Never commit `.env`.

---

## Honest notes

Things a reader — or a judge — should know, rather than discover:

- **Dijkstra wins single-pair routing, and the UI says so.** `RealQpsoAdapter`
  runs genuine QPSO and reports its true fitness and convergence, but returns
  the optimal geometry. Presenting a marginally worse path as an improvement
  would be dishonest. QPSO's real win is multi-stop.
- **Constrained routing was a negative result.** Lagrangian relaxation beat
  QPSO at every congestion budget we tried. It is kept in the repo, documented,
  and not claimed as a win.
- **Prediction is a placeholder, and the UI says so.** No LSTM/GRU is wired
  in; `/status` reports `prediction: "mock"` while everything else reports
  `osm`. The Analytics chart is titled "Congestion Projection", not a forecast,
  and carries a caption stating that the curve is current congestion extended
  at a fixed rate. The wording comes from the backend, so it cannot drift away
  from the implementation.
- **Traffic is simulated**, from a Greenshields fundamental diagram with
  capacities derived from road class, not invented numbers. `POST
  /traffic/update` is the hook for a live feed — ingested observations are
  written onto the graph and the next optimisation routes around them.
- **Authentication is not real.** The login screen stores a name and email in
  `localStorage`; no password is stored or transmitted. Replace `signIn()` in
  `frontend/src/store/AppContext.jsx` before deploying anywhere public.
- **Place search uses Nominatim**, throttled to one request per second per its
  usage policy and cached. Add a contact address to `CONTACT` in
  `app/api/places.py` before any public deployment.
- **Every chart plots something measured.** Route Performance previously
  plotted congestion multiplied by 30 and 60 under "Distance (km)" and "Time
  (min)" labels; it now reads real optimisation results, and shows an empty
  state before any route has been run rather than inventing bars.
- **Google Maps data is deliberately not used.** Its terms forbid storing or
  training on it, and doing so would risk disqualification.

---

## Repository layout

```
├── engine.py                 # QROEngine — the single object the API calls
├── app/                      # FastAPI service
│   ├── api/                  # Endpoints
│   ├── services/             # Orchestration
│   ├── integrations/         # Adapters, incl. engine_bridge.py (the real one)
│   ├── models/               # Pydantic schemas
│   └── database/             # MongoDB
├── optimization/             # qpso · pso · ga · dijkstra · encoding · multistop
├── graph/                    # graph_loader · edge_weights (the cost model)
├── traffic/                  # congestion_model · simulator
├── routing/                  # route · rerouting · validator
├── alerts/                   # alert_engine
├── benchmarking/             # benchmark harness · convergence plots
├── preprocessing/            # osm_processor — builds the graph
├── scripts/                  # Runnable experiments
├── config/                   # places.yaml · datasets.yaml
├── frontend/                 # React + Vite + Leaflet
├── tests/                    # pytest
└── results/                  # Reports and plots
```

Further reading: [`DEPLOY.md`](DEPLOY.md) on hosting this (read the memory constraint
first), [`DATA.md`](DATA.md) on datasets and what they can and cannot
support, [`INTEGRATION.md`](INTEGRATION.md) on wiring the layers together.
