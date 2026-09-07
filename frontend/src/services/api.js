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
  ROUTE_PERFORMANCE, ANALYTICS_STATS,
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

async function request(path, options = {}) {
  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
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
      throw new ApiError(`Request failed: ${res.statusText}`, res.status)
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
 * So the first unreachable response flips this flag and every later call goes
 * straight to the bundled demo data, which the UI already labels on screen.
 * A 404 or 500 is NOT treated this way — those mean the backend answered and
 * something is genuinely wrong, which should surface rather than be papered
 * over. Only status 0, a failure to connect at all, triggers the fallback.
 */
let backendUnreachable = false

/** True once we have given up on the backend and switched to demo data. */
export function isUsingFallback() {
  return backendUnreachable
}

async function liveOrMock(live, mock) {
  if (USE_MOCK || backendUnreachable) return mock()
  try {
    return await live()
  } catch (err) {
    if (err instanceof ApiError && err.status === 0) {
      if (!backendUnreachable) {
        backendUnreachable = true
        console.warn(
          `[api] ${BASE} is unreachable — serving bundled demo data instead. ` +
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
export async function searchPlaces(query = '', limit = 8) {
  const q = query.trim()

  if (!USE_MOCK) {
    try {
      const res = await request(`/places/search?q=${encodeURIComponent(q)}&limit=${limit}`)
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
export async function getRouteOptimization({ start, end, algorithm = 'qpso', mode = 'balanced' } = {}) {
  return liveOrMock(
    () => optimizeLive({ start, end, algorithm, mode }),
    async () => {
      await delay(400)
      const routes = clone(ROUTES)
      return {
        routes,
        recommended: routes.find((r) => r.recommended) || routes[0],
        meta: { algorithm, mode, isDemoData: true, computedAt: new Date().toISOString() },
      }
    },
  )
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

async function optimizeLive({ start, end, algorithm, mode }) {
  {
    const body = JSON.stringify({
      source: coordsFor(start),
      destination: coordsFor(end),
      algorithm,
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

export async function getBenchmark() {
  return liveOrMock(
    async () => mapBenchmarkResponse(await request('/benchmark/results')),
    async () => {
      await delay(400)
      return clone(BENCHMARK)
    },
  )
}

export async function getConvergence() {
  return liveOrMock(
    async () => mapConvergenceResponse(await request('/benchmark/convergence/all')),
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

export async function getRouteHistory() {
  return liveOrMock(
    async () => mapHistoryResponse(await request('/routes/history')),
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
