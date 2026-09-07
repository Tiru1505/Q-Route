import { useMemo, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { BellOff, CloudRain, Construction, Filter, Radio, TrafficCone, Waypoints } from 'lucide-react'
import TrafficAlert from '../components/TrafficAlert'
import { useApp } from '../store/AppContext'

const TRIGGERS = [
  { id: 'congestion', label: 'Congestion',  icon: TrafficCone,  hint: 'Congestion building at Mehdipatnam – Masab Tank' },
  { id: 'incident',   label: 'Accident',    icon: Construction, hint: 'Accident on the PVNR Expressway, two lanes blocked' },
  { id: 'closure',    label: 'Road closed', icon: Construction, hint: 'Tank Bund Road closed for an event' },
  { id: 'reroute',    label: 'Better route',icon: Waypoints,    hint: 'A faster route is available' },
  { id: 'weather',    label: 'Heavy rain',  icon: CloudRain,    hint: 'Heavy rain across the city, speeds down 30%' },
]

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'predictive', label: 'Predictive' },
  { id: 'incident', label: 'Incidents' },
  { id: 'reroute', label: 'Route changes' },
]

export default function Alerts() {
  const { alerts, dismissAlert, runReroute, raiseAlert, wipeAlerts } = useApp()
  const [filter, setFilter] = useState('all')
  const [raising, setRaising] = useState(null)

  const fire = async (id) => {
    setRaising(id)
    await raiseAlert(id)
    setRaising(null)
  }

  const visible = useMemo(
    () => (filter === 'all' ? alerts : alerts.filter((a) => a.kind === filter)),
    [alerts, filter]
  )

  const counts = useMemo(() => {
    const c = { severe: 0, heavy: 0, moderate: 0 }
    alerts.forEach((a) => { if (c[a.severity] !== undefined) c[a.severity] += 1 })
    return c
  }, [alerts])

  return (
    <>
      <div className="row-between page-head">
        <div>
          <h1>Alerts</h1>
          <p>Predictive warnings, incidents and route-change notifications.</p>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <span className="badge badge-red">{counts.severe} severe</span>
          <span className="badge badge-orange">{counts.heavy} heavy</span>
          <span className="badge badge-yellow">{counts.moderate} moderate</span>
        </div>
      </div>

      {/* Raising an alert on demand.

          The alert engine only fires when traffic genuinely degrades past its
          policy gates — correct behaviour, and impossible to schedule for a
          live demonstration. These buttons ask the backend to raise a real
          alert through the same service and storage, so what appears came back
          from the server. It is recorded as manually triggered, which is why
          this panel says so on its face rather than pretending otherwise. */}
      <div className="card trigger-panel">
        <div className="trigger-head">
          <Radio size={13} />
          <strong>Raise an alert</strong>
          <span>manually triggered, for demonstration</span>
        </div>
        <div className="trigger-grid">
          {TRIGGERS.map((t) => (
            <button
              key={t.id}
              className="btn btn-sm trigger-btn"
              onClick={() => fire(t.id)}
              disabled={raising !== null}
              title={t.hint}
            >
              <t.icon size={13} />
              <span>{raising === t.id ? 'Raising…' : t.label}</span>
            </button>
          ))}
          <button
            className="btn btn-sm trigger-btn trigger-clear"
            onClick={wipeAlerts}
            disabled={raising !== null}
            title="Remove every alert so the demonstration can be replayed"
          >
            <BellOff size={13} />
            <span>Clear all</span>
          </button>
        </div>
      </div>

      <div className="card" style={{ padding: 10, marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
          <Filter size={13} style={{ color: 'var(--text-faint)' }} />
          {FILTERS.map((f) => (
            <button
              key={f.id}
              className="btn btn-sm"
              onClick={() => setFilter(f.id)}
              style={
                filter === f.id
                  ? {
                      background: 'var(--brand-light)',
                      borderColor: 'var(--brand)',
                      color: 'var(--brand)',
                      fontWeight: 600,
                    }
                  : undefined
              }
            >
              {f.label}
              {f.id !== 'all' && (
                <span style={{ color: 'var(--text-faint)' }}>
                  {alerts.filter((a) => a.kind === f.id).length}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {visible.length === 0 ? (
        <div className="card">
          <div className="empty">
            <BellOff size={30} />
            <strong style={{ fontSize: 13, color: 'var(--text-dim)' }}>No alerts</strong>
            <span style={{ fontSize: 12 }}>
              {alerts.length === 0
                ? "You've dismissed everything. Run Demo Mode to generate new alerts."
                : 'Nothing matches this filter.'}
            </span>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <AnimatePresence mode="popLayout">
            {visible.map((a) => (
              <TrafficAlert
                key={a.id}
                alert={a}
                onDismiss={dismissAlert}
                onAction={a.kind !== 'incident' ? runReroute : undefined}
              />
            ))}
          </AnimatePresence>
        </div>
      )}
    </>
  )
}
