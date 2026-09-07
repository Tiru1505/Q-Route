import { useState } from 'react'
import { motion } from 'framer-motion'
import { GitBranch, Table, List } from 'lucide-react'

export default function AlternativeRoutes({ routes, selectedId, onSelect }) {
  const [viewMode, setViewMode] = useState('list') // 'list' | 'table'

  if (!routes.length) return null

  return (
    <div className="card">
      <div className="row-between" style={{ marginBottom: 12 }}>
        <div className="card-title" style={{ margin: 0 }}>
          <GitBranch size={13} />
          All Routes ({routes.length})
        </div>

        <div className="segmented" style={{ padding: 2 }}>
          <button
            data-active={viewMode === 'list'}
            onClick={() => setViewMode('list')}
            title="List view"
            style={{ padding: '3px 8px', fontSize: 11 }}
          >
            <List size={12} /> List
          </button>
          <button
            data-active={viewMode === 'table'}
            onClick={() => setViewMode('table')}
            title="Compare table view"
            style={{ padding: '3px 8px', fontSize: 11 }}
          >
            <Table size={12} /> Compare
          </button>
        </div>
      </div>

      {viewMode === 'list' ? (
        routes.map((r, i) => (
          <motion.div
            key={r.id}
            className="alt-route"
            data-active={r.id === selectedId}
            onClick={() => onSelect(r.id)}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.28, delay: i * 0.07 }}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && onSelect(r.id)}
          >
            <span
              className="alt-swatch"
              style={{ background: r.color }}
            />
            <div className="alt-body">
              <strong>
                {r.label}
                {r.recommended && (
                  <span className="badge badge-green" style={{ marginLeft: 6, padding: '1px 6px' }}>
                    Best
                  </span>
                )}
              </strong>
              <span>{r.via}</span>
            </div>
            <div className="alt-nums">
              <div className="mono" style={{ color: 'var(--text)' }}>{r.etaMin} min</div>
              <div>{r.distanceKm} km · {Math.round(r.congestion * 100)}%</div>
            </div>
          </motion.div>
        ))
      ) : (
        <div className="table-wrap" style={{ marginTop: 4 }}>
          <table className="table" style={{ fontSize: 12 }}>
            <thead>
              <tr>
                <th style={{ textTransform: 'uppercase', fontSize: 10 }}>Metric</th>
                {routes.map((r) => (
                  <th
                    key={r.id}
                    style={{
                      cursor: 'pointer',
                      background: r.id === selectedId ? 'var(--panel-hover)' : 'transparent',
                    }}
                    onClick={() => onSelect(r.id)}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                      <span className="alt-swatch" style={{ background: r.color, width: 8, height: 8 }} />
                      {r.label}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>ETA</strong></td>
                {routes.map((r) => (
                  <td key={r.id} className="mono" style={{ fontWeight: r.id === selectedId ? 600 : 400 }}>
                    {r.etaMin} min
                  </td>
                ))}
              </tr>
              <tr>
                <td><strong>Distance</strong></td>
                {routes.map((r) => (
                  <td key={r.id} className="mono">{r.distanceKm} km</td>
                ))}
              </tr>
              <tr>
                <td><strong>Congestion</strong></td>
                {routes.map((r) => (
                  <td key={r.id} className="mono">
                    {Math.round(r.congestion * 100)}%
                  </td>
                ))}
              </tr>
              <tr>
                <td><strong>Toll</strong></td>
                {routes.map((r) => (
                  <td key={r.id} className="mono">₹0</td>
                ))}
              </tr>
              <tr>
                <td><strong>Reliability</strong></td>
                {routes.map((r) => (
                  <td key={r.id}>
                    <span className={`badge ${r.recommended ? 'badge-green' : 'badge-grey'}`}>
                      {r.recommended ? 'High' : 'Medium'}
                    </span>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

