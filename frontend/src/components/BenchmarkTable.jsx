import { motion } from 'framer-motion'
import { Info, Zap } from 'lucide-react'

const fmt = (v, d = 3) => (v === null || v === undefined ? '—' : v.toFixed(d))

/**
 * Comparison across all four algorithms.
 *
 * The "best" highlight marks the lowest objective value, whichever algorithm
 * achieves it. It is not hardcoded to QPSO — on this problem class Dijkstra is
 * provably optimal, and the table is expected to show that.
 */
export default function BenchmarkTable({ data }) {
  if (!data) return null

  const bestFitness = Math.min(...data.rows.map((r) => r.fitness))
  const fastest = Math.min(...data.rows.map((r) => r.runtimeMs))

  // The footnote below has to describe the table that is actually on screen.
  // Multi-stop runs have no Dijkstra row — it cannot order stops — so claiming
  // it is the provable optimum there would be wrong. The trial count comes
  // from the data for the same reason: it was hardcoded to 30 and the API
  // defaults to 20.
  const hasDijkstra = data.rows.some((r) => /dijkstra/i.test(r.algorithm || ''))
  const trials = data.rows.find((r) => r.trials)?.trials ?? null

  return (
    <div className="card">
      <div className="row-between" style={{ marginBottom: 12 }}>
        <div className="card-title" style={{ margin: 0 }}>
          <Info size={14} />
          Algorithm Comparison
        </div>
        <span style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>{data.problem}</span>
      </div>

      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Algorithm</th>
              <th>Distance</th>
              <th>Travel time</th>
              <th>Congestion</th>
              <th>Runtime</th>
              <th>Objective</th>
              <th>Std dev</th>
              <th>Best</th>
              <th>Worst</th>
              <th>Validity</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r, i) => {
              const isBest = r.fitness === bestFitness
              const isFastest = r.runtimeMs === fastest
              return (
                <motion.tr
                  key={r.algorithm}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.28, delay: i * 0.07 }}
                >
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                      <strong>{r.algorithm}</strong>
                      {r.algorithm === 'QPSO' && (
                        <span className="badge badge-green" style={{ padding: '1px 6px', fontSize: 10 }}>
                          Q
                        </span>
                      )}
                      {!r.deterministic && (
                        <span
                          className="badge badge-grey"
                          style={{ padding: '1px 6px', fontSize: 10 }}
                          title={`Stochastic — results averaged over ${r.trials ?? trials ?? 'multiple'} independent trials`}
                        >
                          stoch
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="mono">{r.distanceKm} km</td>
                  <td className="mono">{r.timeMin.toFixed(1)} min</td>
                  <td className="mono">{(r.congestion * 100).toFixed(1)}%</td>
                  <td className="mono" style={{ color: isFastest ? 'var(--low)' : undefined, fontWeight: isFastest ? 600 : 400 }}>
                    {r.runtimeMs} ms
                  </td>
                  <td className="mono" style={{ color: isBest ? 'var(--low)' : undefined, fontWeight: isBest ? 600 : 400 }}>
                    {fmt(r.fitness, 4)}
                  </td>
                  <td className="mono" style={{ color: 'var(--text-dim)' }}>
                    {r.deterministic ? '—' : fmt(r.fitnessStd, 4)}
                  </td>
                  <td className="mono" style={{ color: 'var(--text-dim)' }}>{fmt(r.fitnessBest, 4)}</td>
                  <td className="mono" style={{ color: 'var(--text-dim)' }}>{fmt(r.fitnessWorst, 4)}</td>
                  <td>
                    <span className={`badge ${r.validity === 100 ? 'badge-green' : 'badge-yellow'}`}>
                      {r.validity}%
                    </span>
                  </td>
                </motion.tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div
        style={{
          display: 'flex', gap: 8, alignItems: 'flex-start', marginTop: 14,
          padding: '10px 14px', borderRadius: 'var(--radius-sm)',
          background: 'var(--panel-hover)', border: '1px solid var(--border)',
        }}
      >
        <Info size={14} style={{ color: 'var(--brand)', flexShrink: 0, marginTop: 2 }} />
        <p style={{ fontSize: 11.5, color: 'var(--text-dim)', lineHeight: 1.5 }}>
          Lower objective is better.{' '}
          {hasDijkstra ? (
            <>
              On single-pair routing with additively combined weights, Dijkstra is provably
              optimal, so it is expected to attain the best objective value — the meaningful
              result is how close the metaheuristics get, and how consistently.
            </>
          ) : (
            <>
              This is multi-stop routing: Dijkstra cannot express it, because it finds a path
              between two points and has no notion of ordering stops. The comparison is
              therefore between the metaheuristics, measured against the exact optimum from
              brute force.
            </>
          )}{' '}
          {trials
            ? `Stochastic algorithms are averaged over ${trials} trials.`
            : 'Stochastic algorithms are averaged over repeated independent trials.'}
        </p>
      </div>
    </div>
  )
}
