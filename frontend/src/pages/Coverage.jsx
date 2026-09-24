import { useEffect, useMemo, useRef, useState } from 'react'
// MapLibre 6 has no default export; the pieces are named.
import { Map as MapLibreMap, NavigationControl } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { Globe2, Layers, Loader2, MapPin, RotateCw } from 'lucide-react'
import { getGraphs } from '../services/api'
import { useApp } from '../store/AppContext'

/**
 * The networks this system can route on, on a globe.
 *
 * Every footprint drawn here is a graph that was actually built: the
 * rectangle is the bounding box the builder used, and the figures beside it
 * are read from the stats file written at build time — nodes, edges and road
 * length, not estimates made for the picture. A network that has not been
 * built is listed and greyed, never drawn as if it existed.
 *
 * WHY A SECOND MAP ENGINE
 * -----------------------
 * Leaflet draws flat raster tiles and cannot show a globe. MapLibre can, and
 * the tiles come from CARTO's keyless basemap, so nothing here needs an
 * account or an API key. The routing map is untouched — this view exists to
 * answer "what does this cover?", and the dashboard answers "how do I get
 * there?".
 */

// Keyless, attribution carried by the style itself.
const STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
const SPIN_DEGREES_PER_SECOND = 4

const BRAND = '#FF6B35'
const QUIET = '#5A6B7A'

function centreOf(bbox) {
  const [w, s, e, n] = bbox
  return [(w + e) / 2, (s + n) / 2]
}

function footprint(bbox) {
  const [w, s, e, n] = bbox
  return [[[w, s], [e, s], [e, n], [w, n], [w, s]]]
}

const number = (n) => (n == null ? '—' : n.toLocaleString())

export default function Coverage() {
  const { t } = useApp()
  const holder = useRef(null)
  const mapRef = useRef(null)
  const spinRef = useRef(true)
  const [networks, setNetworks] = useState(null)
  const [failed, setFailed] = useState(null)
  const [selected, setSelected] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false
    getGraphs()
      .then((d) => {
        if (cancelled) return
        const rows = Object.entries(d.graphs || {})
          .map(([id, g]) => ({ id, ...g }))
          .sort((a, b) => (b.stats?.nodes || 0) - (a.stats?.nodes || 0))
        setNetworks(rows)
      })
      .catch((err) => !cancelled && setFailed(err.message || 'Could not read the networks.'))
    return () => { cancelled = true }
  }, [])

  const built = useMemo(
    () => (networks || []).filter((n) => n.available && Array.isArray(n.bbox)),
    [networks],
  )

  /* ------------------------------------------------------------- the globe */
  useEffect(() => {
    if (!holder.current || mapRef.current) return undefined

    const map = new MapLibreMap({
      container: holder.current,
      style: STYLE,
      center: [78.47, 17.38],          // Hyderabad, where the work is
      zoom: 1.6,
      attributionControl: { compact: true },
    })
    mapRef.current = map
    // A handle while developing, so the map's own state can be inspected
    // from the console. Never present in a production build.
    if (import.meta.env.DEV) window.__coverageMap = map
    map.addControl(new NavigationControl({ visualizePitch: true }), 'top-right')

    map.on('load', () => {
      // A globe rather than a flat sheet. Guarded: a future version that
      // renames this should leave a working flat map, not a blank page.
      try { map.setProjection({ type: 'globe' }) } catch { /* flat is fine */ }
      map.setPaintProperty('background', 'background-color', '#05070d')
      setReady(true)
    })

    // Turning slowly until someone takes hold of it.
    let frame
    let last = performance.now()
    const spin = (now) => {
      const dt = (now - last) / 1000
      last = now
      if (spinRef.current && !map.isMoving()) {
        map.setCenter([map.getCenter().lng - SPIN_DEGREES_PER_SECOND * dt, map.getCenter().lat])
      }
      frame = requestAnimationFrame(spin)
    }
    frame = requestAnimationFrame(spin)
    const stop = () => { spinRef.current = false }
    map.on('mousedown', stop)
    map.on('touchstart', stop)
    map.on('wheel', stop)

    return () => {
      cancelAnimationFrame(frame)
      map.remove()
      mapRef.current = null
    }
  }, [])

  /* ------------------------------------------- the footprints that exist */
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || !built.length) return

    const data = {
      type: 'FeatureCollection',
      features: built.map((n) => ({
        type: 'Feature',
        id: n.id,
        properties: { id: n.id, label: n.label, nodes: n.stats?.nodes || 0 },
        geometry: { type: 'Polygon', coordinates: footprint(n.bbox) },
      })),
    }
    const points = {
      type: 'FeatureCollection',
      features: built.map((n) => ({
        type: 'Feature',
        properties: { id: n.id, label: n.label },
        geometry: { type: 'Point', coordinates: centreOf(n.bbox) },
      })),
    }

    if (map.getSource('coverage')) {
      map.getSource('coverage').setData(data)
      map.getSource('coverage-points').setData(points)
      return
    }

    map.addSource('coverage', { type: 'geojson', data })
    map.addSource('coverage-points', { type: 'geojson', data: points })

    map.addLayer({
      id: 'coverage-fill',
      type: 'fill',
      source: 'coverage',
      paint: { 'fill-color': BRAND, 'fill-opacity': 0.18 },
    })
    map.addLayer({
      id: 'coverage-edge',
      type: 'line',
      source: 'coverage',
      paint: { 'line-color': BRAND, 'line-width': 1.4, 'line-opacity': 0.9 },
    })
    map.addLayer({
      id: 'coverage-dot',
      type: 'circle',
      source: 'coverage-points',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 1, 4, 6, 9],
        'circle-color': BRAND,
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 1.2,
        'circle-opacity': 0.95,
      },
    })
    map.addLayer({
      id: 'coverage-name',
      type: 'symbol',
      source: 'coverage-points',
      layout: {
        'text-field': ['get', 'label'],
        'text-size': 11,
        'text-offset': [0, 1.2],
        'text-anchor': 'top',
      },
      paint: { 'text-color': '#E8EEF5', 'text-halo-color': '#05070d', 'text-halo-width': 1.4 },
    })

    const pick = (e) => {
      const id = e.features?.[0]?.properties?.id
      if (id) flyTo(id)
    }
    map.on('click', 'coverage-dot', pick)
    map.on('click', 'coverage-fill', pick)
    for (const layer of ['coverage-dot', 'coverage-fill']) {
      map.on('mouseenter', layer, () => { map.getCanvas().style.cursor = 'pointer' })
      map.on('mouseleave', layer, () => { map.getCanvas().style.cursor = '' })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, built])

  const flyTo = (id) => {
    const network = built.find((n) => n.id === id)
    const map = mapRef.current
    if (!network || !map) return
    spinRef.current = false
    setSelected(id)
    const [w, s, e, n] = network.bbox
    map.fitBounds([[w, s], [e, n]], { padding: 80, duration: 2600, pitch: 45 })
  }

  const backToGlobe = () => {
    const map = mapRef.current
    if (!map) return
    setSelected(null)
    map.flyTo({ center: [78.47, 17.38], zoom: 1.6, pitch: 0, duration: 2200 })
    spinRef.current = true
  }

  return (
    <>
      <div className="row-between page-head">
        <div>
          <h1>{t('coverage.title')}</h1>
          <p>{t('coverage.subtitle')}</p>
        </div>
        <button className="btn btn-sm" type="button" onClick={backToGlobe}>
          <RotateCw size={13} /> {t('coverage.backToGlobe')}
        </button>
      </div>

      <div className="coverage-grid">
        <div className="coverage-globe">
          <div ref={holder} className="coverage-canvas" />
          {!ready && (
            <div className="coverage-loading">
              <Loader2 size={16} className="spin" /> {t('coverage.loading')}
            </div>
          )}
        </div>

        <div className="coverage-list">
          {failed && <div className="card" role="alert"><p className="settings-hint">{failed}</p></div>}
          {!networks && !failed && <div className="card"><p className="settings-hint">{t('coverage.loading')}</p></div>}

          {(networks || []).map((n) => {
            const s = n.stats || {}
            const on = selected === n.id
            return (
              <button
                key={n.id}
                type="button"
                className={`card coverage-item${on ? ' is-selected' : ''}`}
                onClick={() => n.available && flyTo(n.id)}
                disabled={!n.available}
              >
                <div className="coverage-item-head">
                  <span className="coverage-item-name">
                    {n.loaded ? <Layers size={13} /> : <MapPin size={13} />} {n.label}
                  </span>
                  {n.available
                    ? <span className={`badge ${n.loaded ? 'badge-green' : 'badge-grey'}`}>
                        {n.loaded ? t('coverage.inMemory') : t('coverage.built')}
                      </span>
                    : <span className="badge badge-grey">{t('coverage.notBuilt')}</span>}
                </div>
                <p className="coverage-scope">{n.scope}</p>
                {n.available && (
                  <dl className="coverage-figures">
                    <div><dt>{t('coverage.nodes')}</dt><dd className="mono">{number(s.nodes)}</dd></div>
                    <div><dt>{t('coverage.edges')}</dt><dd className="mono">{number(s.edges)}</dd></div>
                    <div>
                      <dt>{t('coverage.roadLength')}</dt>
                      <dd className="mono">
                        {s.roadKm ? `${Math.round(s.roadKm).toLocaleString()} km` : '—'}
                        {s.roadKmBasis === 'directed' && (
                          <em title={t('coverage.directedHint')}> ({t('coverage.directed')})</em>
                        )}
                      </dd>
                    </div>
                  </dl>
                )}
              </button>
            )
          })}

          <p className="coverage-note">{t('coverage.note')}</p>
        </div>
      </div>
    </>
  )
}
