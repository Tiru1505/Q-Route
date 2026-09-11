# Q Route — Quantum-Inspired Traffic Route Optimization

> **SIH PS 26137** — Quantum-Inspired Intelligent Traffic Route Optimization in
> Transportation Systems Using Metaheuristic Optimization. Built on the real
> Hyderabad road network.

Four parts, one repository:

| Part | What it is | Where |
|---|---|---|
| **Optimisation engine** | QPSO, PSO, GA, Dijkstra + Lagrangian, traffic simulation, rerouting, alerts | `optimization/`, `graph/`, `traffic/`, `routing/`, `alerts/`, `engine.py` |
| **AI layer** | YOLOv8 vehicle counting, LSTM congestion forecast, the traffic agent that decides when to reroute | `results/`, `app/services/` |
| **API** | FastAPI service over the engine, with accounts, roles and MongoDB persistence | `app/` |
| **Web app** | React + Vite + Leaflet — a driver's app for users and a control-room console for admins | `frontend/` |

The road graph is real: **286,603 nodes, 741,203 edges**, extracted from
OpenStreetMap across the Hyderabad metro area (ORR and a margin), with Indian
urban free-flow speeds rather than OSMnx's Western defaults.

---

## The pipeline

```
camera / photo ──► YOLOv8 counts vehicles ──► congestion on the road graph
                                                   (simulated where unobserved)
                                                              │
                                                              ▼
                                                   LSTM forecasts congestion
                                                              │
      user drives a route ◄── map + moving car                ▼
              │                                   traffic agent: is a better
              ▼                                   road worth switching to?
    monitor watches the road ahead ──────────────────────────┤
                                                              ▼
       robot notifies the driver ◄── alert ◄── QPSO / Dijkstra re-solve
              │
       Switch route / Keep current ──► the trip is saved to History
```

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

## Two roles: user and admin

Everyone signs in, and the **server** decides the role. A role edited in the
browser fails the session's signature check.

| | **User** — the driver | **Admin** — the control room |
|---|---|---|
| Lands on | `/user/dashboard` | `/admin/dashboard` |
| Pages | Dashboard · History · Settings | Dashboard · Live Traffic · Analytics · Traffic Analysis Lab · Benchmark · Alerts · History · Settings |
| Sees | The optimised route and its result: ETA, distance, traffic now and predicted, time saved | Everything, including the QPSO convergence card, algorithm choice and benchmarks |
| Can | Plan, navigate, switch or keep a route, look back at trips | Also trigger traffic scenarios and spikes, run Demo Mode, analyse road footage, run benchmarks |

A user who types an admin address gets an "Admins only" page, and the API
refuses the request with 403 in any case: hiding a page is not the protection,
the server check is (`app/core/security.py`).

**There is no public admin sign-up** — anyone who could register as an admin
could make themselves one. An account becomes admin in one of two ways:

```bash
# an existing account (e.g. one that signed in with Google) -> admin
.venv/Scripts/python.exe scripts/create_admin.py you@gmail.com --promote
```

```bash
# a new admin with an email + password (typed at the prompt, never shown)
.venv/Scripts/python.exe scripts/create_admin.py ops@example.com --name "Control Room"
```

Or list Google accounts in `ADMIN_EMAILS` in `.env`. That list is only read for
Google sign-in, because only Google has verified the address.

### What a user does

1. **Plan** — start, destination, vehicle, route preference → *Find best route*.
   QPSO runs on the server as always; the user sees the result, not its controls.
2. **Navigate** — *Start navigation* makes that exact route (node for node) the
   trip the server monitors, and a car drives it on the map, turning with the
   road. The drive is **simulated and sped up** (≈19× for a 49-minute trip),
   and the screen says so.
3. **Decide** — when the traffic agent finds a better road, the car waits and a
   card shows *current 53 min → alternative 33 min, you save 20 min*, with
   **Switch route** / **Keep current route**. The robot says the same thing.
4. **Switch** — the map redraws the new road, the car carries on from where it
   is, and the robot checks the new route by itself.
5. **Arrive** — the trip is saved to **History** with the server's own figures:
   original ETA, optimised ETA, time saved.

### Demonstrating it

Sign-ins are per browser tab. Open the **user** in one tab and the **admin** in
another. The user starts navigation; the admin presses *Simulate Congestion
Spike*; the monitor notices the jam on its own and the user's robot alerts them.
The admin dashboard's **Demo Mode** still runs the whole scenario in one tab.

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

This pulls **torch, ultralytics, opencv and lap** as well — the vehicle
detector and the traffic forecaster both load real trained weights.

### 2. Check what the clone is missing

```bash
python scripts/setup_check.py
```

Several things this system needs are too large for the repository: the road
graphs run to hundreds of megabytes and the country extract is 1.71 GB. A fresh
clone is therefore incomplete, and the failure is not obvious — the API boots,
the UI loads, and only one particular request reports that a graph is absent.

The check imports every package, stats every file and opens every model, then
prints one table. Nothing is assumed. To install and build whatever is missing:

```bash
python scripts/setup_check.py --fix
```

Add `--download-extract` to also fetch the 1.71 GB country extract. That is
behind its own flag on purpose — it is a large transfer that only matters if
you intend to build the national or city-level graphs.

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

A network that has not been built reports `available: false` from
`/api/graphs`, and the UI disables it rather than offering a route it cannot
compute.

### 4. Trained models

Both ship with the repository and need no training to run:

- **YOLOv8n** — `results/yolo/dats_v8n/weights/best.pt`, 6.2 MB, 12 vehicle classes
- **LSTM** — `results/lstm_india/india_traffic_lstm.pt`, 30 KB (32 hidden units, 4-step lookback)

Retrain with `python scripts/train_yolo.py` and
`python scripts/train_lstm_india.py`.

### 5. MongoDB

**Required for sign-in** — accounts and trips live there. Route optimisation
itself still works without it.

```bash
docker compose up mongodb -d
```

### 6. Configure `.env`

Copy `.env.example` to `.env`, then set at least:

```bash
SESSION_SECRET=paste-a-long-random-string-here
```

Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
Without it a random key is used per run, which works but signs everyone out
whenever the server restarts. Google sign-in and admin emails are optional —
see [Environment variables](#environment-variables).

### 7. Run the API

```bash
uvicorn app.main:app --reload --port 8010
```

Port 8010 rather than 8000 because another service commonly holds 8000; the
Vite proxy targets 8010 by default (override with `VITE_API_TARGET`).

**First-run timings, so a cold start is not mistaken for a hang:** the
Hyderabad graph takes ~30 s to load and `app/main.py` warms it at startup. The
first QPSO route takes ~10 s, later ones ~2 s. The India graph adds ~24 s the
first time something routes on it. The first image upload pays ~30 s while YOLO
loads its weights. Every one of these is once per process.

Swagger UI: `http://localhost:8010/docs`

### 8. Run the web app

```bash
cd frontend && npm install && npm run dev
```

Opens at `http://localhost:5173`. Register a user on the login page, and make
yourself an admin with `scripts/create_admin.py` (above).

Set `VITE_USE_MOCK=true` in `frontend/.env` to run the UI on bundled demo data
with no backend at all. Offline mode signs you in locally as a **user** only —
there is no offline admin.

### API keys

**None are required** for the core system: routing, QPSO, traffic, the
forecast, alerts and the robot all run without a single key.

| Key | Needed for | Without it |
|---|---|---|
| `GOOGLE_CLIENT_ID` | "Continue with Google" | Email + password sign-in only; the Google button says it is not configured |
| `AI_API_KEY` | Free-form `/assistant/chat`, and rewording notifications | The robot still answers from measured system state (`/assistant/ask`) and notifications use plain wording |
| `TOMTOM_API_KEY` | `scripts/collect_tomtom_hyderabad.py` only | Traffic stays simulated |

---

## Architecture

```
React + Vite + Leaflet  (frontend/)
   /login · /user/* (driver) · /admin/* (control room)
          │  HTTP / JSON + Bearer session, proxied /api -> :8010
          │  WebSocket /api/notifications/ws  (alerts pushed to the robot)
          ▼
      FastAPI  (app/)              Swagger at /docs
          │
    Access layer       app/core/security.py — signed sessions, current_user,
          │            require_admin; passwords hashed with PBKDF2-SHA256
    Service layer      route · trips · auth · agent · monitor · notify ·
          │            forecast (LSTM) · vision (YOLO) · benchmark · alert
          ▼
    Adapter layer      abstract base + mock + REAL implementation
          │            app/integrations/engine_bridge.py
          ▼
    QROEngine  (engine.py)         one object, loaded once, one lock
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

Base path `/api`. **Access:** *open* — anyone; *signed in* — any session;
*own* — only the caller's own data; *admin* — admin session only.

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/health`, `/status` | open | Liveness; `/status` reports which adapter backs each module |
| GET | `/auth/config` | open | Which sign-in methods are available |
| POST | `/auth/register`, `/auth/login`, `/auth/google` | open | Sign in → `{user, token}`; registration always makes a user |
| GET / PATCH | `/auth/me` | signed in | Your account, name and preferences |
| POST | `/auth/password` | signed in | Change your password |
| GET | `/places/search?q=` | open | Free-text place search, restricted to the metro box and the graph |
| POST | `/routes/optimize`, `/routes/alternatives` | open | Optimise between two coordinates; genuinely different corridors |
| GET | `/routes/history` | own (admin: any) | Past optimisations |
| POST | `/trips` | signed in | Start navigation on the chosen route |
| POST | `/trips/{id}/progress` | own | Where the car is (forward only) |
| GET | `/trips/{id}/outlook` | own | Congestion now vs predicted on the road ahead |
| POST | `/trips/{id}/finish` | own | Arrived, or ended early |
| GET | `/trips` | own | Trip history |
| POST | `/agent/analyze`, `/agent/accept`, `/agent/decline` | signed in | The reroute decision; accepting records the switch on the trip |
| POST | `/assistant/ask` · GET `/assistant/briefing` | open | The robot, answering from measured system state |
| WS | `/notifications/ws` | open | Alerts and route checks pushed to every open tab |
| GET | `/traffic/current`, `/traffic/predict`, `/forecast/*` | open | Congestion sample, LSTM forecast |
| POST | `/simulation/event`, `/simulation/congest-route`, `/simulation/advance`, `/simulation/reset` | admin | Traffic scenarios and spikes (all labelled SIMULATED) |
| POST | `/monitor/start`, `/monitor/stop` | admin | The traffic monitor (a user's trip starts it automatically) |
| POST | `/vision/analyse`, `/vision/reset` | admin | YOLO on an uploaded road photo or clip |
| POST | `/benchmark/run`, `/alerts/trigger`, `/alerts/clear`, `/traffic/update`, `/routes/reroute` | admin | Other control-room actions |
| GET | `/analytics`, `/benchmark/results`, `/benchmark/convergence/all` | open | Dashboard aggregates and algorithm comparisons |

Example:

```bash
curl -X POST http://localhost:8010/api/routes/optimize -H "Content-Type: application/json" -d '{"source":{"lat":17.4435,"lon":78.3772},"destination":{"lat":17.3616,"lon":78.4747},"algorithm":"qpso","source_name":"Hitec City","destination_name":"Charminar"}'
```

### The robot assistant

The robot answers questions — *"Will there be congestion ahead?"*, *"Should I
reroute?"* — from the system's own state: the agent's decision, the forecast,
the active trip. That is why it needs no AI key: routing those questions
through a language model would replace a measured number with a recalled one.
Every reply shows where it came from.

When the monitor raises an alert, the robot opens by itself and delivers it in
its own chat with **Switch** / **Keep** buttons. After a switch it checks the
new road and reports back. An optional `AI_API_KEY` only rewords these
messages; the figures stay measured, and the card says which wording was used.

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
| `scripts/create_admin.py` | Create an admin, or promote an existing account |

---

## Tests

```bash
pytest tests/ -q
```

**164 tests**, including:

- `test_rbac.py` — registration always makes a user, passwords are hashed, a
  user's session is refused by every control endpoint, an edited session fails
  its signature, admins come only from the script or Google + `ADMIN_EMAILS`
- `test_trips.py` — a full journey on the real graph: plan, start, drive, admin
  spike, switch, arrive, history — and one user cannot touch another's trip
- `test_auto_alert.py` — the monitor alerts on its own, the robot checks the
  new route, asking the robot never silences the real alert

The full suite takes ~20 minutes because it loads the real 286,603-node graph.
Account and trip tests use in-memory collections, so they never write test
users into your database.

---

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `SESSION_SECRET` | Signs sign-in sessions. Keep it secret; changing it signs everyone out | *(random per run)* |
| `SESSION_HOURS` | How long a session lasts | `12` |
| `GOOGLE_CLIENT_ID` | OAuth client ID (Web application). Public, not a secret | *(unset — Google sign-in off)* |
| `ADMIN_EMAILS` | Comma-separated Google accounts that are admins | *(unset)* |
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGODB_DATABASE` | Database name | `smartroute` |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins | `http://localhost:5173` |
| `APP_ENV` | `development` or `production` | `development` |
| `LOG_LEVEL` | Python log level | `INFO` |
| `AI_API_KEY` | Free-form assistant and message rewording only | *(unset)* |
| `AI_MODEL` | Model for that assistant | `gpt-4o-mini` |
| `AI_BASE_URL` | Any OpenAI-compatible gateway | `https://api.openai.com/v1` |
| `QRO_GRAPH_PATH` | Point at a Hyderabad graph outside the repo | *(unset)* |
| `QRO_INDIA_GRAPH_PATH` | Point at a national graph outside the repo | *(unset)* |
| `TOMTOM_API_KEY` | Only `scripts/collect_tomtom_hyderabad.py` | *(unset)* |
| `VITE_USE_MOCK` | `true` runs the frontend with no backend | `false` |
| `VITE_API_TARGET` | Where the Vite proxy sends `/api` | `http://127.0.0.1:8010` |

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
- **Traffic is simulated**, from a Greenshields fundamental diagram with
  capacities derived from road class, and every simulated response is labelled
  `SIMULATED`. `POST /traffic/update` is the hook for a live feed. A TomTom
  Traffic Flow key has been verified against live Hyderabad roads, but the app
  does not read TomTom data yet.
- **The forecast is a real LSTM, fed a reconstructed history.** The trained
  model is served in the app (`/status` reports
  `prediction: "lstm+anchored-history"`). It reads the last hour of 15-minute
  vehicle counts, and no road here keeps such a history yet, so that hour is
  rebuilt from the congestion on the graph *now*, shaped by the measured daily
  profile of Indian traffic. Fed the simulator, it forecasts the simulator; fed
  real observations, the same code forecasts real traffic. Every response says
  so in its `assumption` field. The Analytics page's older linear projection is
  kept beside it and titled as a linear extrapolation, not a forecast.
- **YOLO finds 91 % of vehicles by count** (off by 1.15 vehicles per image);
  recall across all classes is 0.36, and bicycles and carts were never detected
  in validation. No correction factor is applied — one did not improve
  held-out accuracy. The Lab shows these figures next to every result.
- **The navigation drive is simulated.** The car moves along real route
  geometry at demo speed; the traffic, forecast and reroute decisions it meets
  are the system's own.
- **One trip at a time.** The engine monitors a single active trip for the
  whole server. Two people navigating at once would replace each other's trip —
  the displaced one is told so rather than silently mixed up. A multi-trip
  engine is the main change a real fleet deployment would need.
- **Sessions are verified on every request**, but there is no rate limiting or
  account lockout yet; add both before any public deployment.
- **Place search uses Nominatim**, throttled to one request per second per its
  usage policy and cached. Add a contact address to `CONTACT` in
  `app/api/places.py` before any public deployment.
- **Every chart plots something measured.** An empty state is shown before any
  route has been run, rather than invented bars.
- **Google Maps data is deliberately not used.** Its terms forbid storing or
  training on it, and doing so would risk disqualification.

---

## Repository layout

```
├── engine.py                 # QROEngine — the single object the API calls
├── app/                      # FastAPI service
│   ├── api/                  # Endpoints (auth, trips, routes, agent, simulation, …)
│   ├── core/security.py      # Passwords, signed sessions, current_user / require_admin
│   ├── services/             # Orchestration (auth, trips, agent, monitor, notify, …)
│   ├── integrations/         # Adapters, incl. engine_bridge.py (the real one)
│   ├── models/               # Pydantic schemas
│   └── database/             # MongoDB (users, trips, route history, …)
├── optimization/             # qpso · pso · ga · dijkstra · encoding · multistop
├── graph/                    # graph_loader · edge_weights (the cost model) · vehicles
├── traffic/                  # congestion_model · simulator
├── routing/                  # route · rerouting · validator
├── alerts/                   # alert_engine
├── benchmarking/             # benchmark harness · convergence plots
├── preprocessing/            # osm_processor — builds the graph
├── scripts/                  # Runnable experiments, create_admin.py
├── config/                   # places.yaml · datasets.yaml
├── frontend/                 # React + Vite + Leaflet
│   └── src/pages/user/       # The driver's Dashboard, Trip History, Settings
├── tests/                    # pytest
└── results/                  # Trained models, reports and plots
```

Further reading: [`DEPLOY.md`](DEPLOY.md) on hosting this (read the memory constraint
first), [`DATA.md`](DATA.md) on datasets and what they can and cannot
support, [`INTEGRATION.md`](INTEGRATION.md) on wiring the layers together.
