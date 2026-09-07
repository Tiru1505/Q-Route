import { useCallback, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Sliders, Zap } from 'lucide-react'
import MapView from '../components/MapView'
import RouteSelector from '../components/RouteSelector'
import RouteCard from '../components/RouteCard'
import AlternativeRoutes from '../components/AlternativeRoutes'
import OptimizationAnimation from '../components/OptimizationAnimation'
import TrafficLegend from '../components/TrafficLegend'
import { useApp } from '../store/AppContext'
import { ALGORITHMS, OPTIMIZATION_MODES } from '../data/mockData'

export default function RouteOptimizer() {
  const {
    routes, selectedRouteId, setSelectedRouteId, selectedRoute,
    optimize, optimizing, segments, incidents, start, end, mode, algorithm, settings,
  } = useApp()

  const [animating, setAnimating] = useState(false)
  const [revealed, setRevealed] = useState(routes.length > 0)

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
  const weights = OPTIMIZATION_MODES.find((m) => m.id === mode)?.weights
  const algoName = ALGORITHMS.find((a) => a.id === algorithm)?.name || 'QPSO'

  const handleOptimize = useCallback(async () => {
    setRevealed(false)
    setAnimating(true)
    await optimize()
  }, [optimize])

  return (
    <>
      <div className="page-head">
        <h1>Route Optimizer</h1>
        <p>Configure the objective function and run the optimization engine.</p>
      </div>


      <div className="dash-grid">
        <div className="dash-col">
          <RouteSelector onOptimize={handleOptimize} busy={optimizing || animating} />

          <div className="card">
            <div className="card-title">
              <Sliders size={13} />
              Objective Weights
            </div>
            <p style={{ fontSize: 11.5, color: 'var(--text-dim)', marginBottom: 12 }}>
              cost = w<sub>t</sub>·time + w<sub>d</sub>·distance + w<sub>c</sub>·congestion
            </p>
            {weights &&
              Object.entries(weights).map(([k, v]) => (
                <div key={k} style={{ marginBottom: 10 }}>
                  <div className="row-between" style={{ fontSize: 11, marginBottom: 5 }}>
                    <span style={{ textTransform: 'capitalize', color: 'var(--text-dim)' }}>{k}</span>
                    <span className="mono">{v.toFixed(2)}</span>
                  </div>
                  <div className="score-bar">
                    <motion.div
                      className="score-fill"
                      style={{ background: 'var(--brand)' }}
                      initial={{ width: 0 }}
                      animate={{ width: `${v * 100}%` }}
                      transition={{ duration: 0.5 }}
                    />
                  </div>
                </div>
              ))}
            <p style={{ fontSize: 10.5, color: 'var(--text-faint)', marginTop: 6 }}>
              Weights are set by the selected mode. All algorithms receive the same
              weights, so the benchmark stays fair.
            </p>
          </div>

          <OptimizationAnimation
            running={animating}
            onComplete={() => {
              setAnimating(false)
              setRevealed(true)
            }}
            algorithmName={algoName}
          />
        </div>

        <div className="dash-col">
          <div className="map-shell">
            <MapView
              routes={revealed ? routes : []}
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
          </div>
        </div>

        <div className="dash-col dash-col-right">
          {revealed && selectedRoute ? (
            <>
              <RouteCard route={selectedRoute} />
              <AlternativeRoutes
                routes={routes}
                selectedId={selectedRouteId}
                onSelect={setSelectedRouteId}
              />
            </>
          ) : (
            <div className="card">
              <div className="empty">
                <Zap size={26} />
                <strong style={{ fontSize: 13, color: 'var(--text-dim)' }}>No route yet</strong>
                <span style={{ fontSize: 11.5 }}>
                  Choose your endpoints and press Optimize Route.
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
