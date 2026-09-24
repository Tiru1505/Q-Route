# Handoff — where Q-Route stands

> Written for whoever (or whatever) picks this up next. It covers the state of
> the repository, the decisions behind it, what is finished, what is half done,
> and the traps that cost time to discover. Figures here were measured on this
> machine; where something is an assumption it says so.

**Project:** Q-Route — SIH 2026, Problem Statement 26137, "Quantum-Inspired
Intelligent Traffic Route Optimization", organisation Egreen Quanta.
**Repository:** https://github.com/Tiru1505/Q-Route · local path
`C:\Users\tirup\OneDrive\Desktop\Q-Route` (moved here from
`AgriAI\quantum-traffic-hyderabad`).
**Last commit at the time of writing:** `2d3f4d2`.

---

## 1. How the owner wants to be worked with

These are standing instructions, not preferences to re-derive:

- Explain the idea in plain language **before** writing code. One step at a
  time; do not chain into the next phase unasked.
- Complete, runnable code — never pseudocode. Say which file, how to run it,
  and what output to expect.
- **Never fabricate results.** Report honestly, including where QPSO loses.
  Every generated figure on screen must be labelled SIMULATED, PREDICTION or
  UPLOADED.
- Keep QPSO explainable — the owner is graded on their ability to explain it.
- Do not add technologies unprompted.
- **Commit and push only when asked.** Pushing redeploys the Vercel site.

### Hard constraints

- The React Three Fiber 3D frontend lives in `stash@{0}` and is **not wanted**.
  Never push it.
- Google Maps data must never be stored, cached or trained on (their terms;
  a disqualification risk).
- `TOMTOM_API_KEY` comes only from the environment. Never hardcode or print it.
- `.env` is git-ignored and holds `SESSION_SECRET`, `GOOGLE_CLIENT_ID`,
  `ADMIN_EMAILS`. Never commit it, never echo its contents.
- The owner's email must not be sent to unrelated services; `CONTACT` in
  `backend/app/api/places.py` stays blank.

---

## 2. Shape of the repository

```
frontend/    React + Vite + Leaflet (+ MapLibre for the globe page)
backend/     all Python: app/ (FastAPI), engine.py, graph/ optimization/
             traffic/ routing/ alerts/ forecasting/ vision/ preprocessing/
             dataio/ scripts/ tests/ config/ requirements.txt
data/        datasets only (raw, processed graphs, vision imagery)
results/     trained models, metrics, plots, reports
```

Everything runs **from the repository root**:

```bash
pytest -q
uvicorn app.main:app --app-dir backend --reload --port 8010
python backend/scripts/run_multistop.py --stops 6 --trials 30
```

Modules find the repo root by walking up from their own file; `config/` moved
*with* the code, so those references use a `BACKEND` constant rather than
`ROOT`. `.env` is found from either the root or `backend/`.

**The venv survived the folder move**, but only when invoked as
`.venv/Scripts/python.exe -m <module>`. The `.exe` shims inside
`.venv\Scripts\` (uvicorn.exe, pytest.exe) still embed the old path.

---

## 3. What exists and works

### Routing engine
Real OSM graph: **286,603 nodes, 741,203 edges** for Hyderabad; seven networks
in total. Dijkstra is the router (provably optimal for one origin→destination);
QPSO's genuine win is **multi-stop**, and the README says so rather than
pretending otherwise.

### Accounts and roles (`backend/app/core/security.py`)
- Passwords: PBKDF2-SHA256, 600k iterations. Sessions: HMAC-signed token, 12 h,
  carried as `Authorization: Bearer`, **stored per browser tab** — which is how
  the two-tab demo works (user in one, admin in the other).
- Roles `user` / `admin`. **No public admin registration.** Admins come from
  `backend/scripts/create_admin.py` or, for Google-verified emails only,
  `ADMIN_EMAILS` in `.env`.
- 18 control endpoints (simulation, monitor, benchmark runs, alert triggers,
  the vision upload) refuse non-admins with 403; unauthenticated gets 401.
- Two Google accounts exist in the database; **the owner's primary one is
  already an admin** (a stored `role: admin`, set by the script). The other is
  a normal user. Read them with a query on the `users` collection rather than
  guessing — addresses are deliberately not written down here, because this
  repository is public.

### The driver's app (`/user/*`)
Dashboard (planner without QPSO controls — QPSO still runs server-side),
navigation with a car that follows real route geometry, a Switch/Keep
recommendation card, Trip History, Settings. Trips are recorded in MongoDB:
start → progress → reroute (recorded by the server from the engine's own
figures) → finish.

### The admin console (`/admin/*`)
Every page the app had before roles, unchanged, plus the new **Coverage**
globe. Demo Mode still runs the whole scenario end to end.

### Languages
English / हिन्दी / తెలుగు, chosen in Settings on both pages, saved to the
account and the browser. **Server-written text (robot answers, traffic alerts,
reroute reasons) is deliberately NOT translated** — it is generated from
measured figures in `backend/app/services`, and translating it belongs there.
The picker says this in all three languages.

### Vehicle-aware travel time
Each vehicle carries the share of a jam's delay it actually suffers:
two-wheeler 0.55, auto-rickshaw 0.8, **car 1.0 (baseline, unchanged)**,
bus/truck 1.15, bicycle 0.6. Free-flow time is never discounted, so nobody
gains on an empty road. **These shares are assumptions**, labelled as such in
the vehicle picker and shipped as `jamShare` on `/api/vehicles`.

Measured, Hitec City → Charminar, peak hour: two-wheeler 38.0 min ·
auto 45.8 · car 51.6 · bus/truck 55.9 · bicycle 75.1. The distances differ —
the optimiser picks different roads per vehicle.

---

## 4. The models, and their real scores

### YOLOv8n — vehicle counting
DATS_2022, 12 classes, 1,504 train / 376 val images. Transfer-learned from
`yolov8n.pt`, 25 epochs @ 416 px, batch 8, **CPU**, ~2 h 40 m.

- Detection: precision 0.50, recall 0.41, mAP@50 0.40, mAP@50-95 0.22.
- What matters — counting error on held-out images: finds **91%** of vehicles,
  **MAE 1.15 vehicles/image**, bias −0.28; PCU MAE 1.59.
- Per class: Bus 97%, Car 95%, Bike 94%, Rikshaw 84%, Tempo 75%, Truck 108%.
  **Cycles and carts never detected** (11 and 2 instances).
- Dividing by recall made it worse (MAE 5.24), so **no correction is applied**.

### LSTM — congestion forecast
Indian junction data, 15-min counts, 31 days, split by day (24/3/4). One layer,
32 hidden units, dropout 0.3, 60-minute lookback, predicts 4 steps.

| Ahead | LSTM MAE | Persistence | Situation acc. | Persistence | Majority |
|---|---|---|---|---|---|
| 15 min | 23.9 | 27.3 | 70.3% | 62.6% | 60% |
| 30 min | 28.3 | 33.3 | 69.7% | 57.9% | 60% |
| 60 min | 33.9 | 42.0 | 68.2% | 53.7% | 59% |

Ablations: lookback 30 min/1 h/2 h/3 h → 23.6/23.9/25.2/25.4 (more history
hurt); features all/counts/clock → 23.9/24.8/27.6.

**Caveat to state before a judge finds it:** no road keeps an hour of live
counts, so the model's input history is *reconstructed* from current graph
congestion using a daily profile (`prediction_adapter.py` explains it). Fed the
simulator, it forecasts the simulator.

---

## 5. Performance — where the seconds go

Measured in-process, warm, best of three:

| Stage | Time |
|---|---|
| Graph load | 31.5 s, **once per server start** |
| Snap points (KD-tree, cached) | 0.1 ms |
| Cost-model calibration (after a traffic change) | 411 ms |
| Dijkstra across the city | 642 ms |
| QPSO on top | +1.66 s |
| Alternatives (3 corridors) | 3.73 s |

A warm "Find best route" is ~6 s, not 60; 60 s means the server had just
started. Google is fast because of precomputation (contraction hierarchies /
CRP) plus C++, not a cleverer query-time search.

**Cheapest wins, not yet done:** defer QPSO (it only draws the convergence
chart — Dijkstra's answer is already optimal), stop the alternatives
re-solving the primary a fourth time, cache routes by (from, to, vehicle,
preference, traffic version). Together ≈6 s → ~1.5 s. Then A* (~200 ms),
then contracting shape-point chains, then moving the inner loop to SciPy's C
Dijkstra (tens of ms).

---

## 6. Tests

`pytest -q` from the root — **174 tests collected**. The full run takes 18–27
minutes because it loads the real graph; it is slower when memory is tight.

- `test_rbac.py` — registration always makes a user, passwords hashed, control
  endpoints refuse users, an edited session fails its signature, admins only
  from the script or the Google list, and every direct `fetch` in `api.js`
  sends the session (that check exists because the Lab's upload once didn't).
- `test_trips.py` — a full journey on the real graph, and one user cannot touch
  another's trip.
- `test_vehicles.py` — the jam ordering, the car unchanged, no gain on a clear
  road, and bike < car < bus end to end.
- `test_i18n.py` — no missing phrase in any language, no lost `{n}`
  placeholder, and the browser cannot offer a language the server would refuse.
- `conftest.py` signs every test in as a **test admin** unless marked
  `real_auth`; account and trip tests use in-memory collections so nothing is
  written to the real database.

---

## 7. Traps that cost time

- **The browser preview pane delivers no animation frames.** `requestAnimation­Frame`
  never fires, so the car, page transitions and the MapLibre globe do not
  render there — a screenshot forces a single frame. This is the test browser,
  not the app. The navigation car has a watchdog timer for the same reason
  (real browsers also pause background tabs).
- **Restart the backend after backend edits.** Several "it didn't work"
  moments were a server still running the old code.
- **Port 5173 is often taken by the owner's other projects** (taskweave, FitAI).
  Q-Route then runs on 5174 — and **Google sign-in breaks there**, because the
  OAuth client only allows `http://localhost:5173` and
  `https://q-route.vercel.app`. Either free 5173 or add the origin in Google
  Cloud Console.
- **MapLibre must be excluded from Vite's dependency pre-bundling** (already in
  `frontend/vite.config.js`) or its web worker fails to load. Clear
  `node_modules/.vite` after changing that.
- **MapLibre 6 has no default export** — import `{ Map as MapLibreMap }`.
- The engine holds **one active trip for the whole server**. Two people
  navigating at once displace each other; the displaced trip is told so.
- Low free memory (≈0.5 GB) makes the test suite take 27 min instead of 18.
  Stop the servers before a full run.

---

## 8. Open items

**Uncommitted at the time of writing** (all built and verified, none pushed):

- Four UX fixes: the fabricated "₹0 (No tolls)" line removed from the route
  card; one number format everywhere (`frontend/src/i18n/format.js`); the
  assistant no longer covers the trip buttons; the map stops fighting a pan and
  gained a Recenter / Following control.
- The **Coverage globe** (`/admin/coverage`, MapLibre + keyless CARTO tiles)
  and the `/api/graphs` change that serves build statistics and no longer leaks
  the server's filesystem path.

**Known, deliberately not fixed:**

- Six admin Settings toggles (tolls, highways, sensitivity, two alert
  thresholds) are stored but read by nothing.
- The admin map's original car is invisible — its CSS was never written. The
  user-facing navigation car is a separate, working component.
- The full suite has not been run since the language, vehicle and globe work.

**Ideas already discussed, not started:** dark map tiles for the routing map,
moving the brand colour off the congestion palette, "show me the jam" (click an
alert, pan to the congested segment), staged progress while routing, repeat-a-trip
shortcuts, and the premium-feature list (multi-stop planner UI, best-time-to-leave,
live TomTom data, fuel/CO₂ report).

---

## 9. Running it

```bash
# backend (from the repository root)
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8010

# frontend
npm --prefix frontend run dev        # add -- --port 5174 if 5173 is taken

# make someone an admin
.venv/Scripts/python.exe backend/scripts/create_admin.py you@gmail.com --promote
```

First route after a start costs ~12 s (graph load plus a cold QPSO); after that
about 3 s. For a demo: sign in as the user in one tab and the admin in another,
start navigation as the user, then press **Simulate Congestion Spike** as the
admin — the monitor notices on its own and the user's robot alerts them.
