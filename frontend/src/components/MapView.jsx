import { useEffect, useMemo, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

import {
  HYDERABAD_CENTER,
  TRAFFIC_COLORS,
} from '../data/mockData'

/* ============================================================
   HELPERS
   ============================================================ */

function normalizePoint(point) {
  if (!point) return null

  // [lat, lon]
  if (Array.isArray(point) && point.length >= 2) {
    const a = Number(point[0])
    const b = Number(point[1])

    if (Number.isFinite(a) && Number.isFinite(b)) {
      return [a, b]
    }
  }

  // { coords: [lat, lon] }
  if (
    Array.isArray(point.coords) &&
    point.coords.length >= 2
  ) {
    const a = Number(point.coords[0])
    const b = Number(point.coords[1])

    if (Number.isFinite(a) && Number.isFinite(b)) {
      return [a, b]
    }
  }

  // { lat, lon }
  if (
    point.lat !== undefined &&
    point.lon !== undefined
  ) {
    const lat = Number(point.lat)
    const lon = Number(point.lon)

    if (
      Number.isFinite(lat) &&
      Number.isFinite(lon)
    ) {
      return [lat, lon]
    }
  }

  // { lat, lng }
  if (
    point.lat !== undefined &&
    point.lng !== undefined
  ) {
    const lat = Number(point.lat)
    const lon = Number(point.lng)

    if (
      Number.isFinite(lat) &&
      Number.isFinite(lon)
    ) {
      return [lat, lon]
    }
  }

  return null
}

/* ============================================================
   GET ROUTE PATH
   ============================================================ */

function getRoutePath(route) {
  if (!route) return []

  /*
   * Normal application format:
   * route.path
   */
  if (Array.isArray(route.path)) {
    return route.path
  }

  /*
   * GeoJSON format:
   */
  if (
    route.geometry &&
    Array.isArray(route.geometry.coordinates)
  ) {
    return route.geometry.coordinates.map(
      ([lon, lat]) => [lat, lon]
    )
  }

  /*
   * Alternative names just in case
   */
  if (Array.isArray(route.coordinates)) {
    return route.coordinates
  }

  if (Array.isArray(route.points)) {
    return route.points
  }

  return []
}

/* ============================================================
   ROUTE DIRECTION
   ============================================================ */

function getDirectionalPath(
  route,
  startPoint
) {
  const rawPath =
    getRoutePath(route)

  const path =
    rawPath
      .map(normalizePoint)
      .filter(Boolean)

  if (path.length < 2) {
    return []
  }

  const start =
    normalizePoint(startPoint)

  if (!start) {
    return path
  }

  const first =
    path[0]

  const last =
    path[path.length - 1]

  const distance = (a, b) => {
    const lat =
      a[0] - b[0]

    const lon =
      a[1] - b[1]

    return Math.sqrt(
      lat * lat +
      lon * lon
    )
  }

  /*
   * Make sure route starts at A.
   */
  if (
    distance(last, start) <
    distance(first, start)
  ) {
    return [...path].reverse()
  }

  return path
}

/* ============================================================
   MAPLIBRE COORDINATES
   IMPORTANT:
   Application = [lat, lon]
   MapLibre = [lon, lat]
   ============================================================ */

function toMapLibreCoordinates(
  route,
  startPoint
) {
  const path =
    getDirectionalPath(
      route,
      startPoint
    )

  return path
    .map(([lat, lon]) => [
      Number(lon),
      Number(lat),
    ])
    .filter(
      ([lon, lat]) =>
        Number.isFinite(lon) &&
        Number.isFinite(lat) &&
        Math.abs(lat) <= 90 &&
        Math.abs(lon) <= 180
    )
}

/* ============================================================
   BOUNDS
   ============================================================ */

function getRouteBounds(
  routes,
  startPoint,
  endPoint
) {
  const bounds =
    new maplibregl.LngLatBounds()

  let found = false

  routes.forEach((route) => {
    const coordinates =
      toMapLibreCoordinates(
        route,
        startPoint
      )

    coordinates.forEach(
      ([lon, lat]) => {
        bounds.extend([
          lon,
          lat,
        ])

        found = true
      }
    )
  })

  if (found) {
    return bounds
  }

  const start =
    normalizePoint(startPoint)

  const end =
    normalizePoint(endPoint)

  if (start) {
    bounds.extend([
      start[1],
      start[0],
    ])

    found = true
  }

  if (end) {
    bounds.extend([
      end[1],
      end[0],
    ])

    found = true
  }

  return found
    ? bounds
    : null
}

/* ============================================================
   MARKER
   ============================================================ */

function makeMarker(
  label,
  color
) {
  const el =
    document.createElement('div')

  el.innerHTML = `
    <div
      style="
        width:30px;
        height:30px;
        border-radius:50%;
        display:flex;
        align-items:center;
        justify-content:center;
        background:${color};
        color:#fff;
        font-size:13px;
        font-weight:800;
        border:2px solid #fff;
        box-shadow:0 0 14px ${color};
      "
    >
      ${label}
    </div>
  `

  return el
}

function makeIncidentMarker(
  color
) {
  const el =
    document.createElement('div')

  el.innerHTML = `
    <div
      style="
        width:30px;
        height:30px;
        border-radius:50%;
        display:flex;
        align-items:center;
        justify-content:center;
        background:${color}22;
        border:2px solid ${color};
        color:${color};
        font-size:16px;
        font-weight:900;
        box-shadow:0 0 14px ${color}55;
      "
    >
      !
    </div>
  `

  return el
}

/* ============================================================
   ANIMATED CAR
   ============================================================ */

function AnimatedCar({
  map,
  route,
  startPoint,
}) {
  const frame =
    useRef(null)

  useEffect(() => {
    if (!map) return

    const coordinates =
      toMapLibreCoordinates(
        route,
        startPoint
      )

    if (
      coordinates.length < 2
    ) {
      return
    }

    const el =
      document.createElement('div')

    el.innerHTML = `
      <div
        style="
          width:28px;
          height:28px;
          display:flex;
          align-items:center;
          justify-content:center;
          filter:drop-shadow(0 0 7px #ff6b35);
        "
      >
        🚗
      </div>
    `

    const marker =
      new maplibregl.Marker({
        element: el,
        anchor: 'center',
      })
        .setLngLat(
          coordinates[0]
        )
        .addTo(map)

    let index = 0
    let progress = 0

    const animate = () => {
      if (
        index >=
        coordinates.length - 1
      ) {
        index = 0
        progress = 0
      }

      const a =
        coordinates[index]

      const b =
        coordinates[index + 1]

      if (!a || !b) {
        return
      }

      const lon =
        a[0] +
        (b[0] - a[0]) *
          progress

      const lat =
        a[1] +
        (b[1] - a[1]) *
          progress

      marker.setLngLat([
        lon,
        lat,
      ])

      progress += 0.004

      if (progress >= 1) {
        progress = 0
        index += 1
      }

      frame.current =
        requestAnimationFrame(
          animate
        )
    }

    animate()

    return () => {
      if (frame.current) {
        cancelAnimationFrame(
          frame.current
        )
      }

      marker.remove()
    }
  }, [
    map,
    route,
    startPoint,
  ])

  return null
}

/* ============================================================
   MAIN MAP
   ============================================================ */

export default function MapView({
  routes = [],
  selectedRouteId = null,

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

  routeTransition = false,
}) {
  const mapContainerRef =
    useRef(null)

  const mapRef =
    useRef(null)

  const [mapReady, setMapReady] =
    useState(false)

  const [globeMode, setGlobeMode] =
    useState(true)

  const routeIdsRef =
    useRef([])

  const markerRefs =
    useRef([])

  /* ==========================================================
     INITIALIZE MAP
     ========================================================== */

  useEffect(() => {
    if (
      mapRef.current ||
      !mapContainerRef.current
    ) {
      return
    }

    const map =
      new maplibregl.Map({
        container:
          mapContainerRef.current,

        style: {
          version: 8,

          sources: {
            osm: {
              type: 'raster',

              tiles: [
                'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
              ],

              tileSize: 256,

              attribution:
                '© OpenStreetMap contributors',
            },
          },

          layers: [
            {
              id: 'osm',
              type: 'raster',
              source: 'osm',
            },
          ],
        },

        center: [
          Number(
            center?.[1] ??
              78.4867
          ),

          Number(
            center?.[0] ??
              17.3850
          ),
        ],

        zoom: 1.2,

        pitch: 0,

        bearing: 0,
      })

    mapRef.current =
      map

    map.addControl(
      new maplibregl.NavigationControl(),
      'top-right'
    )

    map.on('load', () => {
      /*
       * REAL GLOBE
       */
      map.setProjection({
        type: 'globe',
      })

      setMapReady(true)
    })

    map.on(
      'dragstart',
      () => {
        setGlobeMode(false)
      }
    )

    return () => {
      map.remove()
      mapRef.current =
        null
    }
  }, [])

  /* ==========================================================
     GLOBE ROTATION
     ========================================================== */

  useEffect(() => {
    const map =
      mapRef.current

    if (
      !map ||
      !mapReady
    ) {
      return
    }

    let animationFrame

    const rotate = () => {
      if (
        globeMode &&
        !routeTransition &&
        routes.length === 0
      ) {
        map.setBearing(
          map.getBearing() + 0.012
        )
      }

      animationFrame =
        requestAnimationFrame(
          rotate
        )
    }

    animationFrame =
      requestAnimationFrame(
        rotate
      )

    return () => {
      cancelAnimationFrame(
        animationFrame
      )
    }
  }, [
    mapReady,
    globeMode,
    routeTransition,
    routes.length,
  ])

  /* ==========================================================
     GLOBE -> LOCATION
     ========================================================== */

  useEffect(() => {
    const map =
      mapRef.current

    if (
      !map ||
      !mapReady ||
      !routeTransition
    ) {
      return
    }

    const bounds =
      getRouteBounds(
        routes,
        startPoint,
        endPoint
      )

    if (!bounds) {
      return
    }

    setGlobeMode(false)

    map.stop()

    map.setProjection({
      type: 'globe',
    })

    const centerPoint =
      bounds.getCenter()

    /*
     * Globe zoom toward city.
     */
    map.easeTo({
      center: [
        centerPoint.lng,
        centerPoint.lat,
      ],

      zoom: 3.2,

      duration: 1500,

      essential: true,
    })

    const timer =
      setTimeout(() => {
        if (!mapRef.current) {
          return
        }

        map.setProjection({
          type: 'mercator',
        })

        const latestBounds =
          getRouteBounds(
            routes,
            startPoint,
            endPoint
          )

        if (!latestBounds) {
          return
        }

        map.fitBounds(
          latestBounds,
          {
            padding: 80,

            duration: 1600,

            maxZoom: 14,

            essential: true,
          }
        )
      }, 1500)

    return () =>
      clearTimeout(timer)
  }, [
    mapReady,
    routeTransition,
    routes,
    startPoint,
    endPoint,
  ])

  /* ==========================================================
     FINAL ROUTE FIT
     ========================================================== */

  useEffect(() => {
    const map =
      mapRef.current

    if (
      !map ||
      !mapReady ||
      routeTransition ||
      routes.length === 0
    ) {
      return
    }

    const bounds =
      getRouteBounds(
        routes,
        startPoint,
        endPoint
      )

    if (!bounds) {
      return
    }

    setGlobeMode(false)

    map.stop()

    map.setProjection({
      type: 'mercator',
    })

    map.fitBounds(
      bounds,
      {
        padding: 70,

        duration: 1000,

        maxZoom: 14,

        essential: true,
      }
    )
  }, [
    mapReady,
    routes,
    startPoint,
    endPoint,
    routeTransition,
  ])

  /* ==========================================================
     DRAW ROUTES
     ========================================================== */

  useEffect(() => {
    const map =
      mapRef.current

    if (
      !map ||
      !mapReady
    ) {
      return
    }

    /*
     * REMOVE OLD ROUTES
     */

    routeIdsRef.current.forEach(
      (item) => {
        if (
          map.getLayer(
            item.glow
          )
        ) {
          map.removeLayer(
            item.glow
          )
        }

        if (
          map.getLayer(
            item.line
          )
        ) {
          map.removeLayer(
            item.line
          )
        }

        if (
          map.getSource(
            item.source
          )
        ) {
          map.removeSource(
            item.source
          )
        }
      }
    )

    routeIdsRef.current =
      []

    /*
     * WAIT UNTIL ROUTES ARE REVEALED
     */

    if (
      routeTransition ||
      !routes.length
    ) {
      return
    }

    /*
     * DRAW EVERY ROUTE
     */

    routes.forEach(
      (route, index) => {
        const coordinates =
          toMapLibreCoordinates(
            route,
            startPoint
          )

        console.log(
          `Q-Route ${index + 1}:`,
          route
        )

        console.log(
          `Q-Route ${index + 1} coordinates:`,
          coordinates
        )

        /*
         * THIS SHOULD NEVER HAPPEN
         * IF THE BACKEND ROUTE IS VALID.
         */
        if (
          coordinates.length < 2
        ) {
          console.error(
            'Q-Route: route has no valid coordinates',
            route
          )

          return
        }

        const routeKey =
          route.id ??
          index

        const sourceId =
          `qroute-source-${routeKey}`

        const glowId =
          `qroute-glow-${routeKey}`

        const lineId =
          `qroute-line-${routeKey}`

        const color =
          route.color ||
          [
            '#ff6b35',
            '#2f6fed',
            '#d946ef',
          ][
            index % 3
          ]

        const selected =
          route.id ===
          selectedRouteId

        /*
         * SOURCE
         */

        map.addSource(
          sourceId,
          {
            type: 'geojson',

            data: {
              type: 'Feature',

              properties: {
                id:
                  route.id ??
                  index,
              },

              geometry: {
                type: 'LineString',

                coordinates,
              },
            },
          }
        )

        /*
         * GLOW
         */

        map.addLayer({
          id: glowId,

          type: 'line',

          source: sourceId,

          layout: {
            'line-cap':
              'round',

            'line-join':
              'round',
          },

          paint: {
            'line-color':
              color,

            'line-width':
              selected
                ? 13
                : 8,

            'line-opacity':
              selected
                ? 0.22
                : 0.08,

            'line-blur':
              selected
                ? 1.2
                : 0.5,
          },
        })

        /*
         * ACTUAL ROUTE
         *
         * SOLID LINE
         */

        map.addLayer({
          id: lineId,

          type: 'line',

          source: sourceId,

          layout: {
            'line-cap':
              'round',

            'line-join':
              'round',
          },

          paint: {
            'line-color':
              color,

            'line-width':
              selected
                ? 6
                : 4,

            'line-opacity':
              selected
                ? 1
                : 0.9,
          },
        })

        /*
         * CLICK
         */

        map.on(
          'click',
          lineId,
          () => {
            onSelectRoute?.(
              route.id
            )
          }
        )

        /*
         * CURSOR
         */

        map.on(
          'mouseenter',
          lineId,
          () => {
            map.getCanvas().style.cursor =
              'pointer'
          }
        )

        map.on(
          'mouseleave',
          lineId,
          () => {
            map.getCanvas().style.cursor =
              ''
          }
        )

        routeIdsRef.current.push({
          source: sourceId,
          glow: glowId,
          line: lineId,
        })
      }
    )

    /*
     * FORCE SELECTED ROUTE TO TOP
     */

    const selectedIndex =
      routes.findIndex(
        (route) =>
          route.id ===
          selectedRouteId
      )

    if (
      selectedIndex !== -1
    ) {
      const selectedRoute =
        routes[selectedIndex]

      const key =
        selectedRoute.id ??
        selectedIndex

      const glowId =
        `qroute-glow-${key}`

      const lineId =
        `qroute-line-${key}`

      if (
        map.getLayer(glowId)
      ) {
        map.moveLayer(
          glowId
        )
      }

      if (
        map.getLayer(lineId)
      ) {
        map.moveLayer(
          lineId
        )
      }
    }

    return () => {
      routeIdsRef.current.forEach(
        (item) => {
          if (
            map.getLayer(
              item.glow
            )
          ) {
            map.removeLayer(
              item.glow
            )
          }

          if (
            map.getLayer(
              item.line
            )
          ) {
            map.removeLayer(
              item.line
            )
          }

          if (
            map.getSource(
              item.source
            )
          ) {
            map.removeSource(
              item.source
            )
          }
        }
      )

      routeIdsRef.current =
        []
    }
  }, [
    mapReady,
    routes,
    selectedRouteId,
    startPoint,
    routeTransition,
    onSelectRoute,
  ])

  /* ==========================================================
     MARKERS
     ========================================================== */

  useEffect(() => {
    const map =
      mapRef.current

    if (
      !map ||
      !mapReady
    ) {
      return
    }

    /*
     * Remove old markers.
     */

    markerRefs.current.forEach(
      (marker) =>
        marker.remove()
    )

    markerRefs.current =
      []

    /* --------------------------------------------------------
       START
       -------------------------------------------------------- */

    const start =
      normalizePoint(
        startPoint
      )

    if (start) {
      const marker =
        new maplibregl.Marker({
          element:
            makeMarker(
              'A',
              '#2F6FED'
            ),
        })
          .setLngLat([
            start[1],
            start[0],
          ])
          .addTo(map)

      markerRefs.current.push(
        marker
      )

      if (startPoint?.name) {
        marker.setPopup(
          new maplibregl.Popup({
            offset: 18,
          }).setHTML(
            `<strong>Start</strong><br>${startPoint.name}`
          )
        )
      }
    }

    /* --------------------------------------------------------
       END
       -------------------------------------------------------- */

    const end =
      normalizePoint(
        endPoint
      )

    if (end) {
      const marker =
        new maplibregl.Marker({
          element:
            makeMarker(
              'B',
              '#1F4D3A'
            ),
        })
          .setLngLat([
            end[1],
            end[0],
          ])
          .addTo(map)

      markerRefs.current.push(
        marker
      )

      if (endPoint?.name) {
        marker.setPopup(
          new maplibregl.Popup({
            offset: 18,
          }).setHTML(
            `<strong>Destination</strong><br>${endPoint.name}`
          )
        )
      }
    }

    /* --------------------------------------------------------
       INCIDENTS
       -------------------------------------------------------- */

    if (
      showIncidents &&
      Array.isArray(incidents)
    ) {
      incidents.forEach(
        (incident) => {
          const point =
            normalizePoint(
              incident
            )

          if (!point) {
            return
          }

          const color =
            TRAFFIC_COLORS[
              incident.severity
            ] ||
            '#facc15'

          const marker =
            new maplibregl.Marker({
              element:
                makeIncidentMarker(
                  color
                ),
            })
              .setLngLat([
                point[1],
                point[0],
              ])
              .addTo(map)

          markerRefs.current.push(
            marker
          )

          marker.setPopup(
            new maplibregl.Popup({
              offset: 18,
            }).setHTML(`
              <strong>
                ${
                  incident.name ||
                  'Traffic incident'
                }
              </strong>
              <br>
              ${
                incident.location ||
                ''
              }
              <br>
              ${
                incident.description ||
                ''
              }
            `)
          )
        }
      )
    }

    /* --------------------------------------------------------
       PREDICTIVE ALERT
       -------------------------------------------------------- */

    const alert =
      normalizePoint(
        highlightCoords
      )

    if (alert) {
      const marker =
        new maplibregl.Marker({
          element:
            makeIncidentMarker(
              '#D64545'
            ),
        })
          .setLngLat([
            alert[1],
            alert[0],
          ])
          .addTo(map)

      markerRefs.current.push(
        marker
      )

      marker.setPopup(
        new maplibregl.Popup({
          offset: 18,
        }).setHTML(
          '<strong>Predicted congestion spike</strong>'
        )
      )
    }

    return () => {
      markerRefs.current.forEach(
        (marker) =>
          marker.remove()
      )

      markerRefs.current =
        []
    }
  }, [
    mapReady,
    startPoint,
    endPoint,
    incidents,
    showIncidents,
    highlightCoords,
  ])

  /* ==========================================================
     SELECTED ROUTE
     ========================================================== */

  const selectedRoute =
    routes.find(
      (route) =>
        route.id ===
        selectedRouteId
    ) || null

  /* ==========================================================
     RENDER
     ========================================================== */

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      <div
        ref={mapContainerRef}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
        }}
      />

      {/* GLOBAL VIEW */}

      {!routes.length &&
        !routeTransition && (
          <div
            style={{
              position: 'absolute',
              top: 14,
              left: 14,
              zIndex: 20,
              padding:
                '7px 12px',
              borderRadius: 8,
              background:
                'rgba(8,12,20,.82)',
              color: '#fff',
              fontSize: 11,
              fontWeight: 700,
              pointerEvents:
                'none',
            }}
          >
            Global view
          </div>
        )}

      {/* OPTIMIZING */}

      {routeTransition && (
        <div
          style={{
            position: 'absolute',
            top: 14,
            left: 14,
            zIndex: 20,
            padding:
              '7px 12px',
            borderRadius: 8,
            background:
              'rgba(8,12,20,.85)',
            color: '#fff',
            fontSize: 11,
            fontWeight: 700,
            pointerEvents:
              'none',
          }}
        >
          Calculating optimal routes...
        </div>
      )}

      {/* SELECTED ROUTE */}

      {selectedRoute &&
        !routeTransition && (
          <div
            style={{
              position: 'absolute',
              left: 14,
              bottom: 14,
              zIndex: 20,
              padding:
                '9px 12px',
              borderRadius: 9,
              background:
                'rgba(8,12,20,.85)',
              color: '#fff',
              fontSize: 11,
              pointerEvents:
                'none',
            }}
          >
            <strong>
              {selectedRoute.label ||
                'Selected route'}
            </strong>

            <br />

            <span
              style={{
                opacity: 0.75,
              }}
            >
              {selectedRoute.distanceKm ??
                '--'}{' '}
              km ·{' '}
              {selectedRoute.etaMin ??
                '--'}{' '}
              min
            </span>
          </div>
        )}

      {/* ANIMATED CAR */}

      {showTraffic &&
        selectedRoute &&
        !routeTransition && (
          <AnimatedCar
            map={mapRef.current}
            route={selectedRoute}
            startPoint={startPoint}
          />
        )}
    </div>
  )
}