import { useEffect, useRef, useState } from 'react'
// MapLibre 6 has no default export; the pieces are named.
import { Map as MapLibreMap, NavigationControl } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

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
}) {
  const holder = useRef(null)
  const mapRef = useRef(null)
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

  return <div ref={holder} className="map3d-canvas" />
}
