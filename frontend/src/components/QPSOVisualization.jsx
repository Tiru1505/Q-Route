import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Atom } from 'lucide-react'

const PARTICLES = 22
const MS_PER_ITERATION = 90

/**
 * The swarm, replaying the optimiser's actual run.
 *
 * WHAT CHANGED AND WHY
 * --------------------
 * This used to animate on a wall clock and print `iterations={48}
 * bestFitness={0.418}` — literals hardcoded at the call site. It carried a
 * footnote admitting the numbers were demo values, which was honest but left
 * the dashboard's most eye-catching panel saying nothing about the run the
 * user had just waited fourteen seconds for.
 *
 * The optimiser was already producing a convergence history; the route
 * response simply dropped it. It now arrives, and this replays it: the swarm
 * contracts in step with the real fitness curve, and every figure below is
 * read from that curve.
 *
 * WHAT "CONVERGENCE %" MEANS HERE
 * -------------------------------
 * The share of the run's total improvement achieved by the current iteration:
 *
 *     (first − current) / (first − best)
 *
 * It reaches 100% when the best-known fitness is reached, and it is defined
 * only because we have both endpoints of a finished run. It is NOT a claim
 * about distance to the true optimum — the optimiser cannot know that, and
 * the benchmark page is where that comparison belongs.
 *
 * WHEN THERE IS NO RUN
 * --------------------
 * It says so. A swarm animating over invented numbers next to a real map is
 * the kind of thing that reads as live output to anyone watching a demo.
 */

function stats(curve) {
  if (!curve || curve.length === 0) return null

  const first = curve[0]
  const best = Math.min(...curve)
  // The first iteration that reached the best value — where the search
  // effectively finished, as opposed to where it was told to stop.
  const convergedAt = curve.findIndex((v) => v <= best)
  const span = first - best

  return {
    iterations: curve.length,
    first,
    best,
    convergedAt,
    span,
    // A deterministic algorithm returns one value and never iterates. Saying
    // "converged in 1 iteration" of Dijkstra would misrepresent what it does.
    iterative: curve.length > 1,
    improved: span > 1e-9,
  }
}

export default function QPSOVisualization({
  active = false,
  convergence = null,
  algorithm = 'QPSO',
  runtimeMs = null,
}) {
  const [step, setStep] = useState(0)
  const raf = useRef()

  const curve = Array.isArray(convergence) ? convergence : null
  const s = useMemo(() => stats(curve), [curve])
  // Shouted in the heading, spoken in the sentence.
  const name = algorithm.toUpperCase()
  const spoken = name.charAt(0) + name.slice(1).toLowerCase()

  const seeds = useMemo(
    () =>
      Array.from({ length: PARTICLES }, (_, i) => ({
        angle: (i / PARTICLES) * Math.PI * 2 + Math.random() * 0.6,
        radius: 30 + Math.random() * 34,
        speed: 0.5 + Math.random() * 0.9,
        phase: Math.random() * Math.PI * 2,
      })),
    [],
  )

  // Walk the real curve. When the run is over the swarm rests at its final
  // state rather than looping, because the run genuinely ended.
  useEffect(() => {
    if (!s) { setStep(0); return undefined }
    if (!active) { setStep(s.iterations - 1); return undefined }

    let start
    const loop = (now) => {
      if (!start) start = now
      const i = Math.floor((now - start) / MS_PER_ITERATION)
      setStep(Math.min(i, s.iterations - 1))
      if (i < s.iterations - 1) raf.current = requestAnimationFrame(loop)
    }
    raf.current = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf.current)
  }, [active, s])

  // Progress through the run's own improvement. A run that never improved has
  // no progress to show, so the swarm stays dispersed rather than pretending.
  const current = s ? curve[Math.min(step, s.iterations - 1)] : null
  const progress = s && s.improved
    ? Math.min(Math.max((s.first - current) / s.span, 0), 1)
    : 0
  const spread = s ? Math.max(0.12, 1 - progress) : 1
  const t = step * 0.12

  return (
    <div className="card">
      <div className="card-title quantum">
        <Atom size={13} />
        {name} Optimization
      </div>

      <div className="qpso-canvas">
        {seeds.map((sd, i) => {
          const wobble = Math.sin(t * sd.speed * 2 + sd.phase) * 6
          const r = (sd.radius + wobble) * spread
          const x = 50 + (r * Math.cos(sd.angle + t * 0.35 * sd.speed)) / 2.4
          const y = 50 + (r * Math.sin(sd.angle + t * 0.35 * sd.speed)) / 1.5
          return (
            <motion.span
              key={i}
              className="qpso-particle"
              animate={{ opacity: s ? [0.45, 1, 0.45] : 0.28 }}
              transition={{ duration: 1.6, repeat: Infinity, delay: i * 0.04 }}
              style={{
                left: `${x}%`,
                top: `${y}%`,
                background: i % 5 === 0 ? 'var(--quantum)' : 'var(--cyan)',
                boxShadow: `0 0 8px ${i % 5 === 0 ? 'var(--quantum)' : 'var(--cyan)'}`,
              }}
            />
          )
        })}

        <motion.span
          className="qpso-target"
          animate={{ scale: s && active ? [1, 1.35, 1] : 1 }}
          transition={{ duration: 1.4, repeat: Infinity }}
        />
      </div>

      {!s ? (
        <>
          <div className="qpso-stats">
            <div className="qpso-stat"><b className="mono">—</b><span>Iterations</span></div>
            <div className="qpso-stat"><b className="mono">—</b><span>Best fitness</span></div>
            <div className="qpso-stat"><b className="mono">—</b><span>Convergence</span></div>
          </div>
          <p className="qpso-note">
            No optimisation has run yet. Optimise a route and this replays the
            search that produced it.
          </p>
        </>
      ) : (
        <>
          <div className="qpso-stats">
            <div className="qpso-stat">
              <b className="mono">{s.iterations}</b>
              <span>Iterations</span>
            </div>
            <div className="qpso-stat">
              <b className="mono" style={{ color: 'var(--low)' }}>
                {current.toFixed(3)}
              </b>
              <span>Best fitness</span>
            </div>
            <div className="qpso-stat">
              <b className="mono" style={{ color: 'var(--quantum)' }}>
                {s.improved ? `${Math.round(progress * 100)}%` : 'n/a'}
              </b>
              <span>Convergence</span>
            </div>
          </div>

          <p className="qpso-note">
            {!s.iterative ? (
              <>
                {spoken} is exact — it computes the answer rather than
                searching for it, so there is one value and no convergence to
                show.
              </>
            ) : !s.improved ? (
              <>
                The swarm did not improve on its starting solution across{' '}
                {s.iterations} iterations. That is a real result, shown as it
                happened.
              </>
            ) : (
              <>
                Replaying a real run: fitness fell from{' '}
                <b>{s.first.toFixed(3)}</b> to <b>{s.best.toFixed(3)}</b>,
                reaching its best at iteration <b>{s.convergedAt + 1}</b> of{' '}
                {s.iterations}
                {runtimeMs ? <> in {(runtimeMs / 1000).toFixed(1)}s</> : null}.
                Lower fitness is better.
              </>
            )}
          </p>
        </>
      )}
    </div>
  )
}
