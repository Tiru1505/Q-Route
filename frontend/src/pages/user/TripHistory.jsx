import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { ArrowRight, Car, History as HistoryIcon, Search } from 'lucide-react'
import { CardSkeleton } from '../../components/LoadingScreen'
import { getTrips } from '../../services/api'
import { TRAFFIC_COLORS } from '../../data/mockData'
import { kmLabel, minutesLabel } from '../../i18n/format'
import { useApp } from '../../store/AppContext'

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
  completed: { key: 'history.completed', badge: 'badge-green' },
  active: { key: 'history.inProgress', badge: 'badge-blue' },
  cancelled: { key: 'history.endedEarly', badge: 'badge-grey' },
}



// Dates follow the chosen language: 16 సెప్టెంబర్ 2026 rather than 16 Sep 2026.
function when(iso, language) {
  if (!iso) return ''
  const d = new Date(iso)
  const locale = language === 'en' ? [] : `${language}-IN`
  return `${d.toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric' })} · ${
    d.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })}`
}

function TripCard({ trip, index, t, language }) {
  const status = STATUS[trip.status] || STATUS.cancelled
  const optimized = trip.rerouted
  const mins = (m) => minutesLabel(t, m)
  return (
    <motion.article
      className="card trip-history-card"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, delay: Math.min(index, 8) * 0.04 }}
    >
      <header className="trip-history-head">
        <div className="trip-history-route">
          <span><small>{t('history.from')}</small>{trip.source?.name || 'Start'}</span>
          <ArrowRight size={14} aria-hidden="true" />
          <span><small>{t('history.to')}</small>{trip.destination?.name || 'Destination'}</span>
        </div>
        <div className="trip-history-badges">
          {optimized && <span className="badge badge-quantum">{t('history.routeOptimized')}</span>}
          <span className={`badge ${status.badge}`}>{t(status.key)}</span>
        </div>
      </header>

      <dl className="trip-history-facts">
        <div><dt>{t('history.date')}</dt><dd>{when(trip.createdAt, language)}</dd></div>
        <div><dt>{t('history.route')}</dt><dd>{trip.route?.label || 'Route'}{trip.route?.via ? ` · ${trip.route.via}` : ''}</dd></div>
        <div><dt>{t('history.plannedEta')}</dt><dd className="mono">{mins(trip.plannedEtaMin)}</dd></div>
        <div><dt>{t('trip.distance')}</dt><dd className="mono">{kmLabel(t, trip.distanceKm)}</dd></div>
        <div>
          <dt>{t('history.trafficAtStart')}</dt>
          <dd className="trip-traffic">
            <span className="dot" style={{ background: TRAFFIC_COLORS[trip.trafficCondition] }} />
            {trip.trafficCondition ? t(`traffic.${trip.trafficCondition}`) : '—'}
          </dd>
        </div>
        <div><dt>{t('history.vehicle')}</dt><dd style={{ textTransform: 'capitalize' }}>{(trip.vehicle || 'car').replace('_', ' ')}</dd></div>
        <div>
          <dt>{t('history.wasRerouted')}</dt>
          <dd>{optimized
            ? `${t('history.yes')} · ${trip.reroutes.length > 1
              ? t('history.switches', { n: trip.reroutes.length }) : t('history.oneSwitch')}`
            : t('history.no')}
            {trip.declined ? ` · ${t('history.kept', { n: trip.declined })}` : ''}</dd>
        </div>
      </dl>

      {optimized && (
        <div className="trip-history-saving">
          <div><small>{t('history.originalEta')}</small><b className="mono">{mins(trip.originalEtaMin)}</b></div>
          <ArrowRight size={14} aria-hidden="true" />
          <div><small>{t('history.optimizedEta')}</small><b className="mono">{mins(trip.optimizedEtaMin)}</b></div>
          <div className="trip-history-saved"><small>{t('trip.timeSaved')}</small><b className="mono">{mins(trip.timeSavedMin)}</b></div>
        </div>
      )}
    </motion.article>
  )
}

export default function TripHistory() {
  const { t, language } = useApp()
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
          <h1>{t('history.title')}</h1>
          <p>{t('history.subtitle')}</p>
        </div>
        <div style={{ position: 'relative', width: 240, maxWidth: '45vw' }}>
          <Search size={13} style={{
            position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-faint)',
          }} />
          <input className="input" style={{ paddingLeft: 31 }} placeholder={t('history.search')}
                 value={q} onChange={(e) => setQ(e.target.value)} aria-label={t('history.search')} />
        </div>
      </div>

      {totals && (
        <div className="trip-totals">
          <div><small>{t('history.trips')}</small><b className="mono">{totals.trips}</b></div>
          <div><small>{t('history.reroutedCount')}</small><b className="mono">{totals.rerouted}</b></div>
          <div><small>{t('trip.timeSaved')}</small><b className="mono">{minutesLabel(t, totals.saved)}</b></div>
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
              {q.trim() ? t('history.noMatching') : t('history.noTrips')}
            </strong>
            <span style={{ fontSize: 12 }}>
              {q.trim()
                ? t('history.noMatchingHint')
                : <>{t('trip.empty')} <Link to="/user/dashboard">{t('history.goToDashboard')}</Link></>}
            </span>
          </div>
        </div>
      ) : (
        <div className="trip-history-list">
          {shown.map((row, i) => (
            <TripCard key={row.id} trip={row} index={i} t={t} language={language} />
          ))}
        </div>
      )}
    </>
  )
}
