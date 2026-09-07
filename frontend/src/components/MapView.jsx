import { useEffect, useMemo, useState } from 'react'
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

    map.flyToBounds(
      L.latLngBounds(pts).pad(0.18),
      {
        duration: 0.85,
      }
    )
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

      <InvalidateOnMount />

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

      {showTraffic &&
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