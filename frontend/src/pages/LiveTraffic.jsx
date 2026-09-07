import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Activity, Clock, RefreshCw, TriangleAlert } from 'lucide-react'
import MapView from '../components/MapView'
import TrafficLegend from '../components/TrafficLegend'
import StatCard from '../components/StatCard'
import { useApp } from '../store/AppContext'
import { TRAFFIC_COLORS, TRAFFIC_LABELS } from '../data/mockData'

export default function LiveTraffic() {
  const { segments, incidents, settings } = useApp()
  const [updatedAt, setUpdatedAt] = useState(() => new Date())
  const [refreshing, setRefreshing] = useState(false)

  const counts = useMemo(() => {
    const c = { low: 0, moderate: 0, heavy: 0, severe: 0 }
    segments.forEach((s) => { c[s.level] += 1 })
    return c
  }, [segments])

  const avg = useMemo(
    () => (segments.reduce((s, x) => s + x.congestion, 0) / (segments.length || 1)) * 100,
    [segments]
  )

  const refresh = () => {
    setRefreshing(true)
    setTimeout(() => {
      setUpdatedAt(new Date())
      setRefreshing(false)
    }, 700)
  }

  return (
    <>
      <div className="row-between page-head">
        <div>
          <h1>Live Traffic</h1>
          <p>Congestion and incidents across the Hyderabad network.</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 11, color: 'var(--text-faint)', display: 'flex', alignItems: 'center', gap: 5 }}>
            <Clock size={11} />
            Updated {updatedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
          <button className="btn btn-sm" onClick={refresh} disabled={refreshing}>
            <motion.span
              animate={refreshing ? { rotate: 360 } : {}}
              transition={{ duration: 0.8, repeat: refreshing ? Infinity : 0, ease: 'linear' }}
              style={{ display: 'grid', placeItems: 'center' }}
            >
              <RefreshCw size={13} />
            </motion.span>
            Refresh
          </button>
        </div>
      </div>

      <div className="demo-notice" style={{ marginBottom: 14 }}>
        <Activity size={13} />
        <strong>Traffic Simulation Mode:</strong> Network values are generated from the Greenshields fundamental flow model on the Hyderabad OpenStreetMap graph. Connect live TomTom feed (`TOMTOM_API_KEY`) for real-time telemetry.
      </div>


      <div className="grid grid-4" style={{ marginBottom: 14 }}>
        <StatCard label="Average congestion" value={avg} decimals={1} suffix="%" tone="yellow" icon={Activity} delay={0} />
        <StatCard label="Monitored segments" value={segments.length} tone="brand" delay={0.05} />
        <StatCard label="Severe segments" value={counts.severe} tone="red" icon={TriangleAlert} delay={0.1} />
        <StatCard label="Active incidents" value={incidents.length} tone="orange" delay={0.15} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 330px', gap: 14, alignItems: 'start' }} className="lt-grid">
        <div className="map-shell" style={{ height: 'calc(100vh - var(--navbar-h) - 260px)', minHeight: 420 }}>
          <MapView
            segments={segments}
            incidents={incidents}
            showTraffic
            showIncidents
            mapStyle={settings.mapStyle}
          />
          <div className="map-overlay map-legend">
            <TrafficLegend showRoutes={false} />
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="card">
            <div className="card-title">
              <Activity size={13} />
              Congestion by Segment
            </div>
            <div style={{ maxHeight: 300, overflowY: 'auto', margin: '0 -4px' }}>
              {[...segments]
                .sort((a, b) => b.congestion - a.congestion)
                .map((s, i) => (
                  <motion.div
                    key={s.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.03, duration: 0.25 }}
                    style={{ padding: '7px 4px' }}
                  >
                    <div className="row-between" style={{ marginBottom: 4 }}>
                      <span style={{ fontSize: 12, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {s.name}
                      </span>
                      <span className="mono" style={{ fontSize: 11, color: TRAFFIC_COLORS[s.level] }}>
                        {Math.round(s.congestion * 100)}%
                      </span>
                    </div>
                    <div className="score-bar" style={{ height: 4 }}>
                      <motion.div
                        className="score-fill"
                        style={{ background: TRAFFIC_COLORS[s.level] }}
                        initial={{ width: 0 }}
                        animate={{ width: `${s.congestion * 100}%` }}
                        transition={{ duration: 0.6, delay: i * 0.03 }}
                      />
                    </div>
                  </motion.div>
                ))}
            </div>
          </div>

          <div className="card">
            <div className="card-title">
              <TriangleAlert size={13} />
              Incidents ({incidents.length})
            </div>
            {incidents.length === 0 ? (
              <div className="empty"><span style={{ fontSize: 12 }}>No active incidents</span></div>
            ) : (
              incidents.map((i) => (
                <div key={i.id} className="alt-route" style={{ cursor: 'default' }}>
                  <span className="alt-swatch" style={{ background: TRAFFIC_COLORS[i.severity] }} />
                  <div className="alt-body">
                    <strong>{i.name}</strong>
                    <span>{i.location} · {i.reportedAt}</span>
                  </div>
                  <span className="badge" style={{
                    background: `color-mix(in srgb, ${TRAFFIC_COLORS[i.severity]} 15%, transparent)`,
                    color: TRAFFIC_COLORS[i.severity],
                    borderColor: TRAFFIC_COLORS[i.severity],
                  }}>
                    {TRAFFIC_LABELS[i.severity]}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <style>{`@media (max-width: 1100px) { .lt-grid { grid-template-columns: 1fr !important; } }`}</style>
    </>
  )
}
