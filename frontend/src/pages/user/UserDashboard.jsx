import { useCallback, useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import {
  ArrowRight, CheckCircle2, Clock, Flag, Gauge, Loader2, MapPin, Navigation2,
  Pause, Play, Route as RouteIcon, Square, TrendingDown, TrendingUp, TriangleAlert,
} from 'lucide-react'
import MapView from '../../components/MapView'
import RouteSelector from '../../components/RouteSelector'
import AlternativeRoutes from '../../components/AlternativeRoutes'
import ReroutingPanel from '../../components/ReroutingPanel'
import TrafficLegend from '../../components/TrafficLegend'
import { useApp } from '../../store/AppContext'
import * as api from '../../services/api'
import { TRAFFIC_COLORS, TRAFFIC_LABELS } from '../../data/mockData'

/**
 * The driver's dashboard: plan, drive, and be told when to change road.
 *
 *   plan      where from, where to, vehicle, preference -> the best route
 *             (QPSO runs on the server as always; the user sees its result)
 *   drive     "Start navigation": the route becomes the trip the server
 *             monitors, and a car drives it on the map
 *   decide    when the agent finds a better road, the car waits and the
 *             comparison appears — Switch Route or Keep Current Route
 *   arrive    the trip is saved to History
 *
 * The drive is SIMULATED and sped up — the whole trip takes a couple of
 * minutes — and the page says so. The traffic it is judged against, the
 * forecast and the reroute decision are the real system's.
 */

const DEMO_TRIP_SECONDS = 150
const OUTLOOK_EVERY_MS = 20_000

const levelOf = (c) => (c == null ? null : c < 0.3 ? 'low' : c < 0.5 ? 'moderate' : c < 0.7 ? 'heavy' : 'severe')
const pct = (c) => (c == null ? '—' : `${Math.round(c * 100)}%`)

function minutes(m) {
  if (m == null || Number.isNaN(m)) return '—'
  const total = Math.round(m)
  if (total < 60) return `${total} min`
  return `${Math.floor(total / 60)} h ${String(total % 60).padStart(2, '0')} min`
}

function Stat({ icon: Icon, label, value, hint, tone }) {
  return (
    <div className="trip-stat" data-tone={tone || undefined}>
      <span className="trip-stat-label"><Icon size={11} /> {label}</span>
      <b className="mono">{value}</b>
      {hint && <small>{hint}</small>}
    </div>
  )
}

function TrafficValue({ congestion }) {
  const level = levelOf(congestion)
  if (!level) return <>—</>
  return (
    <span className="trip-traffic">
      <span className="dot" style={{ background: TRAFFIC_COLORS[level] }} />
      {TRAFFIC_LABELS[level]} · {pct(congestion)}
    </span>
  )
}

export default function UserDashboard() {
  const {
    start, end, routes, selectedRoute, selectedRouteId, setSelectedRouteId,
    optimize, optimizing, error, segments, incidents, settings, setAlgorithm,
    latestAlert, switchRoute, keepRoute, rerouting, rerouteResult,
    trip, navRoute, navState, navReading, tripError,
    startNavigation, reportNavProgress, arrive, endTrip,
    pauseNavigation, resumeNavigation, clearTrip,
  } = useApp()

  const [legFraction, setLegFraction] = useState(0)
  const [outlook, setOutlook] = useState(null)

  // Users do not choose the algorithm: every route is QPSO's.
  useEffect(() => { setAlgorithm('qpso') }, [setAlgorithm])

  const navigating = navState === 'driving' || navState === 'paused'
  const tripActive = trip?.status === 'active'

  // An alert that arrived during this trip and has not been answered. While
  // it stands, the car holds position — the decision is the driver's.
  const pendingAlert = useMemo(() => {
    if (!latestAlert || latestAlert.resolved || !tripActive || !navigating) return null
    return latestAlert.actionable ? latestAlert : null
  }, [latestAlert, tripActive, navigating])

  const startPoint = useMemo(
    () => (start ? { ...start, coords: start.coords || [start.lat, start.lon] } : null), [start])
  const endPoint = useMemo(
    () => (end ? { ...end, coords: end.coords || [end.lat, end.lon] } : null), [end])

  // The road ahead, re-read while driving: congestion now against the
  // forecaster's prediction. Asked in preview, so it never spends an alert.
  useEffect(() => {
    if (!tripActive || !navigating) return undefined
    let cancelled = false
    const read = () => api.getTripOutlook(trip.id)
      .then((o) => { if (!cancelled) setOutlook(o) })
      .catch(() => { /* a busy engine answers next time */ })
    read()
    const id = setInterval(read, OUTLOOK_EVERY_MS)
    return () => { cancelled = true; clearInterval(id) }
  }, [tripActive, navigating, trip?.id, navRoute?.id])

  useEffect(() => { if (!trip) { setOutlook(null); setLegFraction(0) } }, [trip])

  const onProgress = useCallback((nodeFraction, distanceFraction) => {
    setLegFraction(distanceFraction)
    reportNavProgress(nodeFraction)
  }, [reportNavProgress])

  // Planned distance over the demo duration; kept for the whole trip, so a
  // switched route is driven at the same pace.
  const speedMps = useMemo(
    () => Math.max(((trip?.distanceKm || 10) * 1000) / DEMO_TRIP_SECONDS, 20),
    [trip?.distanceKm],
  )
  const speedup = trip?.plannedEtaMin ? Math.round((trip.plannedEtaMin * 60) / DEMO_TRIP_SECONDS) : null

  const navigation = navRoute && (navigating || navState === 'arrived') ? {
    path: navRoute.path,
    legKey: navRoute.id,
    running: navState === 'driving' && !pendingAlert && !rerouting,
    speedMps,
    onProgress,
    onArrive: arrive,
  } : null

  const mapRoutes = navRoute ? [navRoute] : routes
  const mapSelected = navRoute ? navRoute.id : selectedRouteId
  const current = navRoute || selectedRoute
  const remainingEta = navReading?.remainingEtaMin
    ?? (current ? current.etaMin * (1 - legFraction) : null)

  const trafficNow = navigating && outlook?.observedCongestion != null
    ? outlook.observedCongestion : current?.congestion
  const predicted = navigating ? outlook?.predictedCongestion : null

  return (
    <div className="dash-grid user-dash">
      {/* ------------------------------------------------------------ plan */}
      <div className="dash-col">
        <RouteSelector
          variant="user"
          onOptimize={() => { clearTrip(); optimize() }}
          busy={optimizing}
          locked={navigating}
        />
        {!navigating && routes.length > 1 && (
          <AlternativeRoutes routes={routes} selectedId={selectedRouteId} onSelect={setSelectedRouteId} />
        )}
      </div>

      {/* ------------------------------------------------------------- map */}
      <div className="dash-col">
        <div className="map-shell">
          <MapView
            routes={mapRoutes}
            selectedRouteId={mapSelected}
            onSelectRoute={navRoute ? undefined : setSelectedRouteId}
            segments={segments}
            incidents={incidents}
            startPoint={startPoint}
            endPoint={endPoint}
            mapStyle={settings.mapStyle}
            navigation={navigation}
            decorativeCars={false}
          />
          <div className="map-overlay map-legend"><TrafficLegend /></div>

          <div className="map-overlay map-topright">
            {optimizing && (
              <div className="legend-card user-finding">
                <Loader2 size={13} className="spin" /> Finding the best route…
              </div>
            )}
            {!optimizing && !routes.length && (
              <div className="legend-card" style={{ maxWidth: 220 }}>
                <div className="legend-title">Where to?</div>
                <p style={{ fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.5 }}>
                  Choose a start and a destination, then find the best route.
                </p>
              </div>
            )}
            {navigating && (
              <div className="legend-card nav-hud" aria-live="polite">
                <div className="legend-title">
                  {pendingAlert ? 'Waiting for your decision' : navState === 'paused' ? 'Paused' : 'Navigating'}
                </div>
                <div className="nav-hud-row">
                  <Clock size={11} /> {minutes(remainingEta)} left
                </div>
                <div className="nav-progress"><span style={{ width: `${Math.round(legFraction * 100)}%` }} /></div>
                <small>Simulated drive{speedup ? ` · ${speedup}× speed` : ''}</small>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------- the trip */}
      <div className="dash-col dash-col-right">
        {(error || tripError) && (
          <div className="card" style={{ borderColor: 'rgba(239,68,68,.3)' }} role="alert">
            <div style={{ display: 'flex', gap: 9, alignItems: 'flex-start' }}>
              <TriangleAlert size={15} style={{ color: 'var(--severe)', flexShrink: 0, marginTop: 2 }} />
              <p style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>{tripError || error}</p>
            </div>
          </div>
        )}

        <AnimatePresence>
          {pendingAlert && (
            <motion.div
              key={pendingAlert.id}
              className="card recommend-card"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              role="alert"
            >
              <div className="card-title" style={{ color: 'var(--severe)' }}>
                <TriangleAlert size={13} /> Faster route available
              </div>
              <p className="recommend-text">{pendingAlert.text}</p>
              <div className="recommend-compare">
                <div>
                  <small>Current route</small>
                  <b className="mono">{minutes(pendingAlert.currentEta)}</b>
                </div>
                <ArrowRight size={16} />
                <div>
                  <small>Alternative</small>
                  <b className="mono">{minutes(pendingAlert.alternativeEta)}</b>
                </div>
                <div className="recommend-saving">
                  <small>You save</small>
                  <b className="mono">{minutes(pendingAlert.timeSaved)}</b>
                </div>
              </div>
              <div className="recommend-actions">
                <button className="btn btn-primary" type="button" onClick={() => switchRoute()} disabled={rerouting}>
                  {rerouting ? <Loader2 size={13} className="spin" /> : <RouteIcon size={13} />} Switch route
                </button>
                <button className="btn" type="button" onClick={() => keepRoute()} disabled={rerouting}>
                  Keep current route
                </button>
              </div>
              <p className="recommend-foot">
                Found by the traffic agent on the road ahead; figures are measured on the road graph.
              </p>
            </motion.div>
          )}
        </AnimatePresence>

        <ReroutingPanel
          state={rerouting ? 'rerouting' : rerouteResult ? 'result' : null}
          result={rerouteResult}
        />

        {current ? (
          <div className="card trip-card">
            <div className="card-title">
              <Navigation2 size={13} />
              {navState === 'arrived' ? 'Trip complete' : navigating ? 'Your trip' : 'Recommended route'}
              {trip?.rerouted && <span className="badge badge-blue" style={{ marginLeft: 'auto' }}>Rerouted</span>}
            </div>

            <div className="trip-ends">
              <span><MapPin size={12} /> {start?.name || 'Start'}</span>
              <ArrowRight size={12} />
              <span><Flag size={12} /> {end?.name || 'Destination'}</span>
            </div>
            {current.via && <p className="trip-via">via {current.via}</p>}

            <div className="trip-stats">
              <Stat icon={Clock} label={navigating ? 'ETA left' : 'ETA'}
                    value={minutes(navigating ? remainingEta : current.etaMin)}
                    hint={navigating && navReading ? 'measured on the road graph' : null} />
              <Stat icon={MapPin} label="Distance" value={`${current.distanceKm} km`}
                    hint={trip?.rerouted ? 'new route, from the switch' : null} />
              <Stat icon={Gauge} label="Traffic now" value={<TrafficValue congestion={trafficNow} />}
                    hint={navigating && outlook ? 'on the road ahead' : 'along the route'} />
              <Stat
                icon={outlook?.worsening ? TrendingUp : TrendingDown}
                label={`Predicted${outlook?.horizonMin ? ` +${outlook.horizonMin} min` : ''}`}
                value={predicted != null ? <TrafficValue congestion={predicted} /> : '—'}
                hint={navigating
                  ? (outlook?.forecastApplied ? 'LSTM forecast' : outlook ? 'forecast unavailable' : 'reading…')
                  : 'starts with navigation'}
                tone={outlook?.worsening ? 'warn' : undefined}
              />
              <Stat icon={CheckCircle2} label="Time saved"
                    value={minutes(trip?.timeSavedMin || 0)}
                    hint={trip?.rerouted ? 'vs staying on the jammed road' : 'no switch yet'}
                    tone={trip?.timeSavedMin > 0 ? 'good' : undefined} />
            </div>

            {navState === 'arrived' ? (
              <div className="trip-actions">
                <Link className="btn btn-primary" to="/user/history">View in history</Link>
                <button className="btn" type="button" onClick={clearTrip}>Plan another trip</button>
              </div>
            ) : navigating ? (
              <div className="trip-actions">
                {navState === 'driving'
                  ? <button className="btn" type="button" onClick={pauseNavigation} disabled={!!pendingAlert}><Pause size={13} /> Pause</button>
                  : <button className="btn btn-primary" type="button" onClick={resumeNavigation}><Play size={13} /> Resume</button>}
                <button className="btn" type="button" onClick={endTrip}><Square size={13} /> End trip</button>
              </div>
            ) : (
              <div className="trip-actions">
                <button
                  className="btn btn-primary btn-block"
                  type="button"
                  onClick={startNavigation}
                  disabled={navState === 'starting' || optimizing}
                >
                  {navState === 'starting' ? <Loader2 size={14} className="spin" /> : <Navigation2 size={14} />}
                  Start navigation
                </button>
              </div>
            )}
            {!navigating && navState !== 'arrived' && (
              <p className="trip-note">
                The car drives this route on the map at demo speed. The traffic
                agent watches the road ahead and tells you if a better one appears.
              </p>
            )}
          </div>
        ) : (
          <div className="card">
            <div className="card-title"><Navigation2 size={13} /> Your trip</div>
            <p style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.55 }}>
              Plan a route and it appears here: ETA, distance, traffic now and
              predicted, and any time saved by switching on the way.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
