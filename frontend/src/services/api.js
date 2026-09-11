/**
 * The single boundary between the UI and the backend.
 *
 * Right now every function resolves mock data after a small artificial delay so
 * loading states are real and visible. When FastAPI is ready, flip USE_MOCK to
 * false (or set VITE_USE_MOCK=false) and only this file changes — no component
 * needs touching, because the response shapes are identical.
 *
 * Expected backend, once it exists:
 *   POST /optimize-route   POST /reroute      GET /traffic
 *   GET  /prediction       GET  /benchmark    GET /convergence
 */
import {
  ALERTS, BENCHMARK, CONVERGENCE, CONVERGENCE_CHART_DATA, INCIDENTS,
  LOCATIONS, PREDICTION_SERIES, REROUTED_ROUTE, ROUTES, SCALABILITY,
  TRAFFIC_SEGMENTS, ROUTE_HISTORY, TRAFFIC_TREND, TRAFFIC_DISTRIBUTION,
  ROUTE_PERFORMANCE, ANALYTICS_STATS, MOCK_VEHICLES,
} from '../data/mockData'
import {
  mapAlertsResponse, mapAnalyticsResponse, mapBenchmarkResponse,
  mapConvergenceResponse, mapHistoryResponse, mapOptimizeResponse,
  mapTrafficResponse,
} from './backendAdapter'

/**
 * A place -> {lat, lon}, since the backend routes by coordinate.
 *
 * Places are now resolved by the search box rather than picked from a fixed
 * list, so they arrive as objects. The `coords` fallback covers the curated
 * landmarks in mockData, which still use the [lat, lon] tuple shape.
 */
function coordsFor(place) {
  if (!place) throw new ApiError('No location selected', 400)
  const lat = place.lat ?? place.coords?.[0]
  const lon = place.lon ?? place.coords?.[1]
  if (typeof lat !== 'number' || typeof lon !== 'number') {
    throw new ApiError(`Location has no coordinates: ${place.name || place.id}`, 400)
  }
  return { lat, lon }
}

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'

/** True when the app runs without a backend. Features that exist only there
 *  — the monitor, real alerts — use it to say so instead of failing silently. */
export const isMockMode = () => USE_MOCK
const BASE = import.meta.env.VITE_API_BASE || '/api'

const delay = (ms) => new Promise((r) => setTimeout(r, ms))

/** Deep-clones mock payloads so callers can never mutate the shared store. */
const clone = (v) => JSON.parse(JSON.stringify(v))

class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/* --------------------------------------------------------- the session
 *
 * The server signs a session token at sign-in; it rides on every request as
 * `Authorization: Bearer ...`, and the server decides from it who is calling
 * and whether they may. The token lives in sessionStorage with the user, so
 * each browser tab holds its own sign-in — which is how a demo can show a
 * user in one tab and the admin in another.
 */
const SESSION_KEY = 'qro.session_user'

export function sessionToken() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null')?.token || null
  } catch {
    return null
  }
}

/**
 * The session header on its own, for calls that cannot go through `request`
 * — an upload, whose Content-Type must be left to the browser. Forgetting it
 * there is how the Traffic Analysis Lab first failed after sign-in became real:
 * the server refused the upload as coming from nobody.
 */
export function authHeaders() {
  const token = sessionToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// Set by the app: what to do when the server says the session is over.
let onSessionExpired = null
export function setSessionExpiredHandler(fn) {
  onSessionExpired = fn
}

async function request(path, options = {}) {
  const token = sessionToken()
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
      },
    })
    if (!res.ok) {
      // A failing response that is not JSON did not come from our API at all —
      // it is the static host answering. Deploying the frontend with
      // VITE_USE_MOCK=false but no VITE_API_BASE makes every call resolve to
      // the site's own origin, where Vercel returns a text/plain 404. Reporting
      // that as a backend error is wrong and unfixable by the visitor, so it is
      // reported as "no backend here" (status 0) and handled by the fallback.
      // A JSON error body means the API really did answer, and that surfaces.
      const type = res.headers.get('content-type') || ''
      if (!type.includes('json')) {
        throw new ApiError(`No API at ${BASE} (host returned ${res.status}).`, 0)
      }
      // The API's own explanation, when it gave one — "Email or password is
      // incorrect" is worth more to the person than "Unauthorized".
      let message = `Request failed: ${res.statusText}`
      try {
        const body = await res.json()
        message = body?.error?.message || body?.detail || message
        if (typeof message !== 'string') message = `Request failed: ${res.statusText}`
      } catch { /* keep the status text */ }
      // A signed request refused as unauthenticated means the session is over
      // (expired, or the server's key changed). Sign-in attempts carry no token,
      // so a wrong password never lands here.
      if (res.status === 401 && token) onSessionExpired?.(message)
      throw new ApiError(message, res.status)
    }
    return await res.json()
  } catch (err) {
    if (err instanceof ApiError) throw err
    throw new ApiError('Cannot reach the optimization backend.', 0)
  }
}

/* ------------------------------------------------- offline fallback */

/**
 * Whether the backend has been found unreachable this session.
 *
 * A deployed build is configured at build time, so a site built to talk to a
 * live API has no way to know the API is down — it just failed on every page
 * with "Cannot reach the optimization backend". That is the worst outcome for
 * a demo: the site looks broken rather than degraded. This is especially easy
 * to hit when the API runs on localhost, where it is reachable for whoever is
 * running it and for nobody else.
 *
 * So an unreachable response switches to the bundled demo data, which the UI
 * already labels on screen. A 404 or 500 is NOT treated this way — those mean
 * the backend answered and something is genuinely wrong, which should surface
 * rather than be papered over. Only status 0, a failure to connect at all,
 * triggers the fallback.
 *
 * THE FALLBACK EXPIRES, AND THAT MATTERS
 * This used to be a one-way latch: the first failure set a flag that was never
 * cleared, so a tab that happened to be open while the backend restarted
 * served demo data for the rest of its life. Nothing on screen explained why
 * a freshly-started backend was still being ignored, and the only cure was a
 * reload nobody knew to perform. Restarting a dev server is routine, so the
 * flag now expires and the next call tries the real backend again.
 */
const FALLBACK_COOLDOWN_MS = 10_000

let fallbackUntil = 0

/**
 * Whether a call failed to reach the backend recently.
 *
 * Reporting only — the UI uses it to say it is showing demo data. It does NOT
 * gate requests; every call tries the backend for itself.
 */
export function isUsingFallback() {
  return Date.now() < fallbackUntil
}

async function liveOrMock(live, mock) {
  if (USE_MOCK) return mock()

  // Every call attempts the backend, always. There used to be a short-circuit
  // here that returned demo data while a cooldown was in force, and it made a
  // single hiccup contagious: one failed request — a restart, a slow endpoint —
  // marked the whole API dead for ten seconds, and any page mounting inside
  // that window rendered "Demo data" from a backend that was answering 200 the
  // whole time. Pages fetch once on mount, so it never corrected itself.
  //
  // Attempting costs nothing when the backend is genuinely down: a refused
  // connection returns immediately. The fallback still catches this call's own
  // failure below; it just no longer speaks for calls it knows nothing about.
  try {
    const result = await live()
    if (fallbackUntil) {
      fallbackUntil = 0
      console.info(`[api] ${BASE} is reachable again — back on live data.`)
    }
    return result
  } catch (err) {
    if (err instanceof ApiError && err.status === 0) {
      const first = !isUsingFallback()
      fallbackUntil = Date.now() + FALLBACK_COOLDOWN_MS
      if (first) {
        console.warn(
          `[api] ${BASE} is unreachable — serving bundled demo data for the ` +
          `next ${FALLBACK_COOLDOWN_MS / 1000}s, then retrying. ` +
          'Start the backend, or set VITE_API_BASE to a reachable URL.'
        )
      }
      return mock()
    }
    throw err
  }
}

/* ------------------------------------------------------------------ places */

/**
 * Free-text place search.
 *
 * The backend merges the curated Hyderabad landmarks with OpenStreetMap
 * results and drops anything that is not on the routing graph, so every result
 * here is safe to route from. In mock mode we filter the curated list locally,
 * which keeps the UI usable with the backend switched off.
 *
 * @returns {Promise<Array<{id, name, address, lat, lon, source}>>}
 */
export async function searchPlaces(query = '', limit = 8, graph = null) {
  const q = query.trim()

  if (!USE_MOCK) {
    try {
      // The search box is scoped to the network the route will run on: a
      // result outside it is not routable, and offering it would produce a
      // route that silently starts somewhere else.
      const scope = graph ? `&graph=${encodeURIComponent(graph)}` : ''
      const res = await request(`/places/search?q=${encodeURIComponent(q)}&limit=${limit}${scope}`)
      return Array.isArray(res?.results) ? res.results : []
    } catch {
      // A dead geocoder should not empty the box — fall through to the
      // curated landmarks so the demo still works offline.
    }
  }

  await delay(USE_MOCK ? 160 : 0)
  const ql = q.toLowerCase()
  return LOCATIONS
    .filter((l) => !ql || l.name.toLowerCase().includes(ql))
    .slice(0, limit)
    .map((l) => ({
      id: l.id,
      name: l.name,
      address: 'Hyderabad, Telangana',
      lat: l.coords[0],
      lon: l.coords[1],
      source: 'preset',
    }))
}

/* ------------------------------------------------------------------ routes */

/**
 * Run the optimizer.
 * @returns {{ routes: Array, recommended: Object, meta: Object }}
 */
export async function getRouteOptimization({ start, end, algorithm = 'qpso', mode = 'balanced', vehicle = 'car', graph = null, userId = null } = {}) {
  return liveOrMock(
    () => optimizeLive({ start, end, algorithm, mode, vehicle, graph, userId }),
    async () => {
      await delay(400)
      const routes = clone(ROUTES)
      return {
        routes,
        recommended: routes.find((r) => r.recommended) || routes[0],
        meta: { algorithm, mode, vehicle, isDemoData: true, computedAt: new Date().toISOString() },
      }
    },
  )
}

/**
 * The vehicle profiles the backend routes by, with each one's rules.
 *
 * The labels, exclusions and speed caps come from the backend's own table,
 * so the selector cannot describe a rule the router does not apply.
 */
export async function getVehicles() {
  return liveOrMock(
    () => request('/vehicles'),
    async () => ({ ...clone(MOCK_VEHICLES), isDemoData: true }),
  )
}

/**
 * The road networks this backend can route on.
 *
 * No mock fallback: the two networks differ in what they can physically do,
 * and inventing that list offline would let the UI offer intercity routing
 * that cannot work.
 */
export async function getGraphs() {
  return request('/graphs')
}

/* ------------------------------------------------- agent & simulation */

/**
 * Ask the AI Traffic Agent whether rerouting is worth it.
 *
 * No mock fallback anywhere in this group. A fabricated "13 minutes saved"
 * is indistinguishable from a real one on screen, and that is exactly the
 * claim this feature exists to make truthfully.
 */
export async function analyzeTraffic({ horizonMin = 15, predictive = true, force = false, graph } = {}) {
  const p = new URLSearchParams({
    horizon_min: String(horizonMin),
    predictive: String(predictive),
    force: String(force),
  })
  if (graph) p.set('graph', graph)
  return request(`/agent/analyze?${p}`, { method: 'POST' })
}

export async function acceptReroute(graph) {
  return request(`/agent/accept${graph ? `?graph=${graph}` : ''}`, { method: 'POST' })
}

export async function declineReroute(graph) {
  return request(`/agent/decline${graph ? `?graph=${graph}` : ''}`, { method: 'POST' })
}

export async function getAgentStatus(graph) {
  return request(`/agent/status${graph ? `?graph=${graph}` : ''}`)
}

export async function getScenarios(graph) {
  return request(`/simulation/scenarios${graph ? `?graph=${graph}` : ''}`)
}

export async function triggerScenario(scenario, graph) {
  const p = new URLSearchParams({ scenario })
  if (graph) p.set('graph', graph)
  return request(`/simulation/event?${p}`, { method: 'POST' })
}

export async function congestActiveRoute({ level = 0.92, graph } = {}) {
  const p = new URLSearchParams({ level: String(level) })
  if (graph) p.set('graph', graph)
  return request(`/simulation/congest-route?${p}`, { method: 'POST' })
}

/**
 * Which sign-in methods the server offers. The Google client ID comes from
 * here — one copy, on the server — rather than from the frontend's own .env.
 */
export async function getAuthConfig() {
  if (USE_MOCK) return { google: { enabled: false, clientId: null }, offline: true }
  return request('/auth/config')
}

/** Exchange a Google ID token for a verified user and a session: `{user, token}`. */
export async function signInWithGoogle(credential) {
  return request('/auth/google', { method: 'POST', body: JSON.stringify({ credential }) })
}

/* ------------------------------------------------------------ accounts */

export async function registerAccount({ name, email, password }) {
  return request('/auth/register', { method: 'POST', body: JSON.stringify({ name, email, password }) })
}

export async function loginAccount({ email, password }) {
  return request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
}

export async function getMe() {
  return request('/auth/me')
}

export async function updateMe({ name, preferences } = {}) {
  return request('/auth/me', { method: 'PATCH', body: JSON.stringify({ name, preferences }) })
}

export async function changePassword({ currentPassword, newPassword }) {
  return request('/auth/password', {
    method: 'POST',
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  })
}

/* --------------------------------------------------------------- trips
 *
 * A trip is one journey: started on the route the user chose, moved along by
 * the car on the map, switched when the agent recommends it, finished on
 * arrival. The switch itself is recorded by /agent/accept on the server.
 */

export async function startTrip({ route, start, end, graph, vehicle, mode, requestId }) {
  return request('/trips', {
    method: 'POST',
    body: JSON.stringify({
      graph,
      request_id: requestId || null,
      source: { name: start?.name || '', lat: start.lat ?? start.coords?.[0], lon: start.lon ?? start.coords?.[1] },
      destination: { name: end?.name || '', lat: end.lat ?? end.coords?.[0], lon: end.lon ?? end.coords?.[1] },
      route: {
        label: route.label || '',
        via: route.via || '',
        distance_km: route.distanceKm,
        eta_min: route.etaMin,
        congestion: Math.min(Math.max(route.congestion || 0, 0), 1),
        nodes: route.nodes,
      },
      vehicle,
      mode,
    }),
  })
}

export async function reportTripProgress(tripId, fraction) {
  return request(`/trips/${tripId}/progress`, { method: 'POST', body: JSON.stringify({ fraction }) })
}

export async function getTripOutlook(tripId) {
  return request(`/trips/${tripId}/outlook`)
}

export async function finishTrip(tripId, status) {
  return request(`/trips/${tripId}/finish`, { method: 'POST', body: JSON.stringify({ status }) })
}

export async function getTrips() {
  return request('/trips')
}

/**
 * Place the simulated driver part-way along the active trip.
 *
 * A spike lands on the road AHEAD of the driver, so the demo needs the driver
 * moving first. Deliberately not /routes/reroute: that also evaluates a
 * reroute, and an alert raised there would beat the monitor to it.
 */
export async function advanceTrip({ progress = 0.3, graph } = {}) {
  const p = new URLSearchParams({ progress: String(progress) })
  if (graph) p.set('graph', graph)
  return request(`/simulation/advance?${p}`, { method: 'POST' })
}

/**
 * Start (or re-tune) the background monitor. Idempotent on the backend:
 * calling it while running only changes the tick.
 */
export async function startMonitor({ tickSeconds = 15, graph } = {}) {
  const p = new URLSearchParams({ tick_seconds: String(tickSeconds) })
  if (graph) p.set('graph', graph)
  return request(`/monitor/start?${p}`, { method: 'POST' })
}

/** Component health, as reported by the backend rather than assumed. */
export async function getSystemStatus() {
  return request('/status')
}

/**
 * Ask the assistant about the journey.
 *
 * Answered from backend state, so this works with no AI key configured — the
 * open-ended `assistantChat` below is the other half, and the backend decides
 * when a question needs it.
 */
export async function assistantAsk({ question, graph, context } = {}) {
  return request('/assistant/ask', {
    method: 'POST',
    body: JSON.stringify({ question, graph: graph || null, context: context || null }),
  })
}

/** What the assistant would say unprompted: the current prediction. */
export async function getAssistantBriefing(graph) {
  return request(`/assistant/briefing${graph ? `?graph=${graph}` : ''}`)
}

/** Send open-ended navigation language to the server-side LLM tool runner. */
export async function assistantChat({ messages, context } = {}) {
  if (USE_MOCK) {
    throw new ApiError('AI assistant requires a live backend with AI_API_KEY configured.', 503)
  }
  return request('/assistant/chat', {
    method: 'POST',
    body: JSON.stringify({ messages, context }),
  })
}

async function optimizeLive({ start, end, algorithm, mode, vehicle, graph, userId }) {
  {
    const body = JSON.stringify({
      source: coordsFor(start),
      destination: coordsFor(end),
      algorithm,
      // The objective and the vehicle. `mode` was accepted by this function
      // and never put in the body, so the objective buttons changed nothing:
      // every route came back "balanced" whatever was chosen.
      mode,
      vehicle,
      // Omitted rather than defaulted, so the backend keeps ownership of what
      // "no preference" means.
      ...(graph ? { graph } : {}),
      // Who ran it. The backend has always stored and filtered on this; the
      // frontend never sent it, so all 585 saved routes carried user_id null
      // and every visitor saw every other visitor's history.
      ...(userId ? { user_id: userId } : {}),
      // Sent so the history page can show where the trip actually went.
      // Endpoints are free text now, so the name cannot be looked up from a
      // coordinate after the fact.
      source_name: start?.name ?? null,
      destination_name: end?.name ?? null,
    })
    const primary = await request('/routes/optimize', { method: 'POST', body })

    // Alternatives are best-effort: the map is still useful with one route.
    let alternatives = []
    try {
      const alt = await request('/routes/alternatives', { method: 'POST', body })
      alternatives = Array.isArray(alt) ? alt : (alt?.alternatives ?? alt?.routes ?? [])
    } catch {
      alternatives = []
    }

    const mapped = mapOptimizeResponse(primary, alternatives, {
      from: start?.name ?? start,
      to: end?.name ?? end,
      mode,
    })
    if (import.meta.env.DEV) window.__qroLast = { primary, alternatives, mapped }
    return mapped
  }
}

export async function getAlternativeRoutes({ start, end } = {}) {
  if (!USE_MOCK) return request(`/alternatives?start=${start}&end=${end}`)
  await delay(250)
  return clone(ROUTES.filter((r) => !r.recommended))
}

/**
 * Recompute from where the driver is now.
 *
 * Hits POST /routes/reroute, which advances the active trip, congests the road
 * ahead and re-solves with Dijkstra from the current position. It needs a route
 * to have been optimised first — that call is what creates the trip.
 *
 * The backend already answers in the shape the UI wants (camelCase, with the
 * new route serialised for the map), so only the old route is added here.
 */
export async function reroute({ progress = 0.4, spike = true, force = false, oldRoute = null } = {}) {
  if (!USE_MOCK) {
    const res = await request('/routes/reroute', {
      method: 'POST',
      body: JSON.stringify({ progress, spike, force }),
    })
    return {
      ...res,
      oldRoute,
      // shouldReroute false is a real answer — the current route is still best.
      // The panel needs newRoute to exist before it renders a comparison.
      newRoute: res.newRoute ?? null,
      isDemoData: false,
    }
  }
  await delay(600)
  const mockNew = clone(REROUTED_ROUTE)
  return {
    shouldReroute: true,
    oldRoute: oldRoute ?? clone(ROUTES[0]),
    newRoute: mockNew,
    // Kept internally consistent: 24 - 17 = 7.
    previousEtaMin: 24,
    newEtaMin: 17,
    timeSavedMin: 7,
    savedPct: 29.2,
    algorithm: 'Dijkstra',
    reason: 'congestion ahead on the current corridor',
    isDemoData: true,
  }
}

/* ----------------------------------------------------------------- traffic */

export async function getTrafficData() {
  return liveOrMock(
    async () => mapTrafficResponse(await request('/traffic/current')),
    async () => {
      await delay(300)
      return {
        segments: clone(TRAFFIC_SEGMENTS),
        incidents: clone(INCIDENTS),
        updatedAt: new Date().toISOString(),
        isDemoData: true,
      }
    },
  )
}

export async function getPrediction() {
  return liveOrMock(
    () => request('/prediction/status'),
    async () => {
      await delay(300)
      return { series: clone(PREDICTION_SERIES), isDemoData: true }
    },
  )
}

/**
 * Raise an alert on demand.
 *
 * The alerting path only fires when traffic genuinely deteriorates past the
 * policy gates, which is correct and impossible to schedule for a live
 * demonstration. This asks the backend to raise a real one through the same
 * service and storage; it is recorded as manually triggered so it can never be
 * mistaken later for something the system detected.
 */
export async function triggerAlert(scenario = 'congestion') {
  if (!USE_MOCK) {
    return request('/alerts/trigger', {
      method: 'POST',
      body: JSON.stringify({ scenario }),
    })
  }
  await delay(200)
  return { trigger: 'manual', scenario, alert: null }
}

/** Wipe stored alerts so a demonstration can be replayed from a clean slate. */
export async function clearAlerts() {
  if (!USE_MOCK) return request('/alerts/clear', { method: 'POST' })
  await delay(150)
  return { cleared: 0 }
}

/**
 * Analyse an uploaded road image or clip.
 *
 * Goes straight to fetch rather than through `request`: the body is
 * multipart/form-data, so the Content-Type header must carry the boundary the
 * browser generates. Setting it by hand breaks the upload.
 *
 * There is no mock fallback. A fabricated detection would be indistinguishable
 * from a real one on screen, which is exactly the thing this feature must never
 * do — so with no backend it fails loudly instead.
 */
export async function analyseRoadMedia(file, { session, segmentM, sampleFps, maxFrames, city, roadId } = {}) {
  const body = new FormData()
  body.append('file', file)
  if (session) body.append('session', session)
  if (segmentM != null) body.append('segment_m', String(segmentM))
  if (sampleFps != null) body.append('sample_fps', String(sampleFps))
  if (maxFrames != null) body.append('max_frames', String(maxFrames))
  // Where the footage was taken. Without these the result is a detection with
  // nowhere to live; with them it becomes an observation on a real road.
  if (city) body.append('city', city)
  if (roadId) body.append('road_id', roadId)

  // The session goes with it: analysing footage is an admin action, and the
  // server refuses an upload that names nobody.
  const headers = authHeaders()
  const res = await fetch(`${BASE}/vision/analyse`, { method: 'POST', body, headers })
  if (!res.ok) {
    let detail = `Analysis failed (${res.status})`
    try {
      const j = await res.json()
      detail = j?.error?.message || j?.detail || detail
    } catch { /* non-JSON error body */ }
    if (res.status === 401 && headers.Authorization) onSessionExpired?.(detail)
    throw new ApiError(detail, res.status)
  }
  return res.json()
}

export async function getVisionStatus() {
  return request('/vision/status')
}

/** Cities an observation can be attached to, with what each network covers. */
export async function getCities() {
  return request('/vision/cities')
}

/** Named roads read from the city's graph — not a curated list. */
export async function getRoads(city, q = '', limit = 50) {
  const p = new URLSearchParams({ city, limit: String(limit) })
  if (q) p.set('q', q)
  return request(`/vision/roads?${p}`)
}

export async function resetVisionSession(session) {
  const res = await fetch(`${BASE}/vision/reset?session=${encodeURIComponent(session)}`,
                          { method: 'POST', headers: authHeaders() })
  return res.ok ? res.json() : { cleared: false }
}

/**
 * Forecast from the trained Indian-traffic LSTM.
 *
 * This is a replay of recorded days the model never saw in training, so the
 * response carries the real outcome next to the prediction. It is not a live
 * forecast: the model needs three hours of recent vehicle counts for a road,
 * which no live road in this system yet provides.
 */
export async function getForecast() {
  return liveOrMock(
    async () => {
      const r = await request('/forecast/replay')
      return { ...r, isDemoData: false }
    },
    async () => {
      await delay(250)
      return { unavailable: true, isDemoData: true }
    },
  )
}

export async function getAlerts() {
  return liveOrMock(
    async () => mapAlertsResponse(await request('/alerts/')),
    async () => {
      await delay(250)
      return clone(ALERTS)
    },
  )
}

/* --------------------------------------------------------------- analytics */

export async function getAnalytics() {
  return liveOrMock(
    async () => mapAnalyticsResponse(await request('/analytics')),
    async () => {
      await delay(350)
      return {
        stats: clone(ANALYTICS_STATS),
        trend: clone(TRAFFIC_TREND),
        prediction: clone(PREDICTION_SERIES),
        performance: clone(ROUTE_PERFORMANCE),
        distribution: clone(TRAFFIC_DISTRIBUTION),
        isDemoData: true,
      }
    },
  )
}

/**
 * The algorithm comparison.
 *
 * Given a start and end, the problem is built around THAT journey, so
 * benchmarking after optimising a different route measures a different
 * instance. Without them the backend runs its fixed curated round — the one
 * the published headline figures were measured on.
 */
export async function getBenchmark({ start, end, graph } = {}) {
  const params = new URLSearchParams()
  if (start && end) {
    // coordsFor throws on a place with no coordinates. That should degrade to
    // the curated benchmark, not fail the whole panel.
    try {
      const a = coordsFor(start)
      const b = coordsFor(end)
      params.set('origin_lat', a.lat)
      params.set('origin_lon', a.lon)
      params.set('dest_lat', b.lat)
      params.set('dest_lon', b.lon)
    } catch {
      params.delete('origin_lat'); params.delete('origin_lon')
      params.delete('dest_lat'); params.delete('dest_lon')
    }
  }
  if (graph) params.set('graph', graph)
  const qs = params.toString()

  return liveOrMock(
    async () => mapBenchmarkResponse(
      await request(`/benchmark/results${qs ? `?${qs}` : ''}`)),
    async () => {
      await delay(400)
      return clone(BENCHMARK)
    },
  )
}

export async function getConvergence({ start, end, graph } = {}) {
  // Same route as the table above it, or the chart describes a different
  // problem than the numbers it sits under.
  const params = new URLSearchParams()
  if (start && end) {
    try {
      const a = coordsFor(start)
      const b = coordsFor(end)
      params.set('origin_lat', a.lat)
      params.set('origin_lon', a.lon)
      params.set('dest_lat', b.lat)
      params.set('dest_lon', b.lon)
    } catch { /* fall back to the curated instance */ }
  }
  if (graph) params.set('graph', graph)
  const qs = params.toString()

  return liveOrMock(
    async () => mapConvergenceResponse(
      await request(`/benchmark/convergence/all${qs ? `?${qs}` : ''}`)),
    async () => {
      await delay(400)
      return {
        ...clone(CONVERGENCE),
        chartData: clone(CONVERGENCE_CHART_DATA),
      }
    },
  )
}

export async function getScalability() {
  return liveOrMock(
    () => request('/analytics/scalability'),
    async () => {
      await delay(400)
      return clone(SCALABILITY)
    },
  )
}

export async function getRouteHistory(userId = null) {
  // Scoped to the caller when known. Note this is a convenience, not a
  // security boundary: sign-in here is a demo that accepts any credentials and
  // the API is unauthenticated, so anyone can request any user_id.
  const qs = userId ? `?user_id=${encodeURIComponent(userId)}` : ''
  return liveOrMock(
    async () => mapHistoryResponse(await request(`/routes/history${qs}`)),
    async () => {
      await delay(250)
      return clone(ROUTE_HISTORY)
    },
  )
}

export async function getHealth() {
  if (!USE_MOCK) return request('/health')  // backend mounts this at /api/health
  await delay(120)
  return { status: 'ok', backend: 'mock' }
}

export { ApiError, USE_MOCK }
