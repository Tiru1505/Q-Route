import { AnimatePresence, motion } from 'framer-motion'
import { ArrowRight, Loader2, Navigation, TriangleAlert } from 'lucide-react'

/**
 * Three states:
 *   detecting  — congestion spike found, nothing computed yet
 *   rerouting  — optimizer re-running
 *   result     — old vs new comparison with the switch action
 */
export default function ReroutingPanel({ state, result, onReroute, onAccept }) {
  // NOTE: deliberately not mode="wait". The demo drives
  // detecting → rerouting → result faster than the exit animations complete,
  // and "wait" deadlocks on the queued exit, leaving the panel blank.
  return (
    <AnimatePresence>
      {state === 'detecting' && (
        <motion.div
          key="detecting"
          className="card"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          style={{ borderColor: 'var(--border)' }}
        >
          <div className="alert-head" style={{ marginBottom: 8 }}>
            <motion.span
              style={{
                width: 30, height: 30, borderRadius: 8, flexShrink: 0,
                display: 'grid', placeItems: 'center',
                background: '#FDEEEE', color: 'var(--severe)',
              }}
              animate={{ scale: [1, 1.08, 1] }}
              transition={{ duration: 1.2, repeat: Infinity }}
            >
              <TriangleAlert size={15} />
            </motion.span>
            <div>
              <h4 style={{ fontSize: 13, fontWeight: 600 }}>Congestion detected</h4>
              <p style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>
                Congestion on your current route has increased sharply.
              </p>
            </div>
          </div>
          <button className="btn btn-primary btn-block btn-sm" onClick={onReroute}>
            <Navigation size={13} /> Recalculate Route
          </button>
        </motion.div>
      )}

      {state === 'rerouting' && (
        <motion.div
          key="rerouting"
          className="card"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          style={{ borderColor: 'var(--brand)' }}
        >
          <div
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              justifyContent: 'center', padding: '14px 0',
            }}
          >
            <motion.span
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              style={{ display: 'grid', placeItems: 'center', color: 'var(--brand)' }}
            >
              <Loader2 size={17} />
            </motion.span>
            <span style={{ fontSize: 13, color: 'var(--text-dim)', fontWeight: 500 }}>
              Recalculating optimal route…
            </span>
          </div>
        </motion.div>
      )}

      {state === 'result' && result && (
        <motion.div
          key="result"
          className="card"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.34 }}
          style={{ borderColor: 'var(--border)' }}
        >
          <div className="card-title" style={{ color: 'var(--brand)' }}>
            <Navigation size={13} style={{ color: 'var(--brand)' }} />
            New Route Found
          </div>

          <div className="reroute-compare">
            <div className="reroute-side reroute-old">
              <small>Previous ETA</small>
              <b className="mono">{result.previousEtaMin}m</b>
            </div>
            <ArrowRight size={17} style={{ color: 'var(--text-dim)' }} />
            <div className="reroute-side reroute-new">
              <small>New ETA</small>
              <b className="mono" style={{ color: 'var(--low)' }}>{result.newEtaMin}m</b>
            </div>
          </div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            style={{
              textAlign: 'center', marginTop: 11, padding: '9px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--brand-light)', border: '1px solid #CCE2D6',
            }}
          >
            <span style={{ fontSize: 12 }}>
              Time saved:{' '}
              <strong style={{ color: 'var(--low)', fontSize: 15 }}>
                {result.timeSavedMin} min
              </strong>
            </span>
          </motion.div>

          <p style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 9 }}>
            New route via {result.newRoute.via}
          </p>

          {onAccept && (
            <button
              className="btn btn-primary btn-block"
              style={{ marginTop: 11 }}
              onClick={onAccept}
            >
              Reroute Now
            </button>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  )
}
