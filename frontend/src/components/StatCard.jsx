import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { TrendingDown, TrendingUp } from 'lucide-react'

const TONES = {
  brand: 'var(--brand)',
  cyan: 'var(--cyan)',
  green: 'var(--low)',
  yellow: 'var(--moderate)',
  orange: 'var(--heavy)',
  red: 'var(--severe)',
  blue: 'var(--cyan)',
  quantum: 'var(--pink)',
}

/** Counts from 0 to `value` once, on mount. Respects reduced-motion. */
export function useCountUp(value, duration = 900) {
  const [display, setDisplay] = useState(0)
  const raf = useRef()

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setDisplay(value)
      return
    }
    const start = performance.now()
    const tick = (now) => {
      const t = Math.min((now - start) / duration, 1)
      // ease-out cubic
      setDisplay(value * (1 - Math.pow(1 - t, 3)))
      if (t < 1) raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf.current)
  }, [value, duration])

  return display
}

export default function StatCard({
  label, value, suffix = '', trend, tone = 'cyan', icon: Icon, decimals = 0, delay = 0,
}) {
  const animated = useCountUp(value)
  const color = TONES[tone] || TONES.cyan
  const up = trend > 0

  return (
    <motion.div
      className="card stat-card"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.34, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ color: tone === 'red' ? 'var(--severe)' : 'var(--text)' }}>
        {animated.toLocaleString(undefined, {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        })}
        <span style={{ fontSize: 14, color: 'var(--text-dim)', marginLeft: 2 }}>{suffix}</span>
      </div>

      {trend !== undefined && trend !== null && (
        <div className="stat-trend" style={{ color: up ? 'var(--severe)' : 'var(--low)' }}>
          {up ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
          {up ? '+' : ''}{trend}
          <span style={{ color: 'var(--text-faint)' }}>vs last hour</span>
        </div>
      )}

      {Icon && (
        <div
          className="stat-icon"
          style={{ background: `color-mix(in srgb, ${color} 14%, transparent)`, color }}
        >
          <Icon size={16} />
        </div>
      )}
    </motion.div>
  )
}
