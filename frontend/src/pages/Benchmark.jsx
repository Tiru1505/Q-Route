import { useEffect, useState } from 'react'
import { AlertOctagon, FlaskConical, Info, Scaling } from 'lucide-react'
import BenchmarkTable from '../components/BenchmarkTable'
import ConvergenceChart from '../components/ConvergenceChart'
import { ScalabilityChart } from '../components/TrafficChart'
import { CardSkeleton } from '../components/LoadingScreen'
import { getBenchmark, getConvergence, getScalability } from '../services/api'

export default function Benchmark() {
  const [bench, setBench] = useState(null)
  const [conv, setConv] = useState(null)
  const [scale, setScale] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    // Fetched independently, NOT with Promise.all. The scalability sweep runs
    // brute force over every problem size and takes the best part of a minute
    // on a cold cache; bundling it meant the benchmark table — the point of
    // this page — sat behind a skeleton until the slowest call finished. Each
    // panel now appears as soon as its own data lands, and one failing does
    // not blank the others.
    getBenchmark().then((d) => !cancelled && setBench(d))
      .catch((e) => !cancelled && setError(e.message))
    getConvergence().then((d) => !cancelled && setConv(d)).catch(() => {})
    getScalability().then((d) => !cancelled && setScale(d)).catch(() => {})

    return () => { cancelled = true }
  }, [])

  if (error) {
    return (
      <div className="card" style={{ borderColor: 'rgba(239,68,68,.3)' }}>
        <div className="empty">
          <AlertOctagon size={26} style={{ color: 'var(--severe)' }} />
          <strong style={{ fontSize: 13 }}>Could not load benchmark results</strong>
          <span style={{ fontSize: 12 }}>{error}</span>
        </div>
      </div>
    )
  }

  return (
    <>
      <div className="page-head">
        <h1>Benchmark</h1>
        <p>QPSO measured against Dijkstra, PSO and GA on identical problem instances.</p>
      </div>

      {/* Benchmark Scenario Parameters Card */}
      <div className="card" style={{ marginBottom: 14, padding: '12px 16px' }}>
        <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-dim)', marginBottom: 8, letterSpacing: '0.05em' }}>
          Benchmark Scenario Parameters
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, fontSize: 12 }}>
          <div>
            <span style={{ color: 'var(--text-faint)', display: 'block', fontSize: 10 }}>ORIGIN & DESTINATION</span>
            <strong>Hitec City → Charminar</strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-faint)', display: 'block', fontSize: 10 }}>PROBLEM CLASS</span>
            <strong>6-Stop Multi-Delivery Round</strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-faint)', display: 'block', fontSize: 10 }}>EVALUATION BUDGET</span>
            <strong>4,800 Evaluations / Algorithm</strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-faint)', display: 'block', fontSize: 10 }}>TRIALS / REPETITIONS</span>
            <strong>30 Independent Runs</strong>
          </div>
        </div>
      </div>

      {bench?.isDemoData === false ? (
        <div
          className="demo-notice"
          style={{
            background: 'rgba(16,185,129,.09)',
            borderColor: 'rgba(16,185,129,.26)',
            color: 'var(--low)',
            marginBottom: 14,
          }}
        >
          <Info size={13} />
          Live engine benchmark results — {bench.problem ? ` ${bench.problem}` : ''}.
        </div>
      ) : (
        <div className="demo-notice" style={{ marginBottom: 14 }}>
          <Info size={13} />
          Demo data — these are placeholder figures, not a validated benchmark run. Replace them with real results from benchmarking/benchmark.py.
        </div>
      )}


      <div style={{ marginBottom: 14 }}>
        {bench ? <BenchmarkTable data={bench} /> : <CardSkeleton height={300} />}
      </div>

      <div style={{ marginBottom: 14 }}>
        {conv ? (
          <ConvergenceChart data={conv.chartData} summary={conv.summary} />
        ) : (
          <CardSkeleton height={340} />
        )}
      </div>

      <div className="card chart-card">
        <div className="row-between" style={{ marginBottom: 12 }}>
          <div className="card-title" style={{ margin: 0 }}>
            <Scaling size={13} />
            Scalability — Network Size vs Execution Time
          </div>
          <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>log-ish growth expected</span>
        </div>

        {scale ? (
          <>
            <ScalabilityChart data={scale.rows} />
            <div className="table-wrap" style={{ marginTop: 14 }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Nodes</th>
                    <th>Dijkstra</th>
                    <th>QPSO</th>
                    <th>PSO</th>
                    <th>GA</th>
                    <th>QPSO solution quality</th>
                  </tr>
                </thead>
                <tbody>
                  {scale.rows.map((r) => (
                    <tr key={r.nodes}>
                      <td className="mono">{r.nodes.toLocaleString()}</td>
                      <td className="mono">{r.dijkstra} ms</td>
                      <td className="mono" style={{ color: 'var(--quantum)' }}>{r.qpso} ms</td>
                      <td className="mono">{r.pso} ms</td>
                      <td className="mono">{r.ga} ms</td>
                      <td>
                        <span className={`badge ${r.qpsoQuality >= 99 ? 'badge-green' : 'badge-yellow'}`}>
                          {r.qpsoQuality}% of optimal
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 10, lineHeight: 1.5 }}>
              "Solution quality" is the metaheuristic's objective value relative to Dijkstra's
              proven optimum on the same instance — 100% means it found the optimal route.
            </p>
          </>
        ) : (
          <CardSkeleton height={280} />
        )}
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <div className="card-title">
          <FlaskConical size={13} />
          Experimental Protocol
        </div>
        <ul style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.7, paddingLeft: 18, margin: 0 }}>
          <li>All four algorithms receive the same graph, endpoints, traffic state and objective weights.</li>
          <li>Stochastic algorithms (QPSO, PSO, GA) are run for 30 independent trials; mean, standard deviation, best and worst are reported.</li>
          <li>Dijkstra is deterministic — a single run, and its objective value is the proven optimum for this problem class.</li>
          <li>Route validity is the share of trials that produced a connected, cycle-free path satisfying all constraints.</li>
          <li>Runtime excludes graph loading, which is shared across all algorithms.</li>
        </ul>
      </div>
    </>
  )
}
