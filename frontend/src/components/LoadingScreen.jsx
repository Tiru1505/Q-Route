import { TextShimmer } from './motion-primitives/TextShimmer'

export default function LoadingScreen({ label = 'Loading…' }) {
  return (
    <div className="loading-screen">
      <div className="spinner" />
      <TextShimmer as="span" style={{ fontSize: 12 }} duration={1.4}>
        {label}
      </TextShimmer>
    </div>
  )
}

/** Inline placeholder for cards whose data is still resolving. */
export function CardSkeleton({ height = 120 }) {
  return <div className="skeleton" style={{ height }} />
}
