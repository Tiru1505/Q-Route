import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, Loader2, ArrowRight, Circle, Activity } from 'lucide-react'

const STAGES = [
  { id: 0, label: 'Generating candidate routes' },
  { id: 1, label: 'Evaluating traffic conditions' },
  { id: 2, label: 'Calculating fitness objective' },
  { id: 3, label: 'Running optimization algorithm' },
  { id: 4, label: 'Selecting best route' },
]

const STAGE_MS = 650

export default function OptimizationAnimation({
  running,
  onComplete,
  algorithmName = 'QPSO',
}) {
  const [stage, setStage] = useState(0)
  const [iteration, setIteration] = useState(0)
  const [fitness, setFitness] = useState(0.482)

  useEffect(() => {
    if (!running) {
      setStage(0)
      setIteration(0)
      setFitness(0.482)
      return
    }

    setStage(0)
    setIteration(0)
    setFitness(0.482)

    const timers = STAGES.map((_, i) =>
      setTimeout(() => {
        setStage(i)
      }, i * STAGE_MS)
    )

    const iterationTimer = setInterval(() => {
      setIteration((prev) => {
        if (prev >= 48) return 48
        return prev + 2
      })

      setFitness((prev) => Math.max(0.418, prev - 0.003))
    }, 70)

    const doneTimer = setTimeout(() => {
      setStage(STAGES.length)
      onComplete?.()
    }, (STAGES.length + 0.5) * STAGE_MS)

    return () => {
      timers.forEach(clearTimeout)
      clearTimeout(doneTimer)
      clearInterval(iterationTimer)
    }
  }, [running, onComplete])

  const progress = Math.min(100, Math.round(((stage + 1) / STAGES.length) * 100))

  return (
    <AnimatePresence>
      {running && (
        <motion.div
          className="card"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.25 }}
          style={{
            borderColor: 'var(--brand)',
            boxShadow: 'var(--shadow-md)',
          }}
        >
          {/* HEADER */}
          <div
            className="row-between"
            style={{
              marginBottom: 14,
              paddingBottom: 10,
              borderBottom: '1px solid var(--border)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Loader2 size={16} className="spin" style={{ color: 'var(--cyan)' }} />
              <strong style={{ fontSize: 13.5, color: 'var(--text)' }}>
                {algorithmName} Optimization Running
              </strong>
            </div>

            <span
              className="badge badge-quantum"
              style={{ fontSize: 10, padding: '2px 8px' }}
            >
              {algorithmName}
            </span>
          </div>

          {/* PROFESSIONAL STAGES LIST */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            {STAGES.map((s, i) => {
              const isDone = stage > i
              const isCurrent = stage === i
              const isPending = stage < i

              return (
                <div
                  key={s.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    fontSize: 12.5,
                    color: isCurrent
                      ? 'var(--cyan)'
                      : isDone
                      ? 'var(--text)'
                      : 'var(--text-faint)',
                    fontWeight: isCurrent ? 600 : 400,
                    transition: 'color 0.18s ease',
                  }}
                >
                  <span
                    style={{
                      width: 18,
                      height: 18,
                      borderRadius: '50%',
                      display: 'grid',
                      placeItems: 'center',
                      fontSize: 11,
                      flexShrink: 0,
                      background: isDone
                        ? 'rgba(52, 211, 153, 0.12)'
                        : isCurrent
                        ? 'rgba(255, 179, 71, 0.15)'
                        : 'transparent',
                      border: isDone
                        ? '1px solid var(--low)'
                        : isCurrent
                        ? '1.5px solid var(--cyan)'
                        : '1px solid var(--border)',
                      color: isDone ? 'var(--low)' : isCurrent ? 'var(--cyan)' : 'var(--text-faint)',
                    }}
                  >
                    {isDone ? (
                      <Check size={11} strokeWidth={3} />
                    ) : isCurrent ? (
                      <ArrowRight size={11} strokeWidth={2.5} />
                    ) : (
                      <Circle size={5} fill="currentColor" stroke="none" />
                    )}
                  </span>

                  <span>
                    {s.id === 3 ? `Running ${algorithmName}` : s.label}
                  </span>
                </div>
              )
            })}
          </div>

          {/* ITERATION METRICS (if available) */}
          <div
            className="row-between mono"
            style={{
              marginTop: 14,
              paddingTop: 10,
              borderTop: '1px solid var(--border)',
              fontSize: 11,
              color: 'var(--text-dim)',
            }}
          >
            <span>Iteration: <strong style={{ color: 'var(--text)' }}>{iteration}</strong>/48</span>
            <span>Fitness: <strong style={{ color: 'var(--low)' }}>{fitness.toFixed(4)}</strong></span>
            <span>{progress}%</span>
          </div>

          {/* SUBTLE PROGRESS BAR */}
          <div className="progress-track" style={{ marginTop: 8 }}>
            <motion.div
              className="progress-fill"
              style={{
                width: `${progress}%`,
                background: 'linear-gradient(90deg, #FF6B35, #E83E8C)',
                boxShadow: '0 0 10px rgba(255, 107, 53, 0.35)',
              }}
              transition={{ duration: 0.2 }}
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}