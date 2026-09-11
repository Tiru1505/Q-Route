import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { ArrowRight, Car, History as HistoryIcon, Search } from 'lucide-react'
import { CardSkeleton } from '../../components/LoadingScreen'
import { getTrips } from '../../services/api'
import { TRAFFIC_COLORS, TRAFFIC_LABELS } from '../../data/mockData'

/**
 * Trips the signed-in user actually drove, from the server's `trips` records.
 *
 * Nothing here is generated: an empty list means no trips yet. The switch
 * figures come from the engine at the moment of the switch —
 *   Original ETA   staying on the road you were on, from where you were
 *   Optimized ETA  the route you switched to
 *   Time saved     the difference, summed over every switch
 * — not from comparing with the plan, which a jam that formed mid-journey
 * would make meaningless.
 */

const STATUS = {
  completed: { label: 'Completed', badge: 'badge-green' },
  active: { label: 'In progress', badge: 'badge-blue' },
  cancelled: { label: 'Ended early', badge: 'badge-grey' },
}

function minutes(m) {
  if (m == null) return '—'
  const total = Math.round(m)
  if (total < 60) return `${total} min`
  return `${Math.floor(total / 60)}h ${String(total % 60).padStart(2, '0')}m`
}

function when(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' })} · ${
    d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
}

function TripCard({ trip, index }) {
  const status = STATUS[trip.status] || STATUS.cancelled
  const optimized = trip.rerouted
  return (
    <motion.article
      className="card trip-history-card"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, delay: Math.min(index, 8) * 0.04 }}
    >
      <header className="trip-history-head">
        <div className="trip-history-route">
          <span><small>From</small>{trip.source?.name || 'Start'}</span>
          <ArrowRight size={14} aria-hidden="true" />
          <span><small>To</small>{trip.destination?.name || 'Destination'}</span>
        </div>
        <div className="trip-history-badges">
          {optimized && <span className="badge badge-quantum">Route optimized</span>}
          <span className={`badge ${status.badge}`}>{status.label}</span>
        </div>
      </header>

      <dl className="trip-history-facts">
        <div><dt>Date</dt><dd>{when(trip.createdAt)}</dd></div>
        <div><dt>Route</dt><dd>{trip.route?.label || 'Route'}{trip.route?.via ? ` · via ${trip.route.via}` : ''}</dd></div>
        <div><dt>Planned ETA</dt><dd className="mono">{minutes(trip.plannedEtaMin)}</dd></div>
        <div><dt>Distance</dt><dd className="mono">{trip.distanceKm} km</dd></div>
        <div>
          <dt>Traffic at start</dt>
          <dd className="trip-traffic">
            <span className="dot" style={{ background: TRAFFIC_COLORS[trip.trafficCondition] }} />
            {TRAFFIC_LABELS[trip.trafficCondition] || '—'}
          </dd>
        </div>
        <div><dt>Vehicle</dt><dd style={{ textTransform: 'capitalize' }}>{(trip.vehicle || 'car').replace('_', ' ')}</dd></div>
        <div>
          <dt>Rerouted</dt>
          <dd>{optimized ? `Yes · ${trip.reroutes.length} switch${trip.reroutes.length > 1 ? 'es' : ''}` : 'No'}
            {trip.declined ? ` · ${trip.declined} kept` : ''}</dd>
        </div>
      </dl>

      {optimized && (
        <div className="trip-history-saving">
          <div><small>Original ETA</small><b className="mono">{minutes(trip.originalEtaMin)}</b></div>
          <ArrowRight size={14} aria-hidden="true" />
          <div><small>Optimized ETA</small><b className="mono">{minutes(trip.optimizedEtaMin)}</b></div>
          <div className="trip-history-saved"><small>Time saved</small><b className="mono">{minutes(trip.timeSavedMin)}</b></div>
        </div>
      )}
    </motion.article>
  )
}

export default function TripHistory() {
  const [trips, setTrips] = useState(null)
  const [failed, setFailed] = useState(null)
  const [q, setQ] = useState('')

  useEffect(() => {
    let cancelled = false
    getTrips()
      .then((d) => !cancelled && setTrips(d.trips || []))
      .catch((err) => !cancelled && setFailed(err.message || 'Could not load your trips.'))
    return () => { cancelled = true }
  }, [])

  const shown = useMemo(() => {
    if (!trips) return null
    const t = q.trim().toLowerCase()
    if (!t) return trips
    return trips.filter((r) => `${r.source?.name} ${r.destination?.name}`.toLowerCase().includes(t))
  }, [trips, q])

  const totals = useMemo(() => {
    if (!trips?.length) return null
    return {
      trips: trips.length,
      rerouted: trips.filter((t) => t.rerouted).length,
      saved: trips.reduce((sum, t) => sum + (t.timeSavedMin || 0), 0),
    }
  }, [trips])

  return (
    <>
      <div className="row-between page-head">
        <div>
          <h1>Trip History</h1>
          <p>Journeys you drove, and what switching route saved.</p>
        </div>
        <div style={{ position: 'relative', width: 240, maxWidth: '45vw' }}>
          <Search size={13} style={{
            position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-faint)',
          }} />
          <input className="input" style={{ paddingLeft: 31 }} placeholder="Search places…"
                 value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search trips by place" />
        </div>
      </div>

      {totals && (
        <div className="trip-totals">
          <div><small>Trips</small><b className="mono">{totals.trips}</b></div>
          <div><small>Rerouted</small><b className="mono">{totals.rerouted}</b></div>
          <div><small>Time saved</small><b className="mono">{minutes(totals.saved)}</b></div>
        </div>
      )}

      {failed ? (
        <div className="card" role="alert"><p style={{ fontSize: 12.5, color: 'var(--text-dim)' }}>{failed}</p></div>
      ) : !shown ? (
        <CardSkeleton height={260} />
      ) : shown.length === 0 ? (
        <div className="card">
          <div className="empty">
            {q.trim() ? <HistoryIcon size={28} /> : <Car size={28} />}
            <strong style={{ fontSize: 13, color: 'var(--text-dim)' }}>
              {q.trim() ? 'No matching trips' : 'No trips yet'}
            </strong>
            <span style={{ fontSize: 12 }}>
              {q.trim()
                ? 'Try a different place name.'
                : <>Plan a route and press <strong>Start navigation</strong> — each trip is saved here. <Link to="/user/dashboard">Go to the dashboard</Link></>}
            </span>
          </div>
        </div>
      ) : (
        <div className="trip-history-list">
          {shown.map((t, i) => <TripCard key={t.id} trip={t} index={i} />)}
        </div>
      )}
    </>
  )
}
