import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Activity } from 'lucide-react'

const SERIES = [
  { key: 'QPSO', color: '#E83E8C', width: 2.5 },
  { key: 'PSO', color: '#FF6B35', width: 2.0 },
  { key: 'GA', color: '#FFB347', width: 2.0 },
]

export default function ConvergenceChart({ data = [], summary = {}, height = 300 }) {
  return (
    <div className="card chart-card">
      <div className="row-between" style={{ marginBottom: 12 }}>
        <div className="card-title" style={{ margin: 0 }}>
          <Activity size={14} />
          <span>Convergence — Iteration vs Fitness</span>
        </div>
        <span style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>Lower objective is better</span>
      </div>

      <div style={{ width: '100%', height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, left: -14, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="iteration"
              axisLine={false}
              tickLine={false}
              tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
              label={{ value: 'Iteration', position: 'insideBottom', offset: -2, fill: 'var(--text-dim)', fontSize: 11 }}
            />
            <YAxis
              domain={['auto', 'auto']}
              axisLine={false}
              tickLine={false}
              tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--surface-elevated)',
                border: '1px solid var(--border-color)',
                borderRadius: 8,
                fontSize: 12,
                color: 'var(--text-primary)',
                boxShadow: '0 8px 24px rgba(0, 0, 0, 0.65)',
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11.5, color: 'var(--text-dim)' }} />
            {SERIES.map((s, i) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                stroke={s.color}
                strokeWidth={s.width}
                dot={false}
                isAnimationActive
                animationDuration={900}
                animationBegin={i * 150}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {Object.keys(summary).length > 0 && (
        <div className="grid grid-3" style={{ marginTop: 14, gap: 10 }}>
          {SERIES.map((s) => {
            const d = summary[s.key]
            if (!d) return null
            return (
              <div
                key={s.key}
                style={{
                  padding: 12,
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--panel-hover)',
                  border: '1px solid var(--border)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
                  <span className="dot" style={{ background: s.color }} />
                  <strong style={{ fontSize: 12.5, color: 'var(--text)' }}>{s.key}</strong>
                </div>
                <div className="row-between" style={{ fontSize: 11.5, color: 'var(--text-dim)', marginBottom: 3 }}>
                  <span>Iterations</span>
                  <span className="mono" style={{ color: 'var(--text)', fontWeight: 600 }}>{d.iterations}</span>
                </div>
                <div className="row-between" style={{ fontSize: 11.5, color: 'var(--text-dim)', marginBottom: 3 }}>
                  <span>Best fitness</span>
                  <span className="mono" style={{ color: 'var(--low)', fontWeight: 600 }}>{d.bestFitness}</span>
                </div>
                <div className="row-between" style={{ fontSize: 11.5, color: 'var(--text-dim)', marginBottom: 3 }}>
                  <span>Execution</span>
                  <span className="mono" style={{ color: 'var(--text)' }}>{d.executionMs} ms</span>
                </div>
                <div className="row-between" style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>
                  <span>Best found at</span>
                  <span className="mono" style={{ color: 'var(--text)' }}>
                    {d.convergedAt === null || d.convergedAt === undefined
                      ? '—'
                      : `iter ${Number(d.convergedAt).toFixed(1)}`}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
