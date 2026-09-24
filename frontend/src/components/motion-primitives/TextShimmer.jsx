// Ported from motion-primitives — animated shimmer sweep across text, for
// pending/loading states ("Calculating route…", "I checked your new route…").
import React, { useMemo } from 'react'
import { motion } from 'framer-motion'
import { cn } from '../../lib/cn'

function TextShimmerComponent({ children, as: Component = 'p', className, style, duration = 2, spread = 2 }) {
  const MotionComponent = useMemo(() => motion.create(Component), [Component])

  const dynamicSpread = useMemo(() => children.length * spread, [children, spread])

  return (
    <MotionComponent
      className={cn(
        'relative inline-block bg-[length:250%_100%,auto] bg-clip-text',
        'text-transparent [--base-color:var(--text-faint)] [--base-gradient-color:var(--text)]',
        '[background-repeat:no-repeat,padding-box] [--bg:linear-gradient(90deg,#0000_calc(50%-var(--spread)),var(--base-gradient-color),#0000_calc(50%+var(--spread)))]',
        className
      )}
      initial={{ backgroundPosition: '100% center' }}
      animate={{ backgroundPosition: '0% center' }}
      transition={{ repeat: Infinity, duration, ease: 'linear' }}
      style={{
        ...style,
        '--spread': `${dynamicSpread}px`,
        backgroundImage: `var(--bg), linear-gradient(var(--base-color), var(--base-color))`,
      }}
    >
      {children}
    </MotionComponent>
  )
}

export const TextShimmer = React.memo(TextShimmerComponent)
