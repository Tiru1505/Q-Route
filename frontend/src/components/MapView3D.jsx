import { useEffect, useRef, useState } from 'react'
// MapLibre 6 has no default export; the pieces are named.
import { Map as MapLibreMap, Marker, NavigationControl, Popup } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { TRAFFIC_COLORS } from '../data/mockData'

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
 * The basemap, the routes, fitting the view to them, and picking one. Markers,
 * incidents, the car and the traffic segments are still MapView's alone —
 * passing them here does nothing yet rather than half-drawing them.
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

function routesToGeoJSON(routes, selectedId) {
  return {
    type: 'FeatureCollection',
    features: (routes || [])
      .filter((r) => r.path?.length)
      .map((r) => ({
        type: 'Feature',
        id: r.id,
        properties: { id: r.id, selected: r.id === selectedId ? 1 : 0 },
        geometry: { type: 'LineString', coordinates: toLngLat(r.path) },
      })),
  }
}

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
}) {
  const holder = useRef(null)
  const mapRef = useRef(null)
  const markersRef = useRef([])
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
      map.addSource('routes', { type: 'geojson', data: routesToGeoJSON([], null) })

      // Alternatives first, so the chosen route draws over them.
      map.addLayer({
        id: 'routes-alt',
        type: 'line',
        source: 'routes',
        filter: ['==', ['get', 'selected'], 0],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': cssVar('--text-faint', '#9F9189'),
          'line-width': ['interpolate', ['linear'], ['zoom'], 8, 2, 14, 4],
          'line-opacity': 0.55,
        },
      })
      map.addLayer({
        id: 'routes-main',
        type: 'line',
        source: 'routes',
        filter: ['==', ['get', 'selected'], 1],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': cssVar('--brand', '#FF6B35'),
          'line-width': ['interpolate', ['linear'], ['zoom'], 8, 4, 14, 7],
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
    map.getSource('routes')?.setData(routesToGeoJSON(routes, selectedRouteId))
    const box = boundsOf(routes)
    if (box) map.fitBounds(box, { padding: 64, duration: 900, maxZoom: 15 })
  }, [ready, routes, selectedRouteId])

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

  return <div ref={holder} className="map3d-canvas" />
}
