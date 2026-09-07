import { TRAFFIC_COLORS, TRAFFIC_LABELS } from '../data/mockData'

export default function TrafficLegend({ showRoutes = true }) {
  return (
    <div className="legend-card">
      <div className="legend-title">Traffic Congestion</div>
      {Object.keys(TRAFFIC_COLORS).map((k) => (
        <div key={k} className="legend-row">
          <span className="legend-swatch" style={{ background: TRAFFIC_COLORS[k] }} />
          <span style={{ color: 'var(--text-dim)', fontSize: 11.5 }}>{TRAFFIC_LABELS[k]}</span>
        </div>
      ))}

      {showRoutes && (
        <>
          <div className="legend-title" style={{ marginTop: 12 }}>Route Paths</div>
          <div className="legend-row">
            <span
              className="legend-swatch"
              style={{ background: '#FF6B35', height: 4 }}
            />
            <span style={{ color: 'var(--text)', fontWeight: 500, fontSize: 11.5 }}>Recommended</span>
          </div>
          <div className="legend-row">
            <span
              className="legend-swatch"
              style={{
                background: '#8A97A0',
                height: 3,
              }}
            />
            <span style={{ color: 'var(--text-dim)', fontSize: 11.5 }}>Alternative</span>
          </div>
        </>
      )}
    </div>
  )
}
