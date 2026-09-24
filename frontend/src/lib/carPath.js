/**
 * Route geometry: which way a route runs, and where along it the car is.
 *
 * All of this is arithmetic on [lat, lon] pairs — no map library appears in
 * this file. Both maps use it: MapView's Leaflet markers and polylines, and
 * MapView3D's MapLibre ones. Kept shared on purpose, because a second copy of
 * "how far along is the car" or "which end is the start" is exactly the kind
 * of thing that drifts and then disagrees with itself in a demo.
 */

const EARTH_RADIUS_M = 6371008.8
const TO_RAD = Math.PI / 180

/** Great-circle metres between two [lat, lon] points. */
export function haversineM(a, b) {
  const dLat = (b[0] - a[0]) * TO_RAD
  const dLon = (b[1] - a[1]) * TO_RAD
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(a[0] * TO_RAD) * Math.cos(b[0] * TO_RAD) * Math.sin(dLon / 2) ** 2
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h))
}

/** Compass bearing a→b, degrees clockwise from north — a car icon points north at 0. */
export function bearingDeg(a, b) {
  const y = Math.sin((b[1] - a[1]) * TO_RAD) * Math.cos(b[0] * TO_RAD)
  const x = Math.cos(a[0] * TO_RAD) * Math.sin(b[0] * TO_RAD)
    - Math.sin(a[0] * TO_RAD) * Math.cos(b[0] * TO_RAD) * Math.cos((b[1] - a[1]) * TO_RAD)
  return (Math.atan2(y, x) * 180) / Math.PI
}

/**
 * The route, running from A to B.
 *
 * A path can come back from the engine drawn either way round. Handed to the
 * map as-is, a reversed one animates its flow backwards and starts the car at
 * the destination. Compared in plain degrees rather than metres: this only has
 * to decide which of two ends is nearer, and haversine would cost more for the
 * same answer.
 */
export function orientPath(path, startCoords) {
  if (!path || path.length < 2) return []
  if (!startCoords) return path
  const sq = (a, b) => (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
  const forward = sq(path[0], startCoords)
  const reversed = sq(path[path.length - 1], startCoords)
  return reversed < forward ? [...path].reverse() : path
}

/** Running distance to each point of the path; index 0 is 0. */
export function cumulativeDistances(path) {
  const cum = [0]
  for (let i = 1; i < path.length; i += 1) {
    cum.push(cum[i - 1] + haversineM(path[i - 1], path[i]))
  }
  return cum
}

/** Index of the path point closest to `point`, or 0 when there is no point. */
export function nearestIndex(path, point) {
  if (!point) return 0
  let best = 0
  let bestD = Infinity
  path.forEach((p, i) => {
    const d = haversineM(point, p)
    if (d < bestD) { bestD = d; best = i }
  })
  return best
}

/**
 * Where the car sits `dist` metres along the path.
 *
 * Binary search for the segment, then interpolate within it. `nodeFraction` is
 * progress in road nodes rather than metres, because that is what the server's
 * trip record counts in.
 */
export function placeAlong(path, cum, dist) {
  let lo = 0
  let hi = cum.length - 1
  while (lo < hi - 1) {
    const mid = (lo + hi) >> 1
    if (cum[mid] <= dist) lo = mid
    else hi = mid
  }
  const a = path[lo]
  const b = path[Math.min(lo + 1, path.length - 1)]
  const span = cum[lo + 1] - cum[lo] || 1
  const t = Math.min(Math.max((dist - cum[lo]) / span, 0), 1)
  return {
    pos: [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t],
    nodeFraction: path.length > 1 ? (lo + t) / (path.length - 1) : 1,
    // null when the segment has no length, so a caller keeps the last heading
    // rather than snapping the car to north.
    bearing: (a[0] !== b[0] || a[1] !== b[1]) ? bearingDeg(a, b) : null,
  }
}
