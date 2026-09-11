import { useEffect, useMemo, useRef, useState } from 'react'
import {
  MapContainer,
  Marker,
  Polyline,
  Popup,
  TileLayer,
  useMap,
} from 'react-leaflet'
import L from 'leaflet'

import {
  HYDERABAD_CENTER,
  TRAFFIC_COLORS,
} from '../data/mockData'

/* ============================================================
   BASIC MAP MARKERS
   ============================================================ */

const pin = (label, color) =>
  L.divIcon({
    className: '',
    html: `<div class="marker-pin" style="background:${color};box-shadow:0 0 14px ${color}">${label}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  })

const incidentIcon = (color) =>
  L.divIcon({
    className: '',
    html: `
      <div
        class="incident-pin"
        style="
          background:${color}22;
          border:2px solid ${color};
        "
      >
        <svg
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="${color}"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
          <path d="M12 9v4"/>
          <path d="M12 17h.01"/>
        </svg>
      </div>
    `,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  })

/* ============================================================
   MAP TILES
   ============================================================ */

const TILES = {
  standard:
    'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',

  humanitarian:
    'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',
}

/* ============================================================
   DISTANCE HELPER
   ============================================================ */

function pointDistance(a, b) {
  if (!a || !b) return Infinity

  const latDiff = a[0] - b[0]
  const lngDiff = a[1] - b[1]

  return Math.sqrt(
    latDiff * latDiff +
    lngDiff * lngDiff
  )
}

/* ============================================================
   GET ROUTE IN A -> B DIRECTION
   ============================================================ */

function getDirectionalPath(
  route,
  startPoint,
  endPoint
) {
  if (
    !route?.path ||
    route.path.length < 2
  ) {
    return []
  }

  const originalPath = route.path

  /*
   * If A/B coordinates are unavailable,
   * use the original route direction.
   */

  if (
    !startPoint?.coords ||
    !endPoint?.coords
  ) {
    return originalPath
  }

  const first =
    originalPath[0]

  const last =
    originalPath[
      originalPath.length - 1
    ]

  /*
   * Check which end of the route is
   * closer to the current START.
   */

  const normalDistance =
    pointDistance(
      first,
      startPoint.coords
    )

  const reversedDistance =
    pointDistance(
      last,
      startPoint.coords
    )

  /*
   * If the last point is closer to A,
   * reverse the route.
   */

  if (
    reversedDistance <
    normalDistance
  ) {
    return [
      ...originalPath,
    ].reverse()
  }

  return originalPath
}

/* ============================================================
   FIT MAP TO ROUTES
   ============================================================ */

function FitBounds({
  routes,
  fallbackCenter,
}) {
  const map = useMap()

  useEffect(() => {
    if (!routes?.length) {
      map.setView(
        fallbackCenter,
        12,
        {
          animate: true,
        }
      )

      return
    }

    const pts =
      routes.flatMap(
        (r) => r.path || []
      )

    if (!pts.length) return

    const bounds = L.latLngBounds(pts).pad(0.18)
    map.flyToBounds(bounds, { duration: 0.85 })

    // Re-fit when the container changes size. Fitting is relative to the
    // viewport Leaflet had at the time, so a map that grows or shrinks
    // afterwards leaves the route occupying a fraction of the space — measured
    // at 256x83px inside a 664x755px map, which reads as a tiny squiggle
    // rather than a journey. invalidateSize alone does not correct it: it
    // updates the size and keeps the old zoom.
    if (typeof ResizeObserver === 'undefined') return undefined

    let frame = 0
    let first = true
    const observer = new ResizeObserver(() => {
      // The observer fires once on attach with the current size; refitting
      // then would fight the flyToBounds still animating above.
      if (first) { first = false; return }
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        map.invalidateSize({ animate: false })
        map.fitBounds(bounds, { animate: false })
      })
    })
    observer.observe(map.getContainer())

    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
    }
  }, [
    routes,
    map,
    fallbackCenter,
  ])

  return null
}

/* ============================================================
   LEAFLET SIZE FIX
   ============================================================ */

function InvalidateOnMount() {
  const map = useMap()

  useEffect(() => {
    const timer =
      setTimeout(() => {
        map.invalidateSize()
      }, 180)

    return () =>
      clearTimeout(timer)
  }, [map])

  return null
}

/**
 * Cap the map to the space actually below it.
 *
 * Every previous attempt at this was a guess at how far down the page the map
 * begins — `100vh - 32px`, `100vh - navbar - 260px` — and each was wrong
 * somewhere. The optimizer starts its map 177px down, Live Traffic 356px, and
 * both move with the viewport. A constant cannot be right for both, so this
 * measures the element instead of predicting it.
 *
 * Runs on mount and on every resize, so it stays correct when the window
 * changes or the panels beside it grow.
 */
function FitToViewport({ gutter = 16 }) {
  const map = useMap()

  useEffect(() => {
    const shell = map.getContainer().closest('.map-shell')
    if (!shell) return undefined

    const apply = () => {
      const top = shell.getBoundingClientRect().top
      // A sticky element reports its pinned position once stuck, which is the
      // right number to use either way: it is where the map actually sits.
      const available = Math.max(window.innerHeight - top - gutter, 240)

      // height, and BOTH bounds. max-height alone loses to a min-height floor:
      // .map-shell carries min-height 580px and Live Traffic added 420px
      // inline, so on a 768px-tall screen the floor kept the map 8px past the
      // fold no matter what the cap said. Setting all three leaves nothing to
      // argue with.
      const px = `${available}px`
      shell.style.height = px
      shell.style.minHeight = px
      shell.style.maxHeight = px
    }

    apply()
    window.addEventListener('resize', apply)
    const observer = typeof ResizeObserver !== 'undefined'
      ? new ResizeObserver(apply)
      : null
    // Watching the page, not the shell: the shell's own height is what we set,
    // and observing that would loop.
    observer?.observe(document.body)

    return () => {
      window.removeEventListener('resize', apply)
      observer?.disconnect()
    }
  }, [map, gutter])

  return null
}

/**
 * Keep Leaflet's idea of its own size in step with the element.
 *
 * Covers the no-route case; when routes are present FitBounds re-fits as well
 * as re-measuring, because a correct size with a stale zoom still shows the
 * route in the wrong place.
 *
 * Leaflet measures the container once and only re-measures on a WINDOW resize.
 * This map lives in a grid row whose height is set by its siblings, so listing
 * three routes instead of one grows the map without the window changing at all.
 * Leaflet then keeps a stale size and requests only enough tiles for the old
 * one — a long intercity route showed the polyline drawn over bare background,
 * because the tiles for the newly exposed area were never asked for.
 *
 * A ResizeObserver watches the element itself, which is the thing that actually
 * changes.
 */
function InvalidateOnResize() {
  const map = useMap()

  useEffect(() => {
    const el = map.getContainer()
    if (typeof ResizeObserver === 'undefined') return undefined

    let frame = 0
    const observer = new ResizeObserver(() => {
      // Coalesced into one frame: a resize fires repeatedly during layout, and
      // invalidateSize on every tick would refetch tiles the whole way.
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => map.invalidateSize({ animate: false }))
    })
    observer.observe(el)

    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
    }
  }, [map])

  return null
}

/* ============================================================
   MAIN OPTIMIZED CAR
   ============================================================ */

function AnimatedCar({
  route,
  startPoint,
  endPoint,
  active = true,
}) {
  const [position, setPosition] =
    useState(null)

  const [angle, setAngle] =
    useState(0)

  /*
   * Build the route specifically in
   * the current A -> B direction.
   */

  const directionalPath =
    useMemo(
      () =>
        getDirectionalPath(
          route,
          startPoint,
          endPoint
        ),
      [
        route,
        startPoint,
        endPoint,
      ]
    )

  useEffect(() => {
    /*
     * Clear the old car immediately
     * when A/B changes.
     */

    setPosition(null)
    setAngle(0)

    if (
      !active ||
      directionalPath.length < 2
    ) {
      return
    }

    let segment = 0
    let progress = 0

    let animationFrame

    const animate = () => {
      if (
        segment >=
        directionalPath.length - 1
      ) {
        /*
         * When the car reaches B,
         * restart from A.
         */

        segment = 0
        progress = 0
      }

      const start =
        directionalPath[segment]

      const end =
        directionalPath[
          segment + 1
        ]

      if (!start || !end) {
        return
      }

      const lat =
        start[0] +
        (end[0] - start[0]) *
          progress

      const lng =
        start[1] +
        (end[1] - start[1]) *
          progress

      setPosition([
        lat,
        lng,
      ])

      /*
       * Calculate vehicle direction.
       */

      const dx =
        end[1] - start[1]

      const dy =
        end[0] - start[0]

      const direction =
        Math.atan2(dx, dy) *
        (180 / Math.PI)

      setAngle(direction)

      progress += 0.006

      if (progress >= 1) {
        progress = 0
        segment += 1
      }

      animationFrame =
        requestAnimationFrame(
          animate
        )
    }

    animate()

    return () => {
      cancelAnimationFrame(
        animationFrame
      )
    }
  }, [
    directionalPath,
    active,
  ])

  if (!position) {
    return null
  }

  const carIcon =
    L.divIcon({
      className:
        'animated-car-marker',

      html: `
        <div
          class="animated-car"
          style="
            transform:rotate(${angle}deg);
          "
        >

          <div class="car-glow"></div>

          <div class="car-body">

            <div class="car-roof">
              <div class="car-window"></div>
            </div>

            <div class="car-headlight left"></div>
            <div class="car-headlight right"></div>

            <div class="car-wheel left"></div>
            <div class="car-wheel right"></div>

          </div>

        </div>
      `,

      iconSize: [
        32,
        32,
      ],

      iconAnchor: [
        16,
        16,
      ],
    })

  return (
    <Marker
      position={position}
      icon={carIcon}
      interactive={false}
      zIndexOffset={1000}
    />
  )
}

/* ============================================================
   NAVIGATION CAR — the user's own car, driving their trip
   ============================================================ */

const EARTH_RADIUS_M = 6371008.8

function haversineM(a, b) {
  const toRad = Math.PI / 180
  const dLat = (b[0] - a[0]) * toRad
  const dLon = (b[1] - a[1]) * toRad
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(a[0] * toRad) * Math.cos(b[0] * toRad) * Math.sin(dLon / 2) ** 2
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h))
}

/** Compass bearing from a to b, degrees clockwise from north — the car icon points north at 0. */
function bearingDeg(a, b) {
  const toRad = Math.PI / 180
  const y = Math.sin((b[1] - a[1]) * toRad) * Math.cos(b[0] * toRad)
  const x = Math.cos(a[0] * toRad) * Math.sin(b[0] * toRad)
    - Math.sin(a[0] * toRad) * Math.cos(b[0] * toRad) * Math.cos((b[1] - a[1]) * toRad)
  return (Math.atan2(y, x) * 180) / Math.PI
}

// A top-down car pointing north, so rotating it by the compass bearing points
// it along the road. Drawn as SVG: the older car markup above relies on
// .car-body / .car-wheel styles that were never written, and renders nothing.
// Not given the 'animated-car-marker' class either — that class's
// reduced-motion rule sets transform:none, which is how Leaflet positions a
// marker, and would pin the car to the map's corner.
const NAV_CAR_ICON = L.divIcon({
  className: 'nav-car-marker',
  html: `
    <div class="nav-car" role="img" aria-label="Your car">
      <svg viewBox="0 0 32 32" width="32" height="32" aria-hidden="true">
        <ellipse cx="16.5" cy="17.5" rx="9.5" ry="13.5" fill="rgba(0,0,0,0.28)"/>
        <rect x="8" y="3" width="16" height="26" rx="6" fill="#FF6B35" stroke="#ffffff" stroke-width="1.6"/>
        <rect x="10.4" y="8.2" width="11.2" height="6" rx="2" fill="#dbe9ff"/>
        <rect x="10.8" y="19.4" width="10.4" height="4.6" rx="1.8" fill="#b9cbe6"/>
        <rect x="9.6" y="3.6" width="3.2" height="2" rx="1" fill="#fff4b8"/>
        <rect x="19.2" y="3.6" width="3.2" height="2" rx="1" fill="#fff4b8"/>
      </svg>
    </div>`,
  iconSize: [32, 32],
  iconAnchor: [16, 16],
})

/**
 * The car follows the route's real geometry at a steady speed.
 *
 * The admin map's car (AnimatedCar above) loops forever and gives every
 * segment the same number of frames, so it crawls through a junction's short
 * segments and races down a long straight. This one moves by DISTANCE: it
 * knows how many metres along the road it is, advances by speed × time each
 * frame, and finds the segment that distance falls in. It drives once, from
 * source to destination, and stops.
 *
 * It moves the Leaflet marker directly rather than through React state, so a
 * frame costs a setLatLng, not a re-render of the map.
 *
 * When the route is switched mid-journey, the new route begins where the
 * driver was when the agent decided — a few seconds behind the car. Starting
 * at the new route's nearest point to the car keeps it where it is instead of
 * jumping back.
 */
function NavigationCar({ path, legKey, running, speedMps, onProgress, onArrive }) {
  const map = useMap()
  const markerRef = useRef(null)
  const distRef = useRef(0)
  const lastPosRef = useRef(null)
  const arrivedRef = useRef(false)
  const callbacks = useRef({ onProgress, onArrive })
  callbacks.current = { onProgress, onArrive }

  // One leg = one path. Keyed on the leg, not the array: the same path handed
  // down again by a re-render must not restart the car.
  const leg = useMemo(() => {
    const cum = [0]
    for (let i = 1; i < path.length; i += 1) cum.push(cum[i - 1] + haversineM(path[i - 1], path[i]))

    // Where this leg begins: the start of the route, or the point nearest the car.
    let startIndex = 0
    const here = lastPosRef.current
    if (here) {
      let bestD = Infinity
      path.forEach((p, i) => {
        const d = haversineM(here, p)
        if (d < bestD) { bestD = d; startIndex = i }
      })
    }
    return { cum, total: cum[cum.length - 1] || 0, startIndex, first: path[startIndex] }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [legKey])

  const place = (dist) => {
    const { cum } = leg
    // Binary search for the segment the distance falls in.
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
    const pos = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
    lastPosRef.current = pos

    const marker = markerRef.current
    if (marker) {
      marker.setLatLng(pos)
      const el = marker.getElement()?.querySelector('.nav-car')
      if (el && (a[0] !== b[0] || a[1] !== b[1])) el.style.transform = `rotate(${bearingDeg(a, b)}deg)`
    }
    // Progress in road nodes is what the server's trip counts in.
    return { pos, nodeFraction: path.length > 1 ? (lo + t) / (path.length - 1) : 1 }
  }

  // A new leg starts at its own start point (or next to the car).
  useEffect(() => {
    distRef.current = leg.cum[leg.startIndex] || 0
    arrivedRef.current = false
  }, [leg])

  useEffect(() => {
    if (!leg.total) return undefined
    const { pos } = place(distRef.current)
    if (!running || arrivedRef.current) return undefined

    let frame
    let last = performance.now()
    let lastReport = 0
    let lastPan = 0
    let done = false
    if (!map.getBounds().contains(pos)) map.panTo(pos, { animate: true })

    const step = (now) => {
      // Capped, so a long stall resumes with a short hop rather than a leap.
      const dt = Math.min((now - last) / 1000, 2)
      last = now
      distRef.current = Math.min(distRef.current + speedMps * dt, leg.total)
      const { pos: here, nodeFraction } = place(distRef.current)

      if (now - lastReport > 2000) {
        lastReport = now
        callbacks.current.onProgress?.(nodeFraction, distRef.current / leg.total)
      }
      // Keep the car in view, without fighting someone panning the map.
      if (now - lastPan > 1500) {
        lastPan = now
        if (!map.getBounds().pad(-0.15).contains(here)) map.panTo(here, { animate: true })
      }
      if (distRef.current >= leg.total) {
        done = true
        arrivedRef.current = true
        callbacks.current.onProgress?.(1, 1)
        callbacks.current.onArrive?.()
      }
    }

    // Smooth motion comes from animation frames. Browsers stop sending those
    // to a tab in the background — and the two-tab demo puts the user's tab
    // there while the admin works — so a watchdog keeps the trip moving at
    // the same speed whenever frames stop arriving.
    const tick = (now) => {
      if (done) return
      step(now)
      if (!done) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    const watchdog = setInterval(() => {
      const now = performance.now()
      if (!done && now - last > 300) step(now)
    }, 250)
    return () => { cancelAnimationFrame(frame); clearInterval(watchdog) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, leg, speedMps])

  if (!leg.first) return null
  return (
    <Marker
      ref={markerRef}
      position={leg.first}
      icon={NAV_CAR_ICON}
      interactive={false}
      zIndexOffset={1200}
    />
  )
}

/* ============================================================
   SMALL TRAFFIC CAR
   ============================================================ */

function TrafficCar({
  route,
  startPoint,
  endPoint,
  speed = 1,
  delay = 0,
  color = '#facc15',
}) {
  const [position, setPosition] =
    useState(null)

  const [angle, setAngle] =
    useState(0)

  const directionalPath =
    useMemo(
      () =>
        getDirectionalPath(
          route,
          startPoint,
          endPoint
        ),
      [
        route,
        startPoint,
        endPoint,
      ]
    )

  useEffect(() => {
    setPosition(null)
    setAngle(0)

    if (
      directionalPath.length < 2
    ) {
      return
    }

    let segment = 0

    /*
     * Delay controls starting position
     * along the route.
     */

    let progress = delay

    let animationFrame

    const animate = () => {
      if (
        segment >=
        directionalPath.length - 1
      ) {
        segment = 0
        progress = 0
      }

      const start =
        directionalPath[segment]

      const end =
        directionalPath[
          segment + 1
        ]

      if (!start || !end) {
        return
      }

      const lat =
        start[0] +
        (end[0] - start[0]) *
          progress

      const lng =
        start[1] +
        (end[1] - start[1]) *
          progress

      setPosition([
        lat,
        lng,
      ])

      const dx =
        end[1] - start[1]

      const dy =
        end[0] - start[0]

      setAngle(
        Math.atan2(dx, dy) *
          (180 / Math.PI)
      )

      progress +=
        0.0025 * speed

      if (progress >= 1) {
        progress = 0
        segment += 1
      }

      animationFrame =
        requestAnimationFrame(
          animate
        )
    }

    animate()

    return () => {
      cancelAnimationFrame(
        animationFrame
      )
    }
  }, [
    directionalPath,
    speed,
    delay,
  ])

  if (!position) {
    return null
  }

  const icon =
    L.divIcon({
      className:
        'traffic-car-marker',

      html: `
        <div
          class="traffic-car"
          style="
            transform:rotate(${angle}deg);
            --traffic-car-color:${color};
          "
        >

          <div class="traffic-car-shadow"></div>

          <div class="traffic-car-body">

            <div class="traffic-car-roof">
              <div class="traffic-car-window"></div>
            </div>

            <div class="traffic-car-light left"></div>
            <div class="traffic-car-light right"></div>

            <div class="traffic-car-wheel left"></div>
            <div class="traffic-car-wheel right"></div>

          </div>

        </div>
      `,

      iconSize: [
        24,
        24,
      ],

      iconAnchor: [
        12,
        12,
      ],
    })

  return (
    <Marker
      position={position}
      icon={icon}
      interactive={false}
      zIndexOffset={700}
    />
  )
}

/* ============================================================
   MAIN MAP
   ============================================================ */

export default function MapView({
  routes = [],
  selectedRouteId = null,

  /*
   * Kept for compatibility with Dashboard.
   * We intentionally do not draw these as roads.
   */

  segments = [],

  incidents = [],
  startPoint = null,
  endPoint = null,

  showTraffic = true,
  showIncidents = true,

  highlightCoords = null,

  onSelectRoute,

  mapStyle = 'standard',

  center = HYDERABAD_CENTER,
  zoom = 12,

  /*
   * The user's trip: { path, legKey, running, speedMps, onProgress, onArrive }.
   * When present, the user's own car drives it; the admin map passes nothing
   * and keeps its looping car exactly as before.
   */
  navigation = null,
  // The small cars that illustrate traffic on the route. The user map turns
  // them off, so the only car on it is theirs.
  decorativeCars = true,
}) {
  /* ==========================================================
     ORDER ROUTES
     ========================================================== */

  const ordered =
    useMemo(() => {
      const selected =
        routes.filter(
          (r) =>
            r.id ===
            selectedRouteId
        )

      const rest =
        routes.filter(
          (r) =>
            r.id !==
            selectedRouteId
        )

      return [
        ...rest,
        ...selected,
      ]
    }, [
      routes,
      selectedRouteId,
    ])

  /* ==========================================================
     ACTIVE ROUTE
     ========================================================== */

  const selectedRoute =
    routes.find(
      (r) =>
        r.id ===
        selectedRouteId
    ) || null

  /* ==========================================================
     TRAFFIC LEVEL
     ========================================================== */

  const trafficLevel =
    selectedRoute?.congestion <
    0.3
      ? 'low'
      : selectedRoute?.congestion <
          0.5
        ? 'moderate'
        : selectedRoute?.congestion <
            0.7
          ? 'heavy'
          : 'severe'

  const trafficColor =
    TRAFFIC_COLORS[
      trafficLevel
    ] || '#facc15'

  /* ==========================================================
     RENDER
     ========================================================== */

  return (
    <MapContainer
      center={center}
      zoom={zoom}
      zoomControl
      scrollWheelZoom
      style={{
        height: '100%',
        width: '100%',
      }}
    >

      {/* ======================================================
          MAP
          ====================================================== */}

      <TileLayer
        url={
          TILES[mapStyle] ||
          TILES.standard
        }
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        maxZoom={19}
      />

      <FitToViewport />
      <InvalidateOnMount />
      <InvalidateOnResize />

      <FitBounds
        routes={routes}
        fallbackCenter={center}
      />

      {/* ======================================================
          ROUTES
          ====================================================== */}

      {ordered.map((r) => {
        const selected =
          r.id ===
          selectedRouteId

        if (
          !r.path ||
          r.path.length < 2
        ) {
          return null
        }

        /*
         * Display route in current A -> B
         * direction as well.
         */

        const displayPath =
          getDirectionalPath(
            r,
            startPoint,
            endPoint
          )

        return (
          <div key={r.id}>

            {/* Active route glow */}

            {selected && (
              <Polyline
                positions={
                  displayPath
                }
                pathOptions={{
                  color: r.color,
                  weight: 15,
                  opacity: 0.18,
                  lineCap:
                    'round',
                }}
              />
            )}

            {/* Actual route */}

            <Polyline
              positions={
                displayPath
              }
              eventHandlers={{
                click: () =>
                  onSelectRoute?.(
                    r.id
                  ),
              }}
              pathOptions={{
                color: r.color,
                weight: selected
                  ? 5.5
                  : 3.5,

                opacity: selected
                  ? 1
                  : 0.5,

                dashArray: selected
                  ? null
                  : '9 9',

                lineCap:
                  'round',

                className:
                  selected
                    ? 'route-flow'
                    : undefined,
              }}
            >

              <Popup>

                <strong>
                  {r.label}
                </strong>

                <br />

                {r.distanceKm} km ·{' '}
                {r.etaMin} min ·{' '}

                {Math.round(
                  r.congestion *
                    100
                )}
                % congestion

                {r.via && (
                  <>
                    <br />
                    <em>
                      {r.via}
                    </em>
                  </>
                )}

              </Popup>

            </Polyline>

          </div>
        )
      })}

      {/* ======================================================
          MAIN CAR
          ====================================================== */}

      {navigation?.path?.length >= 2 && (
        <NavigationCar
          path={navigation.path}
          legKey={navigation.legKey}
          running={navigation.running}
          speedMps={navigation.speedMps}
          onProgress={navigation.onProgress}
          onArrive={navigation.onArrive}
        />
      )}

      {showTraffic &&
        !navigation &&
        selectedRoute && (
          <AnimatedCar
            key={`
              ${selectedRoute.id}-
              ${startPoint?.id}-
              ${endPoint?.id}
            `}
            route={
              selectedRoute
            }
            startPoint={
              startPoint
            }
            endPoint={
              endPoint
            }
            active={
              true
            }
          />
        )}

      {/* ======================================================
          TRAFFIC CARS
          ====================================================== */}

      {showTraffic &&
        decorativeCars &&
        selectedRoute &&
        selectedRoute.path
          ?.length >= 2 && (
          <>
            <TrafficCar
              key={`
                traffic-1-
                ${selectedRoute.id}-
                ${startPoint?.id}-
                ${endPoint?.id}
              `}
              route={
                selectedRoute
              }
              startPoint={
                startPoint
              }
              endPoint={
                endPoint
              }
              speed={
                trafficLevel ===
                'low'
                  ? 1.7
                  : trafficLevel ===
                      'moderate'
                    ? 1.2
                    : trafficLevel ===
                        'heavy'
                      ? 0.8
                      : 0.5
              }
              delay={0.22}
              color={
                trafficColor
              }
            />

            <TrafficCar
              key={`
                traffic-2-
                ${selectedRoute.id}-
                ${startPoint?.id}-
                ${endPoint?.id}
              `}
              route={
                selectedRoute
              }
              startPoint={
                startPoint
              }
              endPoint={
                endPoint
              }
              speed={
                trafficLevel ===
                'low'
                  ? 1.5
                  : trafficLevel ===
                      'moderate'
                    ? 1.05
                    : trafficLevel ===
                        'heavy'
                      ? 0.7
                      : 0.45
              }
              delay={0.58}
              color={
                trafficColor
              }
            />

            {trafficLevel !==
              'low' && (
              <TrafficCar
                key={`
                  traffic-3-
                  ${selectedRoute.id}-
                  ${startPoint?.id}-
                  ${endPoint?.id}
                `}
                route={
                  selectedRoute
                }
                startPoint={
                  startPoint
                }
                endPoint={
                  endPoint
                }
                speed={
                  trafficLevel ===
                  'moderate'
                    ? 0.95
                    : trafficLevel ===
                        'heavy'
                      ? 0.65
                      : 0.4
                }
                delay={0.82}
                color={
                  trafficColor
                }
              />
            )}
          </>
        )}

      {/* ======================================================
          START (Origin: Blue Marker)
          ====================================================== */}

      {startPoint && (
        <Marker
          position={
            startPoint.coords
          }
          icon={pin(
            'A',
            '#2F6FED'
          )}
        >
          <Popup>
            Start ·{' '}
            {
              startPoint.name
            }
          </Popup>
        </Marker>
      )}

      {/* ======================================================
          DESTINATION (Destination: Forest Green Marker)
          ====================================================== */}

      {endPoint && (
        <Marker
          position={
            endPoint.coords
          }
          icon={pin(
            'B',
            '#1F4D3A'
          )}
        >
          <Popup>
            Destination ·{' '}
            {
              endPoint.name
            }
          </Popup>
        </Marker>
      )}

      {/* ======================================================
          INCIDENTS
          ====================================================== */}

      {showIncidents &&
        incidents.map((i) => (
          <Marker
            key={i.id}
            position={
              i.coords
            }
            icon={incidentIcon(
              TRAFFIC_COLORS[
                i.severity
              ]
            )}
          >
            <Popup>

              <strong>
                {i.name}
              </strong>

              <br />

              {i.location} ·{' '}
              {
                i.reportedAt
              }

              <br />

              {
                i.description
              }

            </Popup>
          </Marker>
        ))}

      {/* ======================================================
          PREDICTIVE ALERT
          ====================================================== */}

      {highlightCoords && (
        <Marker
          position={
            highlightCoords
          }
          icon={incidentIcon(
            '#D64545'
          )}
        >
          <Popup>
            Predicted
            congestion
            spike
          </Popup>
        </Marker>
      )}

    </MapContainer>
  )
}