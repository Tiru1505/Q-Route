import { useEffect, useRef, useState } from 'react'
// MapLibre 6 has no default export; the pieces are named.
import { Map as MapLibreMap, Marker, NavigationControl, Popup } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { Crosshair } from 'lucide-react'
import { TRAFFIC_COLORS } from '../data/mockData'
import { cumulativeDistances, nearestIndex, orientPath, placeAlong } from '../lib/carPath'

/**
 * The routing map, drawn by MapLibre instead of Leaflet.
 *
 * WHY A SECOND MAP COMPONENT
 * --------------------------
 * MapView.jsx is 1500 lines and carries the demo: the car, the incidents, the
 * follow control. Rewriting it in place would mean a half-working map for as
 * long as the port took. This one takes the SAME props, so a page can render
 * either, and it only claims the parts it has actually implemented. Leaflet
 * stays the default until this one is better.
 *
 * WHAT IS HERE SO FAR
 * -------------------
 * The basemap, the routes, the endpoint and incident pins, the driver's car
 * and the follow control. Still MapView's alone: the traffic segments and the
 * decorative cars. Passing those here does nothing rather than half-drawing
 * them, so what is on screen is always the whole of what this map claims.
 *
 * The arithmetic that drives the car lives in lib/carPath.js, shared with
 * MapView, so the two maps cannot come to disagree about where it is.
 *
 * ONE TRAP, ALREADY PAID FOR
 * --------------------------
 * MapLibre adds .maplibregl-map (position: relative, overflow: hidden) to its
 * container. A container sized only by `inset: 0` collapses to zero height
 * under that and clips the map away silently — the coverage globe lost a day
 * to exactly that. The height here is explicit for that reason.
 */

// Keyless, and genuinely dark: the Leaflet map fakes dark by CSS-inverting
// light raster tiles, which inverts the road colours along with everything
// else. This is a real dark vector style, so roads stay road-coloured.
const STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
const HYDERABAD = [78.4867, 17.385]

const cssVar = (name, fallback) => {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

/** Leaflet hands out [lat, lon]; GeoJSON wants [lon, lat]. */
const toLngLat = (path) => (path || []).map(([lat, lon]) => [lon, lat])

function routesToGeoJSON(routes, selectedId, startPoint) {
  return {
    type: 'FeatureCollection',
    features: (routes || [])
      .filter((r) => r.path?.length)
      .map((r) => ({
        type: 'Feature',
        id: r.id,
        properties: {
          id: r.id,
          selected: r.id === selectedId ? 1 : 0,
          // Each route carries its own colour from the adapter; the map paints
          // what it is given rather than deciding.
          color: r.color || '#FF6B35',
        },
        geometry: {
          type: 'LineString',
          coordinates: toLngLat(orientPath(r.path, startPoint?.coords)),
        },
      })),
  }
}

/**
 * One cycle of a travelling dash.
 *
 * Every frame sums to the same pattern length, so the dashes appear to slide
 * along rather than stretch. Stepped on a timer rather than an animation
 * frame: it is one paint property per tick, and it should keep moving when
 * the tab is in the background, like the car does.
 */
const FLOW_FRAMES = [
  [0, 4, 3], [0.5, 4, 2.5], [1, 4, 2], [1.5, 4, 1.5], [2, 4, 1], [2.5, 4, 0.5],
  [3, 4, 0], [0, 0.5, 3, 3.5], [0, 1, 3, 3], [0, 1.5, 3, 2.5], [0, 2, 3, 2],
  [0, 2.5, 3, 1.5], [0, 3, 3, 1],
]

/* ------------------------------------------------------------- markers */

// The same two classes the Leaflet map uses, so both maps draw an identical
// pin and there is only one place to restyle it.
function pinElement(label, color) {
  const el = document.createElement('div')
  el.className = 'marker-pin'
  el.style.background = color
  el.style.boxShadow = `0 0 14px ${color}`
  el.textContent = label
  return el
}

const WARNING_SVG =
  '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
  'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' +
  '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>' +
  '<path d="M12 9v4"/><path d="M12 17h.01"/></svg>'

function incidentElement(color) {
  const el = document.createElement('div')
  el.className = 'incident-pin'
  el.style.background = `${color}22`
  el.style.border = `2px solid ${color}`
  el.style.color = color
  // Static markup, no caller data — the popup below is where text goes.
  el.innerHTML = WARNING_SVG
  return el
}

/**
 * Popup content as DOM, never as an HTML string.
 *
 * react-leaflet escaped these for free by taking them as children. MapLibre's
 * setHTML does not, and an incident's name and description come from the
 * backend, so building nodes and assigning textContent keeps a crafted
 * incident from becoming script on the page.
 */
function popupContent(lines) {
  const wrap = document.createElement('div')
  wrap.className = 'map3d-popup'
  for (const line of lines) {
    if (!line?.text) continue
    const row = document.createElement(line.strong ? 'strong' : 'div')
    row.textContent = line.text
    wrap.appendChild(row)
  }
  return wrap
}

/* ----------------------------------------------------------------- car */

// The same markup and classes the Leaflet map uses, so one car is drawn in
// one place and both maps show the same vehicle.
const NAV_CAR_HTML =
  '<div class="nav-car" role="img" aria-label="Your car">' +
  '<svg viewBox="0 0 32 32" width="32" height="32" aria-hidden="true">' +
  '<ellipse cx="16.5" cy="17.5" rx="9.5" ry="13.5" fill="rgba(0,0,0,0.28)"/>' +
  '<rect x="8" y="3" width="16" height="26" rx="6" fill="#FF6B35" stroke="#ffffff" stroke-width="1.6"/>' +
  '<rect x="10.4" y="8.2" width="11.2" height="6" rx="2" fill="#dbe9ff"/>' +
  '<rect x="10.8" y="19.4" width="10.4" height="4.6" rx="1.8" fill="#b9cbe6"/>' +
  '<rect x="9.6" y="3.6" width="3.2" height="2" rx="1" fill="#fff4b8"/>' +
  '<rect x="19.2" y="3.6" width="3.2" height="2" rx="1" fill="#fff4b8"/>' +
  '</svg></div>'

function carElement() {
  const el = document.createElement('div')
  el.className = 'nav-car-marker'
  el.innerHTML = NAV_CAR_HTML   // static markup, no caller data
  return el
}

/**
 * Is `pos` inside the view, shrunk by `inset` of its own size?
 *
 * Leaflet spells this `bounds.pad(-0.15).contains(p)`; MapLibre's LngLatBounds
 * has no pad, so it is done by hand rather than letting the car wander to the
 * very edge before the map follows it.
 */
function withinInset(map, pos, inset) {
  const b = map.getBounds()
  const w = b.getWest()
  const e = b.getEast()
  const s = b.getSouth()
  const n = b.getNorth()
  const dx = (e - w) * inset
  const dy = (n - s) * inset
  const [lat, lon] = pos
  return lon > w + dx && lon < e - dx && lat > s + dy && lat < n - dy
}

function boundsOf(routes) {
  let w = 180, s = 90, e = -180, n = -90
  let seen = false
  for (const r of routes || []) {
    for (const [lat, lon] of r.path || []) {
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue
      seen = true
      if (lon < w) w = lon
      if (lon > e) e = lon
      if (lat < s) s = lat
      if (lat > n) n = lat
    }
  }
  return seen ? [[w, s], [e, n]] : null
}

export default function MapView3D({
  routes = [],
  selectedRouteId = null,
  onSelectRoute,
  center,
  zoom = 11,
  startPoint = null,
  endPoint = null,
  incidents = [],
  showIncidents = true,
  highlightCoords = null,
  navigation = null,
  recenterLabel = 'Recenter',
  followingLabel = 'Following',
}) {
  const holder = useRef(null)
  const mapRef = useRef(null)
  const markersRef = useRef([])
  const carMarkerRef = useRef(null)
  const carPosRef = useRef(null)
  const lastPosRef = useRef(null)
  const followRef = useRef(true)
  const [following, setFollowing] = useState(true)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!holder.current || mapRef.current) return undefined

    const map = new MapLibreMap({
      container: holder.current,
      style: STYLE,
      center: center ? [center[1], center[0]] : HYDERABAD,
      zoom,
      pitch: 45,
      attributionControl: { compact: true },
    })
    mapRef.current = map
    if (import.meta.env.DEV) window.__routeMap = map
    map.addControl(new NavigationControl({ visualizePitch: true }), 'top-right')

    map.on('load', () => {
      map.addSource('routes', { type: 'geojson', data: routesToGeoJSON([], null, null) })

      // The wide translucent halo under the chosen route, as Leaflet draws it
      // (weight 15, opacity 0.18).
      map.addLayer({
        id: 'routes-halo',
        type: 'line',
        source: 'routes',
        filter: ['==', ['get', 'selected'], 1],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': ['get', 'color'],
          'line-width': ['interpolate', ['linear'], ['zoom'], 8, 9, 14, 15],
          'line-opacity': 0.18,
        },
      })
      // Alternatives next, so the chosen route draws over them. Dashed and
      // half-opaque, matching the Leaflet dashArray '9 9'.
      map.addLayer({
        id: 'routes-alt',
        type: 'line',
        source: 'routes',
        filter: ['==', ['get', 'selected'], 0],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': ['get', 'color'],
          'line-width': ['interpolate', ['linear'], ['zoom'], 8, 2, 14, 3.5],
          'line-opacity': 0.5,
          'line-dasharray': [3, 3],
        },
      })
      // The chosen route flows. In Leaflet that is .route-flow animating an SVG
      // stroke-dashoffset; MapLibre draws to WebGL where no CSS reaches it, so
      // the dash pattern is stepped in JS below instead.
      map.addLayer({
        id: 'routes-main',
        type: 'line',
        source: 'routes',
        filter: ['==', ['get', 'selected'], 1],
        layout: { 'line-cap': 'butt', 'line-join': 'round' },
        paint: {
          'line-color': ['get', 'color'],
          'line-width': ['interpolate', ['linear'], ['zoom'], 8, 4, 14, 5.5],
          'line-dasharray': FLOW_FRAMES[0],
        },
      })

      map.on('click', 'routes-alt', (e) => {
        const id = e.features?.[0]?.properties?.id
        if (id && onSelectRoute) onSelectRoute(id)
      })
      for (const layer of ['routes-alt', 'routes-main']) {
        map.on('mouseenter', layer, () => { map.getCanvas().style.cursor = 'pointer' })
        map.on('mouseleave', layer, () => { map.getCanvas().style.cursor = '' })
      }

      setReady(true)
    })

    return () => {
      map.remove()
      mapRef.current = null
      setReady(false)
    }
    // Built once; the camera props are the starting view, not a live binding.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Routes in, and the view moved to hold them.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    map.getSource('routes')?.setData(routesToGeoJSON(routes, selectedRouteId, startPoint))
    const box = boundsOf(routes)
    if (box) map.fitBounds(box, { padding: 64, duration: 900, maxZoom: 15 })
  }, [ready, routes, selectedRouteId, startPoint])

  /* --------------------------------------------------------------- car */
  useEffect(() => {
    const map = mapRef.current
    const path = navigation?.path
    if (!map || !ready || !path || path.length < 2) return undefined

    const cum = cumulativeDistances(path)
    const total = cum[cum.length - 1]
    if (!total) return undefined

    // A new leg resumes beside the car rather than snapping to the start —
    // a switched route continues the journey, it does not restart it.
    const startIndex = nearestIndex(path, lastPosRef.current)
    let dist = cum[startIndex] || 0

    const element = carElement()
    const marker = new Marker({ element }).setLngLat([path[0][1], path[0][0]]).addTo(map)
    carMarkerRef.current = marker

    const draw = () => {
      const { pos, nodeFraction, bearing } = placeAlong(path, cum, dist)
      lastPosRef.current = pos
      carPosRef.current = pos
      marker.setLngLat([pos[1], pos[0]])
      if (bearing !== null) {
        const inner = element.querySelector('.nav-car')
        if (inner) inner.style.transform = `rotate(${bearing}deg)`
      }
      return nodeFraction
    }

    draw()
    if (!navigation.running) {
      return () => { marker.remove(); carMarkerRef.current = null }
    }

    let frame = 0
    let last = performance.now()
    let lastReport = 0
    let lastPan = 0
    let done = false

    const step = (now) => {
      // Capped, so a long stall resumes with a short hop rather than a leap.
      const dt = Math.min((now - last) / 1000, 2)
      last = now
      dist = Math.min(dist + (navigation.speedMps || 0) * dt, total)
      const nodeFraction = draw()

      if (now - lastReport > 2000) {
        lastReport = now
        navigation.onProgress?.(nodeFraction, dist / total)
      }
      // Only while following: dragging the map turns following off, and before
      // that the map hauled itself back and could not be read.
      if (now - lastPan > 1500 && followRef.current !== false) {
        lastPan = now
        if (!withinInset(map, lastPosRef.current, 0.15)) {
          map.panTo([lastPosRef.current[1], lastPosRef.current[0]])
        }
      }
      if (dist >= total) {
        done = true
        navigation.onProgress?.(1, 1)
        navigation.onArrive?.()
      }
    }

    const tick = (now) => {
      if (done) return
      step(now)
      if (!done) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)

    // Browsers stop sending frames to a background tab, and the two-tab demo
    // puts the driver's tab there while the admin works. The watchdog keeps
    // the trip moving at the same speed when frames stop arriving.
    const watchdog = setInterval(() => {
      const now = performance.now()
      if (!done && now - last > 300) step(now)
    }, 250)

    return () => {
      cancelAnimationFrame(frame)
      clearInterval(watchdog)
      marker.remove()
      carMarkerRef.current = null
    }
    // Keyed on the leg, not the array: the same path handed down again by a
    // re-render must not restart the car.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, navigation?.legKey, navigation?.running, navigation?.speedMps])

  // The chosen route's dashes travel along it. Only while a route is selected,
  // so nothing ticks on an empty map.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || !selectedRouteId) return undefined
    let i = 0
    const id = setInterval(() => {
      i = (i + 1) % FLOW_FRAMES.length
      if (map.getLayer('routes-main')) {
        map.setPaintProperty('routes-main', 'line-dasharray', FLOW_FRAMES[i])
      }
    }, 90)
    return () => clearInterval(id)
  }, [ready, selectedRouteId])

  // Dragging means "I want to look somewhere else" — stop chasing the car.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return undefined
    const release = () => {
      followRef.current = false
      setFollowing(false)
    }
    map.on('dragstart', release)
    return () => { map.off('dragstart', release) }
  }, [ready])

  // Endpoints, incidents and the predicted-spike pin. Torn down and rebuilt
  // together: there are a handful of them, and diffing by id would be more
  // code than it saves.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return undefined

    const add = (coords, element, lines) => {
      if (!coords || !Number.isFinite(coords[0]) || !Number.isFinite(coords[1])) return
      const marker = new Marker({ element })
        .setLngLat([coords[1], coords[0]])
        .setPopup(new Popup({ offset: 18, closeButton: false }).setDOMContent(popupContent(lines)))
        .addTo(map)
      markersRef.current.push(marker)
    }

    if (startPoint?.coords) {
      add(startPoint.coords, pinElement('A', '#2F6FED'), [
        { text: `Start · ${startPoint.name ?? ''}`.trim() },
      ])
    }
    if (endPoint?.coords) {
      add(endPoint.coords, pinElement('B', '#1F4D3A'), [
        { text: `Destination · ${endPoint.name ?? ''}`.trim() },
      ])
    }
    if (showIncidents) {
      for (const i of incidents || []) {
        add(i.coords, incidentElement(TRAFFIC_COLORS[i.severity] || '#D64545'), [
          { text: i.name, strong: true },
          { text: [i.location, i.reportedAt].filter(Boolean).join(' · ') },
          { text: i.description },
        ])
      }
    }
    if (highlightCoords) {
      add(highlightCoords, incidentElement('#D64545'), [
        { text: 'Predicted congestion spike' },
      ])
    }

    return () => {
      for (const m of markersRef.current) m.remove()
      markersRef.current = []
    }
  }, [ready, startPoint, endPoint, incidents, showIncidents, highlightCoords])

  const recenter = () => {
    followRef.current = true
    setFollowing(true)
    const pos = carPosRef.current
    if (pos && mapRef.current) mapRef.current.panTo([pos[1], pos[0]])
  }

  // The button is a SIBLING of the map container, never a child: MapLibre owns
  // the DOM inside its container and appends its own layers there.
  return (
    <div className="map3d-holder">
      <div className="map3d-canvas" ref={holder} />
      {navigation?.path && (
        <button
          type="button"
          className="map-recenter map3d-recenter"
          data-following={following}
          onClick={recenter}
          title={following ? followingLabel : recenterLabel}
        >
          <Crosshair size={13} />
          {following ? followingLabel : recenterLabel}
        </button>
      )}
    </div>
  )
}
