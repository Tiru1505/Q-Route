import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, History as HistoryIcon, Search } from 'lucide-react'
import { CardSkeleton } from '../components/LoadingScreen'
import { getRouteHistory } from '../services/api'
import { TRAFFIC_COLORS, TRAFFIC_LABELS } from '../data/mockData'
import { useApp } from '../store/AppContext'

const STATUS_BADGE = {
  completed: 'badge-green',
  rerouted: 'badge-blue',
  cancelled: 'badge-grey',
}

export default function History() {
  const { user } = useApp()
  const [rows, setRows] = useState(null)
  const [q, setQ] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    let cancelled = false
    // Scoped to the signed-in user. Without this every visitor saw every other
    // visitor's trips, because the backend filtered on a user_id the frontend
    // never sent.
    setRows(null)
    getRouteHistory(user?.email || null).then((d) => !cancelled && setRows(d))
    return () => { cancelled = true }
  }, [user?.email])

  const filtered = useMemo(() => {
    if (!rows) return null
    const t = q.trim().toLowerCase()
    if (!t) return rows
    return rows.filter(
      (r) =>
        r.start.toLowerCase().includes(t) ||
        r.end.toLowerCase().includes(t) ||
        r.algorithm.toLowerCase().includes(t)
    )
  }, [rows, q])

  return (
    <>
      <div className="row-between page-head">
        <div>
          <h1>Route History</h1>
          <p>Previously optimized routes and their outcomes.</p>
        </div>
        <div style={{ position: 'relative', width: 240, maxWidth: '45vw' }}>
          <Search
            size={13}
            style={{
              position: 'absolute', left: 11, top: '50%',
              transform: 'translateY(-50%)', color: 'var(--text-faint)',
            }}
          />
          <input
            className="input"
            style={{ paddingLeft: 31 }}
            placeholder="Search routes…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
      </div>

      <div className="card">
        {!filtered ? (
          <CardSkeleton height={300} />
        ) : filtered.length === 0 ? (
          <div className="empty">
            <HistoryIcon size={28} />
            {/* An empty list now means one of two different things, and
                blaming the search term when the user simply has no trips yet
                sends them looking for a fault that is not there. */}
            <strong style={{ fontSize: 13, color: 'var(--text-dim)' }}>
              {q.trim() ? 'No matching routes' : 'No routes yet'}
            </strong>
            <span style={{ fontSize: 12 }}>
              {q.trim()
                ? 'Try a different search term.'
                : `Routes you optimise are saved here${user?.email ? ` for ${user.email}` : ''}.`}
            </span>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Start</th>
                  <th></th>
                  <th>Destination</th>
                  <th>Algorithm</th>
                  <th>Distance</th>
                  <th>ETA</th>
                  <th>Traffic</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r, i) => (
                  <motion.tr
                    key={r.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.24, delay: i * 0.04 }}
                  >
                    <td className="mono" style={{ color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
                      {r.date}
                    </td>
                    <td>{r.start}</td>
                    <td style={{ color: 'var(--text-faint)' }}><ArrowRight size={13} /></td>
                    <td>{r.end}</td>
                    <td>
                      <span className={`badge ${r.algorithm === 'QPSO' ? 'badge-quantum' : 'badge-grey'}`}>
                        {r.algorithm}
                      </span>
                    </td>
                    <td className="mono">{r.distanceKm} km</td>
                    <td className="mono">{r.etaMin} min</td>
                    <td>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                        <span className="dot" style={{ background: TRAFFIC_COLORS[r.traffic] }} />
                        {TRAFFIC_LABELS[r.traffic]}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${STATUS_BADGE[r.status]}`}>{r.status}</span>
                    </td>
                    <td>
                      <button
                        className="btn btn-sm"
                        onClick={() => navigate('/')}
                        title="Open in the dashboard planner"
                      >
                        Open
                      </button>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
