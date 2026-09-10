import { useCallback, useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Clock, Gauge, MapPin, Radio, TriangleAlert } from 'lucide-react'
import MapView from '../components/MapView'
import RouteSelector from '../components/RouteSelector'
import RouteCard from '../components/RouteCard'
import AlternativeRoutes from '../components/AlternativeRoutes'
import OptimizationAnimation from '../components/OptimizationAnimation'
import QPSOVisualization from '../components/QPSOVisualization'
import TrafficAlert from '../components/TrafficAlert'
import ReroutingPanel from '../components/ReroutingPanel'
import TrafficLegend from '../components/TrafficLegend'
import { useApp } from '../store/AppContext'
import { ALGORITHMS } from '../data/mockData'

// Each step is reached by the backend doing it, not by a timer: the alert
// step by the monitor's own alert arriving, the last by the assistant's check.
const DEMO_STEPS = [
  { id: 'optimizing', label: 'Optimize' },
  { id: 'traffic-rising', label: 'Traffic spike' },
  { id: 'alert', label: 'Auto alert' },
  { id: 'rerouting', label: 'Switch route' },
  { id: 'done', label: 'AI checks route' },
]

export default function Dashboard() {
  const {
    routes, selectedRoute, selectedRouteId, setSelectedRouteId,
    optimize, optimizing, error,
    segments, incidents, start, end, algorithm,
    spikeAt, spiking, latestAlert, triggerSpike,
    rerouting, rerouteResult,
    demoMode, demoStep, settings, lastRun,
  } = useApp()

  // Gate the reveal on the staged animation, not on the request finishing.
  const [animating, setAnimating] = useState(false)
  const [revealed, setRevealed] = useState(false)

  // start/end are already resolved places from the search box; the map only
  // needs the [lat, lon] tuple shape alongside them.
  const startPoint = useMemo(
    () => (start ? { ...start, coords: start.coords || [start.lat, start.lon] } : null),
    [start],
  )
  const endPoint = useMemo(
    () => (end ? { ...end, coords: end.coords || [end.lat, end.lon] } : null),
    [end],
  )
  const algoName = ALGORITHMS.find((a) => a.id === algorithm)?.name || 'QPSO'

  const handleOptimize = useCallback(async () => {
    setRevealed(false)
    setAnimating(true)
    await optimize()
  }, [optimize])

  const handleAnimationDone = useCallback(() => {
    setAnimating(false)
    setRevealed(true)
  }, [])

  // Demo mode drives the same reveal without a click.
  useEffect(() => {
    if (!demoMode) return
    if (demoStep === 'optimizing') {
      setRevealed(false)
      setAnimating(true)
    }
  }, [demoMode, demoStep])

  useEffect(() => {
    if (!demoMode && routes.length && !animating) setRevealed(true)
  }, [demoMode, routes.length, animating])

  const showResults = revealed && routes.length > 0

  // A spike is on the road and the monitor has not answered yet. Nothing here
  // decides that an alert happened — that arrives from the backend.
  const alertArrived = !!(latestAlert && spikeAt && latestAlert.receivedAt >= spikeAt)
  const awaitingAlert = !!spikeAt && !alertArrived && !rerouteResult

  const rerouteState = rerouting
    ? 'rerouting'
    : rerouteResult
    ? 'result'
    : awaitingAlert
    ? 'detecting'
    : null

  return (
    <>
      <AnimatePresence>
        {demoMode && (
          <motion.div
            className="demo-strip"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <Radio size={15} style={{ color: 'var(--quantum)' }} />
            <strong style={{ fontSize: 12.5 }}>Demo Mode</strong>
            <span style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>
              Live end-to-end — the system raises every alert itself
            </span>
            <div className="steps">
              {DEMO_STEPS.map((s, i) => {
                const idx = DEMO_STEPS.findIndex((x) => x.id === demoStep)
                return (
                  <span key={s.id} className="demo-pill" data-on={i <= idx}>
                    {s.label}
                  </span>
                )
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="dash-grid">
        {/* ------------------------------------------------------- left */}
        <div className="dash-col">
          <RouteSelector onOptimize={handleOptimize} busy={optimizing || animating} />

          <OptimizationAnimation
            running={animating}
            onComplete={handleAnimationDone}
            algorithmName={algoName}
          />

          <QPSOVisualization
            active={animating || demoStep === 'optimizing'}
            convergence={lastRun?.convergence}
            algorithm={lastRun?.algorithm || algorithm}
            runtimeMs={lastRun?.computeMs}
          />
        </div>

        {/* ------------------------------------------------------ centre */}
        <div className="dash-col">
          <div className="map-shell">
            <MapView
              routes={showResults ? routes : []}
              selectedRouteId={selectedRouteId}
              onSelectRoute={setSelectedRouteId}
              segments={segments}
              incidents={incidents}
              startPoint={startPoint}
              endPoint={endPoint}
              mapStyle={settings.mapStyle}
              routeTransition={animating || optimizing}
            />

            <div className="map-overlay map-legend">
              <TrafficLegend />
            </div>

            <div className="map-overlay map-topright">
              {!showResults && !animating && (
                <div className="legend-card" style={{ maxWidth: 216 }}>
                  <div className="legend-title">Getting started</div>
                  <p style={{ fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.5 }}>
                    Pick a start and destination, then run the optimizer — or press
                    Demo Mode for the full scenario.
                  </p>
                </div>
              )}

              {showResults && selectedRoute && (
                <motion.div
                  className="legend-card"
                  initial={{ opacity: 0, x: 14 }}
                  animate={{ opacity: 1, x: 0 }}
                >
                  <div className="legend-title">Active route</div>
                  <div style={{ display: 'flex', gap: 12, fontSize: 12 }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <MapPin size={11} style={{ color: 'var(--route-blue)' }} />
                      {selectedRoute.distanceKm} km
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Clock size={11} style={{ color: 'var(--route-blue)' }} />
                      {selectedRoute.etaMin} min
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Gauge size={11} style={{ color: 'var(--moderate)' }} />
                      {Math.round(selectedRoute.congestion * 100)}%
                    </span>
                  </div>
                </motion.div>
              )}
            </div>
          </div>
        </div>

        {/* ------------------------------------------------------- right */}
        <div className="dash-col dash-col-right">
          {error && (
            <div className="card" style={{ borderColor: 'rgba(239,68,68,.3)' }}>
              <div style={{ display: 'flex', gap: 9, alignItems: 'flex-start' }}>
                <TriangleAlert size={15} style={{ color: 'var(--severe)', flexShrink: 0, marginTop: 2 }} />
                <div>
                  <h4 style={{ fontSize: 13, marginBottom: 3 }}>Optimization failed</h4>
                  <p style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>{error}</p>
                </div>
              </div>
            </div>
          )}

          <AnimatePresence mode="popLayout">
            {showResults && selectedRoute && <RouteCard key={selectedRoute.id} route={selectedRoute} />}
          </AnimatePresence>

          {showResults && (
            <AlternativeRoutes
              routes={routes}
              selectedId={selectedRouteId}
              onSelect={setSelectedRouteId}
            />
          )}

          <ReroutingPanel
            state={rerouteState}
            result={rerouteResult}
            onAccept={() => setSelectedRouteId(rerouteResult?.newRoute?.id)}
          />

          {!demoMode && !rerouteResult && !awaitingAlert && showResults && (
            <div className="card">
              <div className="card-title">
                <TriangleAlert size={13} />
                Traffic Simulation
              </div>
              <p style={{ fontSize: 11.5, color: 'var(--text-dim)', marginBottom: 11 }}>
                Congest the road ahead of the driver. The monitor detects it on
                its own and alerts you if a better route exists — this button
                changes the traffic, not the alert.
              </p>
              <button className="btn btn-sm btn-block" onClick={() => triggerSpike()} disabled={spiking}>
                {spiking ? 'Applying spike…' : 'Simulate Congestion Spike'}
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
