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
import { TRAFFIC_COLORS } from '../../data/mockData'
import { translateSegments } from '../../i18n'
import { durationParts, kmParts, minutesLabel } from '../../i18n/format'
import { SlidingNumber } from '../../components/motion-primitives/SlidingNumber'
import { BorderTrail } from '../../components/motion-primitives/BorderTrail'

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



/**
 * A translated unit string with its digits rolling rather than jumping.
 * The number never leaves the sentence the dictionary wrote: `translateSegments`
 * hands back the template's own pieces in order, so the unit word stays wherever
 * that language puts it and only the numeric slots become SlidingNumbers.
 */
function AnimatedUnit({ language, tKey, vars, pad = [] }) {
  return (
    <>
      {translateSegments(language, tKey, vars).map((segment, i) => (
        segment.text != null
          ? <span key={i} style={{ whiteSpace: 'pre' }}>{segment.text}</span>
          : <SlidingNumber key={i} value={segment.number} padStart={pad.includes(segment.name)} />
      ))}
    </>
  )
}

/** The same duration format as everywhere else, rendered rather than stringified. */
function Duration({ language, m }) {
  const parts = durationParts(m)
  if (!parts) return <>—</>
  return <AnimatedUnit language={language} tKey={parts.tKey} vars={parts.vars} pad={parts.pad} />
}

/** Likewise for distance, so the 100 km precision rule is not restated here. */
function Distance({ language, km }) {
  const parts = kmParts(km)
  if (!parts) return <>—</>
  return <AnimatedUnit language={language} tKey={parts.tKey} vars={parts.vars} />
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

function TrafficValue({ congestion, t }) {
  const level = levelOf(congestion)
  if (!level) return <>—</>
  return (
    <span className="trip-traffic">
      <span className="dot" style={{ background: TRAFFIC_COLORS[level] }} />
      {t(`traffic.${level}`)} · {pct(congestion)}
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
    pauseNavigation, resumeNavigation, clearTrip, t, language,
  } = useApp()

  // Bound to the chosen language, so every duration on the page reads in it.
  const mins = (m) => minutesLabel(t, m)

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
            recenterLabel={t('map.recenter')}
            followingLabel={t('map.following')}
          />
          <div className="map-overlay map-legend"><TrafficLegend /></div>

          <div className="map-overlay map-topright">
            {optimizing && (
              <div className="legend-card user-finding">
                <Loader2 size={13} className="spin" /> {t('planner.finding')}
              </div>
            )}
            {!optimizing && !routes.length && (
              <div className="legend-card" style={{ maxWidth: 220 }}>
                <div className="legend-title">{t('trip.whereTo')}</div>
                <p style={{ fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.5 }}>
                  {t('trip.whereToHint')}
                </p>
              </div>
            )}
            {navigating && (
              <div className="legend-card nav-hud" aria-live="polite">
                <div className="legend-title">
                  {pendingAlert ? t('trip.waitingDecision')
                    : navState === 'paused' ? t('trip.paused') : t('trip.navigating')}
                </div>
                <div className="nav-hud-row">
                  <Clock size={11} /> {t('trip.left', { v: mins(remainingEta) })}
                </div>
                <div className="nav-progress"><span style={{ width: `${Math.round(legFraction * 100)}%` }} /></div>
                <small>
                  {t('trip.simulatedDrive')}
                  {speedup ? ` · ${t('trip.speed', { n: speedup })}` : ''}
                </small>
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
              style={{ position: 'relative' }}
              role="alert"
            >
              <BorderTrail size={64} style={{ background: 'var(--severe)' }} />
              <div className="card-title" style={{ color: 'var(--severe)' }}>
                <TriangleAlert size={13} /> {t('recommend.title')}
              </div>
              <p className="recommend-text">{pendingAlert.text}</p>
              <div className="recommend-compare">
                <div>
                  <small>{t('recommend.currentRoute')}</small>
                  <b className="mono"><Duration language={language} m={pendingAlert.currentEta} /></b>
                </div>
                <ArrowRight size={16} />
                <div>
                  <small>{t('recommend.alternative')}</small>
                  <b className="mono"><Duration language={language} m={pendingAlert.alternativeEta} /></b>
                </div>
                <div className="recommend-saving">
                  <small>{t('recommend.youSave')}</small>
                  <b className="mono"><Duration language={language} m={pendingAlert.timeSaved} /></b>
                </div>
              </div>
              <div className="recommend-actions">
                <button className="btn btn-primary" type="button" onClick={() => switchRoute()} disabled={rerouting}>
                  {rerouting ? <Loader2 size={13} className="spin" /> : <RouteIcon size={13} />} {t('recommend.switch')}
                </button>
                <button className="btn" type="button" onClick={() => keepRoute()} disabled={rerouting}>
                  {t('recommend.keep')}
                </button>
              </div>
              <p className="recommend-foot">
                {t('recommend.foot')}
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
              {navState === 'arrived' ? t('trip.complete')
                : navigating ? t('trip.yourTrip') : t('trip.recommended')}
              {trip?.rerouted && (
                <span className="badge badge-blue" style={{ marginLeft: 'auto' }}>{t('trip.rerouted')}</span>
              )}
            </div>

            <div className="trip-ends">
              <span><MapPin size={12} /> {start?.name || 'Start'}</span>
              <ArrowRight size={12} />
              <span><Flag size={12} /> {end?.name || 'Destination'}</span>
            </div>
            {current.via && <p className="trip-via">{current.via}</p>}

            <div className="trip-stats">
              <Stat icon={Clock} label={navigating ? t('trip.etaLeft') : t('trip.eta')}
                    value={<Duration language={language} m={navigating ? remainingEta : current.etaMin} />}
                    hint={navigating && navReading ? t('trip.measured') : null} />
              <Stat icon={MapPin} label={t('trip.distance')}
                    value={<Distance language={language} km={current.distanceKm} />}
                    hint={trip?.rerouted ? t('trip.newRouteFromSwitch') : null} />
              <Stat icon={Gauge} label={t('trip.trafficNow')}
                    value={<TrafficValue congestion={trafficNow} t={t} />}
                    hint={navigating && outlook ? t('trip.onRoadAhead') : t('trip.alongRoute')} />
              <Stat
                icon={outlook?.worsening ? TrendingUp : TrendingDown}
                label={`${t('trip.predicted')}${outlook?.horizonMin
                  ? ` +${t('units.min', { n: outlook.horizonMin })}` : ''}`}
                value={predicted != null ? <TrafficValue congestion={predicted} t={t} /> : '—'}
                hint={navigating
                  ? (outlook?.forecastApplied ? t('trip.lstmForecast')
                    : outlook ? t('trip.forecastUnavailable') : t('trip.reading'))
                  : t('trip.startsWithNavigation')}
                tone={outlook?.worsening ? 'warn' : undefined}
              />
              <Stat icon={CheckCircle2} label={t('trip.timeSaved')}
                    value={<Duration language={language} m={trip?.timeSavedMin || 0} />}
                    hint={trip?.rerouted ? t('trip.vsStaying') : t('trip.noSwitchYet')}
                    tone={trip?.timeSavedMin > 0 ? 'good' : undefined} />
            </div>

            {navState === 'arrived' ? (
              <div className="trip-actions">
                <Link className="btn btn-primary" to="/user/history">{t('trip.viewInHistory')}</Link>
                <button className="btn" type="button" onClick={clearTrip}>{t('trip.planAnother')}</button>
              </div>
            ) : navigating ? (
              <div className="trip-actions">
                {navState === 'driving'
                  ? <button className="btn" type="button" onClick={pauseNavigation} disabled={!!pendingAlert}><Pause size={13} /> {t('trip.pause')}</button>
                  : <button className="btn btn-primary" type="button" onClick={resumeNavigation}><Play size={13} /> {t('trip.resume')}</button>}
                <button className="btn" type="button" onClick={endTrip}><Square size={13} /> {t('trip.endTrip')}</button>
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
                  {t('trip.startNavigation')}
                </button>
              </div>
            )}
            {!navigating && navState !== 'arrived' && (
              <p className="trip-note">{t('trip.note')}</p>
            )}
          </div>
        ) : (
          <div className="card">
            <div className="card-title"><Navigation2 size={13} /> {t('trip.yourTrip')}</div>
            <p style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.55 }}>
              {t('trip.empty')}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
