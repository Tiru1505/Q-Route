// Ported from motion-primitives — a light travelling along a card's border,
// used to draw the eye to a newly arrived alert without a popup or a sound.
import { motion } from 'framer-motion'
import { cn } from '../../lib/cn'

export function BorderTrail({ className, size = 60, transition, onAnimationComplete, style }) {
  const defaultTransition = { repeat: Infinity, duration: 5, ease: 'linear' }

  return (
    <div className="pointer-events-none absolute inset-0 rounded-[inherit] border border-transparent [mask-clip:padding-box,border-box] [mask-composite:intersect] [mask-image:linear-gradient(transparent,transparent),linear-gradient(#000,#000)]">
      <motion.div
        className={cn('absolute aspect-square bg-brand', className)}
        style={{
          width: size,
          offsetPath: `rect(0 auto auto 0 round ${size}px)`,
          ...style,
        }}
        animate={{ offsetDistance: ['0%', '100%'] }}
        transition={transition || defaultTransition}
        onAnimationComplete={onAnimationComplete}
      />
    </div>
  )
}
