import { useEffect, useState } from 'react'
import { Activity, AlertOctagon, BarChart3, Clock, RefreshCw, Route as RouteIcon, TrendingUp } from 'lucide-react'
import StatCard from '../components/StatCard'
import PredictionCard from '../components/PredictionCard'
import { CardSkeleton } from '../components/LoadingScreen'
import {
  RoutePerformanceChart, TrafficDistributionChart, TrafficTrendChart,
} from '../components/TrafficChart'
import { getAnalytics, isUsingFallback } from '../services/api'
import { useApp } from '../store/AppContext'

const ICONS = [Activity, Clock, BarChart3, TrendingUp, AlertOctagon, RouteIcon]

export default function Analytics() {
  const { routesVersion } = useApp()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [reloading, setReloading] = useState(false)
  const [nudge, setNudge] = useState(0)
  const [updatedAt, setUpdatedAt] = useState(null)

  // routesVersion is in the dependency list on purpose: optimising a route
  // stores it server-side, and the Route Performance chart is built from that
  // history. Without this the charts would keep showing whatever was true when
  // the page first mounted, even after several new routes had been run.
  useEffect(() => {
    let cancelled = false
    setReloading(true)
    getAnalytics()
      .then((d) => {
        if (cancelled) return
        setData(d)
        setError(null)
        setUpdatedAt(new Date())
      })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setReloading(false))
    return () => { cancelled = true }
  }, [routesVersion, nudge])

  if (error) {
    return (
      <div className="card" style={{ borderColor: 'rgba(239,68,68,.3)' }}>
        <div className="empty">
          <AlertOctagon size={26} style={{ color: 'var(--severe)' }} />
          <strong style={{ fontSize: 13 }}>Could not load analytics</strong>
          <span style={{ fontSize: 12 }}>{error}</span>
        </div>
      </div>
    )
  }

  return (
    <>
      <div className="row-between page-head">
        <div>
          <h1>Analytics</h1>
          <p>Traffic patterns, prediction accuracy and route performance.</p>
        </div>
        <div className="analytics-actions">
          {updatedAt && (
            <span className="analytics-stamp">
              <Clock size={11} />
              {updatedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          )}
          <button
            className="btn btn-sm"
            onClick={() => setNudge((n) => n + 1)}
            disabled={reloading}
            title="Re-read the latest figures from the engine"
          >
            <RefreshCw size={13} className={reloading ? 'spin' : undefined} />
            {reloading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Two different reasons this can show, and they need different wording:
          the build is deliberately in demo mode, or it wanted the real API and
          could not reach it. Telling someone to "edit api.js" in the second
          case sends them to the wrong place — the wiring is fine, the backend
          is just not answering. */}
      {data?.isDemoData && (
        <div className="demo-notice">
          <Activity size={13} />
          Demo data — replace via <code>src/services/api.js</code> once the backend is live.
        </div>
      )}


      <div className="grid grid-3" style={{ marginBottom: 14 }}>
        {data
          ? data.stats.map((s, i) => (
              <StatCard key={s.label} {...s} icon={ICONS[i]} delay={i * 0.05} />
            ))
          : Array.from({ length: 6 }, (_, i) => <CardSkeleton key={i} height={104} />)}
      </div>

      <div className="grid grid-2" style={{ marginBottom: 14 }}>
        <div className="card chart-card">
          <div className="card-title">
            <TrendingUp size={13} />
            Traffic Trend — 24 hours
          </div>
          {data ? <TrafficTrendChart data={data.trend} /> : <CardSkeleton height={260} />}
        </div>

        {data ? (
          <PredictionCard
            series={data.prediction}
            title="Actual vs Predicted Congestion"
            note={data.predictionNote}
          />
        ) : (
          <CardSkeleton height={300} />
        )}
      </div>

      <div className="grid grid-2">
        <div className="card chart-card">
          <div className="card-title">
            <RouteIcon size={13} />
            Route Performance
          </div>
          {data ? <RoutePerformanceChart data={data.performance} height={300} /> : <CardSkeleton height={260} />}
        </div>

        <div className="card chart-card">
          <div className="card-title">
            <BarChart3 size={13} />
            Traffic Distribution
          </div>
          {data ? (
            <TrafficDistributionChart data={data.distribution} />
          ) : (
            <CardSkeleton height={260} />
          )}
        </div>
      </div>
    </>
  )
}
