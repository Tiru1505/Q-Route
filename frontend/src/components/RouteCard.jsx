import { forwardRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Clock,
  Gauge,
  MapPin,
  Route as RouteIcon,
  Check,
  ChevronDown,
  ChevronUp,
  Info,
} from 'lucide-react'
import { useCountUp } from './StatCard'
import { TRAFFIC_COLORS } from '../data/mockData'

function congestionLevel(c) {
  if (c < 0.3) return 'low'
  if (c < 0.5) return 'moderate'
  if (c < 0.7) return 'heavy'
  return 'severe'
}

/* forwardRef so AnimatePresence's popLayout mode can measure this card. */
const RouteCard = forwardRef(function RouteCard({ route, onCompareAlternatives }, ref) {
  const [detailsOpen, setDetailsOpen] = useState(false)

  const distance = useCountUp(route.distanceKm)
  const eta = useCountUp(route.etaMin)
  const cong = useCountUp(route.congestion * 100)
  const score = useCountUp(route.score)

  const level = congestionLevel(route.congestion)

  return (
    <motion.div
      ref={ref}
      className="card"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.3,
        ease: [0.22, 1, 0.36, 1],
      }}
      style={{
        borderColor: 'var(--border)',
        boxShadow: 'var(--shadow)',
      }}
    >
      {/* HEADER */}
      <div
        className="row-between"
        style={{
          marginBottom: 12,
        }}
      >
        <div
          className="card-title"
          style={{
            margin: 0,
            fontSize: 12,
            fontWeight: 700,
            color: 'var(--text)',
            letterSpacing: '0.02em',
          }}
        >
          <RouteIcon size={14} style={{ color: 'var(--route-blue)' }} />
          <span>Recommended Route</span>
        </div>

        <span
          className="badge badge-green"
          style={{
            fontSize: 10.5,
            padding: '2px 8px',
          }}
        >
          Optimal Match
        </span>
      </div>

      {route.via && (
        <div
          style={{
            fontSize: 12,
            color: 'var(--text-dim)',
            marginBottom: 14,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={`via ${route.via}`}
        >
          via {route.via}
        </div>
      )}

      {/* LARGE PROMINENT METRICS: 38 min, 18.9 km, 22% congestion */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 8,
          padding: '12px 10px',
          borderRadius: 'var(--radius-sm)',
          background: 'var(--panel-hover)',
          border: '1px solid var(--border)',
          marginBottom: 16,
          textAlign: 'center',
        }}
      >
        <div>
          <div
            style={{
              fontSize: 22,
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: 'var(--text)',
              lineHeight: 1.1,
            }}
          >
            {Math.round(eta)} <span style={{ fontSize: 13, fontWeight: 500 }}>min</span>
          </div>
          <span style={{ fontSize: 10.5, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Travel Time
          </span>
        </div>

        <div>
          <div
            style={{
              fontSize: 22,
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: 'var(--text)',
              lineHeight: 1.1,
            }}
          >
            {distance.toFixed(1)} <span style={{ fontSize: 13, fontWeight: 500 }}>km</span>
          </div>
          <span style={{ fontSize: 10.5, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Distance
          </span>
        </div>

        <div>
          <div
            style={{
              fontSize: 22,
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: TRAFFIC_COLORS[level],
              lineHeight: 1.1,
            }}
          >
            {Math.round(cong)}%
          </div>
          <span style={{ fontSize: 10.5, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Congestion
          </span>
        </div>
      </div>

      {/* WHY THIS ROUTE? */}
      <div
        style={{
          padding: '12px 14px',
          borderRadius: 'var(--radius-sm)',
          background: 'var(--surface-elevated)',
          border: '1px solid var(--border)',
          marginBottom: 16,
        }}
      >
        <div
          style={{
            fontSize: 11.5,
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            color: 'var(--text)',
            marginBottom: 8,
          }}
        >
          Why this route?
        </div>

        <ul
          style={{
            margin: 0,
            padding: 0,
            listStyle: 'none',
            fontSize: 12,
            color: 'var(--text-dim)',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}
        >
          <li style={{ display: 'flex', alignItems: 'flex-start', gap: 7 }}>
            <span style={{ color: 'var(--low)', marginTop: 1 }}>•</span>
            <span>
              {route.timeSavedMin > 0
                ? `Lower estimated travel time (${route.timeSavedMin} min faster than alternatives)`
                : 'Lower estimated travel time along primary thoroughfares'}
            </span>
          </li>
          <li style={{ display: 'flex', alignItems: 'flex-start', gap: 7 }}>
            <span style={{ color: 'var(--low)', marginTop: 1 }}>•</span>
            <span>Lower congestion along designated arterial roads</span>
          </li>
          <li style={{ display: 'flex', alignItems: 'flex-start', gap: 7 }}>
            <span style={{ color: 'var(--low)', marginTop: 1 }}>•</span>
            <span>Avoids reported incidents and critical construction zones</span>
          </li>
          <li style={{ display: 'flex', alignItems: 'flex-start', gap: 7 }}>
            <span style={{ color: 'var(--low)', marginTop: 1 }}>•</span>
            <span>Better optimization objective score ({Math.round(score)}/100)</span>
          </li>
        </ul>
      </div>

      {/* ACTION BUTTONS: View route details & Compare alternatives */}
      <div style={{ display: 'flex', gap: 8, marginBottom: detailsOpen ? 12 : 0 }}>
        <button
          className="btn btn-sm"
          style={{ flex: 1 }}
          onClick={() => setDetailsOpen((v) => !v)}
        >
          <span>View route details</span>
          {detailsOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>

        {onCompareAlternatives && (
          <button
            className="btn btn-sm"
            style={{ flex: 1 }}
            onClick={onCompareAlternatives}
          >
            Compare alternatives
          </button>
        )}
      </div>

      {/* ROUTE DETAILS DRAWER */}
      <AnimatePresence>
        {detailsOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: 'hidden' }}
          >
            <div
              style={{
                paddingTop: 10,
                borderTop: '1px solid var(--border)',
                fontSize: 11.5,
                color: 'var(--text-dim)',
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              <div className="row-between">
                <span>Algorithm:</span>
                <strong style={{ color: 'var(--text)' }}>{route.algorithm} Metaheuristic</strong>
              </div>
              <div className="row-between">
                <span>Estimated Arrival:</span>
                <strong style={{ color: 'var(--text)' }}>
                  {new Date(Date.now() + route.etaMin * 60000).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </strong>
              </div>
              <div className="row-between">
                <span>Average Corridor Speed:</span>
                <strong style={{ color: 'var(--text)' }}>
                  {route.etaMin > 0 ? (route.distanceKm / (route.etaMin / 60)).toFixed(0) : '—'} km/h
                </strong>
              </div>
              <div className="row-between">
                <span>Toll Charges:</span>
                <strong style={{ color: 'var(--low)' }}>₹0 (No tolls)</strong>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
})

export default RouteCard