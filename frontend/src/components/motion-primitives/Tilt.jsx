// Ported from motion-primitives — mouse-follow 3D tilt. No Tailwind classes
// used, so this one needed no changes beyond dropping TypeScript types.
import { useRef } from 'react'
import { motion, useMotionTemplate, useMotionValue, useSpring, useTransform } from 'framer-motion'

export function Tilt({ children, className, style, rotationFactor = 12, isReverse = false, springOptions }) {
  const ref = useRef(null)

  const x = useMotionValue(0)
  const y = useMotionValue(0)

  const xSpring = useSpring(x, springOptions)
  const ySpring = useSpring(y, springOptions)

  const rotateX = useTransform(
    ySpring,
    [-0.5, 0.5],
    isReverse ? [rotationFactor, -rotationFactor] : [-rotationFactor, rotationFactor]
  )
  const rotateY = useTransform(
    xSpring,
    [-0.5, 0.5],
    isReverse ? [-rotationFactor, rotationFactor] : [rotationFactor, -rotationFactor]
  )

  const transform = useMotionTemplate`perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`

  const handleMouseMove = (e) => {
    if (!ref.current) return
    const rect = ref.current.getBoundingClientRect()
    x.set((e.clientX - rect.left) / rect.width - 0.5)
    y.set((e.clientY - rect.top) / rect.height - 0.5)
  }

  const handleMouseLeave = () => {
    x.set(0)
    y.set(0)
  }

  return (
    <motion.div
      ref={ref}
      className={className}
      style={{ transformStyle: 'preserve-3d', ...style, transform }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      {children}
    </motion.div>
  )
}
