# Deploying Q Route

Two services: the React app on **Vercel**, the FastAPI service on **Railway**
(or Render, if you prefer — both are configured).

Read the constraint first — it decides what is actually possible.

---

## The constraint: the API needs 1.8 GB of RAM

The API keeps the entire Hyderabad road graph in memory — 286,603 nodes and
741,203 edges. Measured on the running service:

| | |
|---|---|
| Resident memory | **1.74 GB** |
| Peak during graph load | **1.80 GB** |

This is the number that decides where it can be hosted, because platforms
differ enormously in how they treat it.

| Platform / plan | Memory available | Fits? | Cost |
|---|---|---|---|
| Render Free / Starter | 512 MB | **No** — killed during startup | $0 |
| Render Standard | 2 GB | Yes, little headroom | ~$25/mo flat |
| **Railway Hobby** | **up to 48 GB per service** | **Yes** | **$5/mo + ~2.5 c/hour running** |
| Hugging Face Spaces (CPU Basic) | 16 GB | Yes | PRO required to create a Docker Space |

**Railway is the best fit, and it is not close.** Two reasons:

1. **No small-instance wall.** Render's free tier hard-caps at 512 MB, so this
   service cannot start there at all. Railway's Hobby plan allows up to 48 GB
   per service — you are limited by what you are willing to pay for, not by a
   tier ceiling.
2. **Per-second billing.** Railway charges about $10/GB/month, metered by the
   second, which for a 1.8 GB service is roughly **2.5 cents per hour**. Render
   charges a flat monthly fee whether or not anyone visits.

For a hackathon that difference is decisive. Judging needs the service up for
hours, not months:

| Uptime | Railway RAM cost | Render Standard |
|---|---|---|
| 8 hours | ~$0.20 | $25 |
| 48 hours (a judging weekend) | ~$1.20 | $25 |
| 24/7 for a month | ~$18 | $25 |

The $5 Hobby plan includes $5 of usage credit, so a few days of demo time is
covered by the subscription you are already paying.

Hugging Face Spaces is worth knowing about as a third option — CPU Basic
hardware is 16 GB and costs nothing per hour — but creating a Docker Space
requires a PRO account ($9/month), and free hardware sleeps when idle, which is
painful here because waking up means paying the ~30 s graph load again.

### If you want to spend nothing at all

1. **Deploy the frontend only, in mock mode.** Free, works today, gives you a
   shareable link. Every page and interaction works; the numbers are the
   built-in demo dataset and the app says so on screen. Shows the interface,
   not the engine.
2. **Run the API locally and tunnel it** (`ngrok http 8010`), with the deployed
   frontend pointed at the tunnel. Free, real numbers, but only while your
   laptop is on, and the URL changes each session.

Shrinking the graph does not rescue a 512 MB tier. Dropping to major roads only
would cut node count substantially, but the arithmetic still lands near 650 MB,
and it degrades door-to-door accuracy on small streets.

Do **not** switch to the `hyderabad-city` graph to save memory. It is half the
size because it stops at the municipal boundary, which excludes the airport,
Medchal and Patancheru — it returns routes shorter than the straight-line
distance between their endpoints. It is kept only as a counter-example.

---

## 1. Frontend on Vercel

The repo is already on GitHub, so connect it rather than uploading.

1. Go to **vercel.com → Add New → Project**, import `Tiru1505/SmartRoute-AI`.
2. Set **Root Directory** to `frontend`. This matters — the repo root is the
   Python project, and Vercel will not find a build without it.
3. Framework preset should auto-detect **Vite**. `frontend/vercel.json` supplies
   the build command, output directory and the SPA rewrite. Keep the rewrite:
   without it, refreshing on `/analytics` returns a 404, because those routes
   exist only in the browser.
4. Add environment variables:

| Variable | Value (mock mode) | Value (live backend) |
|---|---|---|
| `VITE_USE_MOCK` | `true` | `false` |
| `VITE_API_BASE` | *(leave unset)* | `https://<your-api-host>/api` |

Start in mock mode. Flip both variables once the API is up, and redeploy —
Vite bakes env vars in at build time, so a redeploy is required for a change to
take effect.

---

## 2. Backend on Railway (recommended)

`railway.toml` configures the build and start commands. Two things it cannot
set for you, both in the Railway dashboard:

1. **Attach a volume**, mounted at `/data`. Without one the graph is fetched
   again on every deploy, because the container filesystem is ephemeral.
2. **Set the variables** below.

| Variable | Value | Notes |
|---|---|---|
| `QRO_GRAPH_PATH` | `/data/hyderabad/hyderabad_drive.pkl` | Must sit on the volume |
| `QRO_GRAPH_URL` | URL of a prebuilt `.pkl` | Optional but strongly preferred — see below |
| `ALLOWED_ORIGINS` | Your Vercel URL | Exact origin, no trailing slash |
| `MONGODB_URI` | Atlas connection string | Optional; without it only History is empty |
| `MONGODB_DATABASE` | `smartroute` | |

Then **New Project → Deploy from GitHub repo → `Tiru1505/SmartRoute-AI`**.

### Get the graph there the fast way

On first boot `backend/scripts/ensure_graph.py` runs before uvicorn binds. If
`QRO_GRAPH_URL` is set it downloads a prebuilt pickle (~214 MB, a couple of
minutes). If not, it rebuilds the whole metro extract from OpenStreetMap, which
is slow and briefly uses *more* memory than the API itself.

Prefer the download. You already have the file locally:

```bash
ls -lh data/processed/hyderabad/hyderabad_drive.pkl
```

Upload that to any object store — Cloudflare R2, S3, even a GitHub Release
asset (the 2 GB per-asset limit is well clear of 214 MB) — and point
`QRO_GRAPH_URL` at it. The script writes to a `.part` file and moves it into
place, so an interrupted download cannot leave a half-written graph that looks
valid on the next boot.

After the first successful boot the graph is on the volume and later deploys
skip all of this.

---

## 2b. Backend on Render (alternative)

`render.yaml` is a working blueprint if you would rather use Render. **New →
Blueprint**, point it at the repo.

The one thing to check: the blueprint requests `plan: standard`. Do not drop it
to Free or Starter — at 512 MB the process is killed during startup, and the
logs will show an unexplained restart loop rather than a clear out-of-memory
message.

Set `ALLOWED_ORIGINS`, and `QRO_GRAPH_URL` if you have the pickle hosted.
Everything else the blueprint fills in.

---

## 3. Wiring them together

After both are live:

1. Copy the API's public URL into Vercel as `VITE_API_BASE` (with the `/api`
   suffix),
   and set `VITE_USE_MOCK=false`. Redeploy.
2. Copy the Vercel URL into the API as `ALLOWED_ORIGINS`. Both platforms
   restart the service automatically on a variable change.

Getting CORS wrong is the usual failure here: the browser will report a network
error while the API looks healthy when you curl it. If that happens, check that
`ALLOWED_ORIGINS` exactly matches the origin the browser sends — scheme
included, no trailing slash.

Verify:

```bash
curl https://<your-api-host>/api/status
```

`adapters` should read `osm` for graph, optimization and traffic. `prediction`
correctly reads `mock` — no forecasting model is wired in.

---

## What is deployed vs what is real

In mock mode the deployed site is a faithful interface demo and labels itself
as one. Only with the API connected are the routes, benchmarks, traffic and
rerouting computed from the real graph.
