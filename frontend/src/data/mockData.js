/**
 * Central mock data store.
 *
 * Every number in this file is DEMO DATA. Nothing here comes from a real
 * benchmark run. When the FastAPI backend is ready, src/services/api.js swaps
 * these objects for real responses — the components never change, because they
 * only ever consume the shapes defined here.
 *
 * Coordinates are genuine Hyderabad locations, so the map is geographically
 * correct even while the routing numbers are illustrative.
 */

export const DEMO_DATA_NOTICE =
  'Demo data — not a validated benchmark run. Replace via src/services/api.js.'

export const HYDERABAD_CENTER = [17.4065, 78.4772]

/* ------------------------------------------------------------------ places */
export const LOCATIONS = [
  { id: 'hitec', name: 'Hitec City', coords: [17.4435, 78.3772] },
  { id: 'gachibowli', name: 'Gachibowli', coords: [17.4401, 78.3489] },
  { id: 'madhapur', name: 'Madhapur', coords: [17.4483, 78.3915] },
  { id: 'kondapur', name: 'Kondapur', coords: [17.464, 78.364] },
  { id: 'jubilee', name: 'Jubilee Hills', coords: [17.4239, 78.4138] },
  { id: 'banjara', name: 'Banjara Hills', coords: [17.4126, 78.4482] },
  { id: 'panjagutta', name: 'Panjagutta', coords: [17.4256, 78.45] },
  { id: 'ameerpet', name: 'Ameerpet', coords: [17.4374, 78.4487] },
  { id: 'begumpet', name: 'Begumpet', coords: [17.4443, 78.4649] },
  { id: 'secunderabad', name: 'Secunderabad', coords: [17.4344, 78.5013] },
  { id: 'mehdipatnam', name: 'Mehdipatnam', coords: [17.395, 78.436] },
  { id: 'charminar', name: 'Charminar', coords: [17.3616, 78.4747] },
  { id: 'dilsukhnagar', name: 'Dilsukhnagar', coords: [17.3687, 78.5247] },
  { id: 'lbnagar', name: 'LB Nagar', coords: [17.3457, 78.5522] },
  { id: 'uppal', name: 'Uppal', coords: [17.402, 78.559] },
  { id: 'kukatpally', name: 'Kukatpally', coords: [17.4849, 78.4138] },
  { id: 'miyapur', name: 'Miyapur', coords: [17.496, 78.358] },
  { id: 'airport', name: 'RGIA Airport (Shamshabad)', coords: [17.2403, 78.4294] },
]

/**
 * Endpoints are resolved place objects, not ids into LOCATIONS — the search
 * box can return any OpenStreetMap place, which has no entry in this file.
 * LOCATIONS survives as the curated suggestion list and the offline fallback.
 */
const asPlace = (l) => ({
  id: l.id,
  name: l.name,
  address: 'Hyderabad, Telangana',
  lat: l.coords[0],
  lon: l.coords[1],
  coords: l.coords,
  source: 'preset',
})

export const DEFAULT_START = asPlace(LOCATIONS.find((l) => l.id === 'hitec'))
export const DEFAULT_END = asPlace(LOCATIONS.find((l) => l.id === 'charminar'))

/* ------------------------------------------------------------------ routes */
/* Three genuinely different corridors between Hitec City and Charminar. */
export const ROUTES = [
  {
    id: 'r1',
    label: 'Route 1',
    algorithm: 'QPSO',
    recommended: true,
    fastest: true,
    distanceKm: 18.9,
    etaMin: 38,
    congestion: 0.22,
    score: 91,
    timeSavedMin: 6,
    via: 'Jubilee Hills → Banjara Hills → Mehdipatnam',
    color: '#FF6B35',
    path: [
      [17.4435, 78.3772], [17.44, 78.39], [17.431, 78.402], [17.4239, 78.4138],
      [17.418, 78.429], [17.4126, 78.4482], [17.405, 78.445], [17.395, 78.436],
      [17.393, 78.448], [17.388, 78.465], [17.38, 78.47], [17.37, 78.473],
      [17.3616, 78.4747],
    ],
  },
  {
    id: 'r2',
    label: 'Route 2',
    algorithm: 'QPSO',
    recommended: false,
    fastest: false,
    distanceKm: 20.4,
    etaMin: 44,
    congestion: 0.35,
    score: 78,
    timeSavedMin: 0,
    via: 'Madhapur → Panjagutta → Khairatabad → Abids',
    color: '#E83E8C',
    path: [
      [17.4435, 78.3772], [17.4483, 78.3915], [17.44, 78.405], [17.43, 78.43],
      [17.4256, 78.45], [17.418, 78.456], [17.409, 78.465], [17.399, 78.47],
      [17.3897, 78.4747], [17.38, 78.476], [17.37, 78.475], [17.3616, 78.4747],
    ],
  },
  {
    id: 'r3',
    label: 'Route 3',
    algorithm: 'QPSO',
    recommended: false,
    fastest: false,
    distanceKm: 22.1,
    etaMin: 47,
    congestion: 0.41,
    score: 71,
    timeSavedMin: 0,
    via: 'Manikonda → Tolichowki → Attapur',
    color: '#E83E8C',
    path: [
      [17.4435, 78.3772], [17.43, 78.38], [17.415, 78.385], [17.403, 78.376],
      [17.396, 78.405], [17.39, 78.42], [17.361, 78.423], [17.355, 78.44],
      [17.356, 78.46], [17.3616, 78.4747],
    ],
  },
]

/* Route the system switches to during the rerouting demo. */
export const REROUTED_ROUTE = {
  id: 'r1b',
  label: 'New QPSO Route',
  algorithm: 'QPSO',
  recommended: true,
  fastest: true,
  distanceKm: 19.8,
  etaMin: 31,
  congestion: 0.19,
  score: 94,
  timeSavedMin: 7,
  via: 'Madhapur → Panjagutta → Masab Tank → Nampally',
  color: '#FF6B35',
  path: [
    [17.4435, 78.3772], [17.4483, 78.3915], [17.442, 78.408], [17.4374, 78.4487],
    [17.4256, 78.45], [17.415, 78.452], [17.4026, 78.4535], [17.3935, 78.4485],
    [17.3888, 78.4655], [17.379, 78.4705], [17.369, 78.4735], [17.3616, 78.4747],
  ],
}

/* ---------------------------------------------------------------- traffic */
/* Coloured overlay segments — the "live" congestion picture. */
export const TRAFFIC_SEGMENTS = [
  { id: 't1', name: 'Jubilee Hills Road No. 36', level: 'low', congestion: 0.14,
    path: [[17.4239, 78.4138], [17.418, 78.429]] },
  { id: 't2', name: 'Banjara Hills Road No. 1', level: 'moderate', congestion: 0.42,
    path: [[17.4126, 78.4482], [17.405, 78.445], [17.395, 78.436]] },
  { id: 't3', name: 'Mehdipatnam – Masab Tank', level: 'severe', congestion: 0.88,
    path: [[17.395, 78.436], [17.393, 78.448]] },
  { id: 't4', name: 'Nampally – Charminar', level: 'heavy', congestion: 0.67,
    path: [[17.388, 78.465], [17.38, 78.47], [17.37, 78.473], [17.3616, 78.4747]] },
  { id: 't5', name: 'Madhapur Main Road', level: 'moderate', congestion: 0.38,
    path: [[17.4435, 78.3772], [17.4483, 78.3915]] },
  { id: 't6', name: 'Panjagutta Flyover', level: 'heavy', congestion: 0.71,
    path: [[17.4256, 78.45], [17.418, 78.456]] },
  { id: 't7', name: 'Ameerpet – Begumpet', level: 'moderate', congestion: 0.49,
    path: [[17.4374, 78.4487], [17.4443, 78.4649]] },
  { id: 't8', name: 'Tank Bund Road', level: 'low', congestion: 0.21,
    path: [[17.4239, 78.4738], [17.4344, 78.5013]] },
  { id: 't9', name: 'Gachibowli – Kondapur', level: 'low', congestion: 0.18,
    path: [[17.4401, 78.3489], [17.464, 78.364]] },
  { id: 't10', name: 'Dilsukhnagar – LB Nagar', level: 'severe', congestion: 0.83,
    path: [[17.3687, 78.5247], [17.3457, 78.5522]] },
  { id: 't11', name: 'Uppal Ring Road', level: 'heavy', congestion: 0.62,
    path: [[17.402, 78.559], [17.425, 78.558]] },
  { id: 't12', name: 'PVNR Expressway', level: 'low', congestion: 0.12,
    path: [[17.361, 78.423], [17.33, 78.42], [17.2403, 78.4294]] },
]

export const TRAFFIC_COLORS = {
  low: '#A3E635',
  moderate: '#FFB020',
  heavy: '#FF6B35',
  severe: '#FF4D5A',
}


export const TRAFFIC_LABELS = {
  low: 'Low',
  moderate: 'Moderate',
  heavy: 'Heavy',
  severe: 'Severe',
}

export const INCIDENTS = [
  { id: 'i1', type: 'accident', name: 'Multi-vehicle collision',
    location: 'Mehdipatnam Junction', coords: [17.395, 78.436],
    severity: 'severe', reportedAt: '5 min ago',
    description: 'Two lanes blocked. Traffic police on site.' },
  { id: 'i2', type: 'closure', name: 'Road closure — metro works',
    location: 'Nampally Station Road', coords: [17.388, 78.465],
    severity: 'heavy', reportedAt: '32 min ago',
    description: 'Carriageway closed until 18:00. Diversion via Abids.' },
  { id: 'i3', type: 'congestion', name: 'Heavy congestion',
    location: 'Panjagutta Flyover', coords: [17.4256, 78.45],
    severity: 'heavy', reportedAt: '12 min ago',
    description: 'Peak-hour build-up. Average speed 11 km/h.' },
  { id: 'i4', type: 'waterlogging', name: 'Waterlogging reported',
    location: 'Dilsukhnagar', coords: [17.3687, 78.5247],
    severity: 'moderate', reportedAt: '48 min ago',
    description: 'Slow-moving traffic in the right lane.' },
]

/* ----------------------------------------------------------------- alerts */
export const ALERTS = [
  { id: 'a1', kind: 'predictive', severity: 'severe', title: 'Predictive congestion alert',
    location: 'Mehdipatnam – Masab Tank', time: '2 min ago',
    current: 0.62, predicted: 0.91, etaMinutes: 15,
    description: 'Congestion on your current route is forecast to rise sharply.',
    action: 'Consider an alternate route via Panjagutta.' },
  { id: 'a2', kind: 'incident', severity: 'severe', title: 'Accident reported',
    location: 'Mehdipatnam Junction', time: '5 min ago',
    description: 'Multi-vehicle collision blocking two lanes.',
    action: 'Avoid the junction for the next 30 minutes.' },
  { id: 'a3', kind: 'reroute', severity: 'moderate', title: 'Better route available',
    location: 'Hitec City → Charminar', time: '8 min ago',
    description: 'An alternative route is currently 7 minutes faster.',
    action: 'Switch to the new QPSO route.' },
  { id: 'a4', kind: 'incident', severity: 'heavy', title: 'Road closure',
    location: 'Nampally Station Road', time: '32 min ago',
    description: 'Metro construction. Closed until 18:00.',
    action: 'Diversion via Abids is in effect.' },
  { id: 'a5', kind: 'predictive', severity: 'moderate', title: 'Predictive congestion alert',
    location: 'Ameerpet – Begumpet', time: '41 min ago',
    current: 0.49, predicted: 0.68, etaMinutes: 25,
    description: 'Evening peak build-up expected.',
    action: 'Depart before 17:30 to avoid delay.' },
]

/* -------------------------------------------------------------- analytics */
export const TRAFFIC_TREND = [
  { hour: '00:00', congestion: 12, vehicles: 420 },
  { hour: '02:00', congestion: 8, vehicles: 210 },
  { hour: '04:00', congestion: 9, vehicles: 260 },
  { hour: '06:00', congestion: 28, vehicles: 1150 },
  { hour: '08:00', congestion: 74, vehicles: 3420 },
  { hour: '10:00', congestion: 52, vehicles: 2480 },
  { hour: '12:00', congestion: 46, vehicles: 2260 },
  { hour: '14:00', congestion: 44, vehicles: 2180 },
  { hour: '16:00', congestion: 58, vehicles: 2740 },
  { hour: '18:00', congestion: 86, vehicles: 3910 },
  { hour: '20:00', congestion: 61, vehicles: 2830 },
  { hour: '22:00', congestion: 31, vehicles: 1240 },
]

export const PREDICTION_SERIES = [
  { time: 'now', actual: 62, predicted: 62 },
  { time: '+5m', actual: 68, predicted: 71 },
  { time: '+10m', actual: 79, predicted: 82 },
  { time: '+15m', actual: null, predicted: 91 },
  { time: '+20m', actual: null, predicted: 88 },
  { time: '+25m', actual: null, predicted: 74 },
  { time: '+30m', actual: null, predicted: 59 },
]

export const ROUTE_PERFORMANCE = [
  { route: 'Hitec → Charminar', distance: 18.9, time: 38 },
  { route: 'Gachibowli → Secbad', distance: 21.4, time: 44 },
  { route: 'Miyapur → LB Nagar', distance: 30.4, time: 62 },
  { route: 'Kukatpally → Uppal', distance: 24.8, time: 51 },
  { route: 'Hitec → Airport', distance: 34.1, time: 46 },
]

export const TRAFFIC_DISTRIBUTION = [
  { name: 'Low', value: 34, color: '#A3E635' },
  { name: 'Moderate', value: 29, color: '#FFB020' },
  { name: 'Heavy', value: 24, color: '#FF6B35' },
  { name: 'Severe', value: 13, color: '#FF4D5A' },
]

export const ANALYTICS_STATS = [
  { label: 'Average Traffic', value: 47, suffix: '%', trend: +4.2, tone: 'yellow' },
  { label: 'Average Delay', value: 11, suffix: ' min', trend: +1.8, tone: 'orange' },
  { label: 'Congestion Level', value: 62, suffix: '%', trend: +9.1, tone: 'red' },
  { label: 'Predicted Congestion', value: 91, suffix: '%', trend: +29, tone: 'red' },
  { label: 'Active Incidents', value: 4, suffix: '', trend: +2, tone: 'orange' },
  { label: 'Routes Optimized', value: 1284, suffix: '', trend: +12.4, tone: 'cyan' },
]

/* ------------------------------------------------------------- benchmark */
/*
 * IMPORTANT — read before presenting.
 *
 * On a single source→destination problem with additively-combined weights,
 * Dijkstra is provably optimal. The numbers below reflect that honestly:
 * Dijkstra attains the best objective value and the fastest runtime, and QPSO
 * lands close to it. Do NOT edit these to make QPSO "win" — the defensible
 * claim is that QPSO reaches near-optimal quality on a problem where the
 * optimum is known, which validates the implementation before applying it to
 * constrained problems Dijkstra cannot solve.
 */
export const BENCHMARK = {
  isDemoData: true,
  problem: 'Hitec City → Charminar · balanced mode · 30 trials',
  rows: [
    { algorithm: 'Dijkstra', deterministic: true,
      distanceKm: 18.9, timeMin: 38.0, congestion: 0.220, runtimeMs: 512,
      fitness: 0.4120, fitnessStd: 0, fitnessBest: 0.4120, fitnessWorst: 0.4120,
      iterations: null, validity: 100 },
    { algorithm: 'QPSO', deterministic: false,
      distanceKm: 19.1, timeMin: 38.6, congestion: 0.224, runtimeMs: 1840,
      fitness: 0.4183, fitnessStd: 0.0071, fitnessBest: 0.4120, fitnessWorst: 0.4361,
      iterations: 48, validity: 100 },
    { algorithm: 'PSO', deterministic: false,
      distanceKm: 19.6, timeMin: 40.1, congestion: 0.241, runtimeMs: 1710,
      fitness: 0.4372, fitnessStd: 0.0134, fitnessBest: 0.4142, fitnessWorst: 0.4708,
      iterations: 62, validity: 97 },
    { algorithm: 'Genetic Algorithm', deterministic: false,
      distanceKm: 20.0, timeMin: 41.3, congestion: 0.253, runtimeMs: 2260,
      fitness: 0.4491, fitnessStd: 0.0186, fitnessBest: 0.4198, fitnessWorst: 0.4922,
      iterations: 80, validity: 94 },
  ],
}

/* -------------------------------------------------------- convergence */
/* Generated once at module load so the curve is stable across renders. */
function convergenceCurve(start, floor, rate, iterations, jitter, seed) {
  let s = seed
  const rand = () => {
    s = (s * 1103515245 + 12345) % 2147483648
    return s / 2147483648
  }
  const out = []
  let best = start
  for (let i = 0; i <= iterations; i++) {
    const target = floor + (start - floor) * Math.exp(-rate * i)
    const candidate = target + (rand() - 0.5) * jitter
    best = Math.min(best, candidate)
    out.push(Number(best.toFixed(4)))
  }
  return out
}

const ITER = 80
export const CONVERGENCE = {
  isDemoData: true,
  iterations: ITER,
  series: {
    QPSO: convergenceCurve(0.92, 0.412, 0.115, ITER, 0.012, 7),
    PSO: convergenceCurve(0.94, 0.436, 0.072, ITER, 0.018, 21),
    GA: convergenceCurve(0.96, 0.449, 0.055, ITER, 0.026, 43),
  },
  summary: {
    QPSO: { iterations: 48, bestFitness: 0.4183, executionMs: 1840, converged: 94 },
    PSO: { iterations: 62, bestFitness: 0.4372, executionMs: 1710, converged: 81 },
    GA: { iterations: 80, bestFitness: 0.4491, executionMs: 2260, converged: 73 },
  },
}

/** Reshaped for Recharts: [{ iteration, QPSO, PSO, GA }, ...] */
export const CONVERGENCE_CHART_DATA = Array.from({ length: ITER + 1 }, (_, i) => ({
  iteration: i,
  QPSO: CONVERGENCE.series.QPSO[i],
  PSO: CONVERGENCE.series.PSO[i],
  GA: CONVERGENCE.series.GA[i],
}))

/* ------------------------------------------------------------ scalability */
export const SCALABILITY = {
  isDemoData: true,
  rows: [
    { nodes: 100, dijkstra: 3, qpso: 118, pso: 104, ga: 142, qpsoQuality: 100.0 },
    { nodes: 500, dijkstra: 14, qpso: 356, pso: 331, ga: 448, qpsoQuality: 99.6 },
    { nodes: 1000, dijkstra: 31, qpso: 642, pso: 611, ga: 838, qpsoQuality: 99.1 },
    { nodes: 5000, dijkstra: 186, qpso: 2140, pso: 2080, ga: 2960, qpsoQuality: 98.2 },
    { nodes: 10000, dijkstra: 412, qpso: 3980, pso: 3910, ga: 5640, qpsoQuality: 97.4 },
  ],
}

/* --------------------------------------------------------------- history */
export const ROUTE_HISTORY = [
  { id: 'h1', date: '2026-08-27 09:14', start: 'Hitec City', end: 'Charminar',
    algorithm: 'QPSO', distanceKm: 18.9, etaMin: 38, traffic: 'moderate', status: 'completed' },
  { id: 'h2', date: '2026-08-27 08:02', start: 'Gachibowli', end: 'Secunderabad',
    algorithm: 'QPSO', distanceKm: 21.4, etaMin: 44, traffic: 'heavy', status: 'rerouted' },
  { id: 'h3', date: '2026-08-26 18:47', start: 'Miyapur', end: 'LB Nagar',
    algorithm: 'PSO', distanceKm: 30.4, etaMin: 62, traffic: 'severe', status: 'completed' },
  { id: 'h4', date: '2026-08-26 17:20', start: 'Kukatpally', end: 'Uppal',
    algorithm: 'QPSO', distanceKm: 24.8, etaMin: 51, traffic: 'heavy', status: 'completed' },
  { id: 'h5', date: '2026-08-26 11:05', start: 'Hitec City', end: 'RGIA Airport',
    algorithm: 'Dijkstra', distanceKm: 34.1, etaMin: 46, traffic: 'low', status: 'completed' },
  { id: 'h6', date: '2026-08-25 19:33', start: 'Banjara Hills', end: 'Dilsukhnagar',
    algorithm: 'QPSO', distanceKm: 14.2, etaMin: 39, traffic: 'severe', status: 'rerouted' },
  { id: 'h7', date: '2026-08-25 14:12', start: 'Ameerpet', end: 'Uppal',
    algorithm: 'GA', distanceKm: 17.6, etaMin: 42, traffic: 'moderate', status: 'cancelled' },
  { id: 'h8', date: '2026-08-25 09:58', start: 'Mehdipatnam', end: 'Madhapur',
    algorithm: 'QPSO', distanceKm: 12.3, etaMin: 29, traffic: 'moderate', status: 'completed' },
]

/* ------------------------------------------------- optimisation sequence */
/* Stage labels shown during the QPSO run animation. */
export const OPTIMIZATION_STAGES = [
  'Analyzing transportation network',
  'Initializing particle swarm',
  'Generating candidate routes',
  'Evaluating fitness',
  'Updating particle positions',
  'Searching solution space',
  'Converging on optimum',
  'Best route found',
]

export const ALGORITHMS = [
  { id: 'qpso', name: 'QPSO', full: 'Quantum Particle Swarm Optimization', quantum: true },
  { id: 'pso', name: 'PSO', full: 'Particle Swarm Optimization', quantum: false },
  { id: 'ga', name: 'GA', full: 'Genetic Algorithm', quantum: false },
  { id: 'dijkstra', name: 'Dijkstra', full: "Dijkstra's Shortest Path", quantum: false },
]

export const OPTIMIZATION_MODES = [
  { id: 'balanced', name: 'Balanced', weights: { time: 0.4, distance: 0.3, congestion: 0.3 } },
  { id: 'fastest', name: 'Fastest', weights: { time: 0.7, distance: 0.2, congestion: 0.1 } },
  { id: 'shortest', name: 'Shortest', weights: { time: 0.2, distance: 0.7, congestion: 0.1 } },
  { id: 'low_congestion', name: 'Low Congestion', weights: { time: 0.2, distance: 0.1, congestion: 0.7 } },
]

export const SYSTEM_STATUS = {
  version: 'v0.1.0',
  // Reflects reality rather than a hardcoded string: the sidebar badge said
  // "MOCK" even when the app was talking to the live FastAPI backend.
  backend: import.meta.env.VITE_USE_MOCK === 'false' ? 'live' : 'mock',
  graph: 'Hyderabad · 286,603 nodes · 741,203 edges',
  lastUpdated: new Date().toISOString(),
}
