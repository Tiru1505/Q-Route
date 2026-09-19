import { TRAFFIC_COLORS } from '../data/mockData'
import { useApp } from '../store/AppContext'

export default function TrafficLegend({ showRoutes = true }) {
  const { t } = useApp()
  return (
    <div className="legend-card">
      <div className="legend-title">{t('legend.congestion')}</div>
      {Object.keys(TRAFFIC_COLORS).map((k) => (
        <div key={k} className="legend-row">
          <span className="legend-swatch" style={{ background: TRAFFIC_COLORS[k] }} />
          <span style={{ color: 'var(--text-dim)', fontSize: 11.5 }}>{t(`traffic.${k}`)}</span>
        </div>
      ))}

      {showRoutes && (
        <>
          <div className="legend-title" style={{ marginTop: 12 }}>{t('legend.routePaths')}</div>
          <div className="legend-row">
            <span
              className="legend-swatch"
              style={{ background: '#FF6B35', height: 4 }}
            />
            <span style={{ color: 'var(--text)', fontWeight: 500, fontSize: 11.5 }}>{t('legend.recommended')}</span>
          </div>
          <div className="legend-row">
            <span
              className="legend-swatch"
              style={{
                background: '#8A97A0',
                height: 3,
              }}
            />
            <span style={{ color: 'var(--text-dim)', fontSize: 11.5 }}>{t('legend.alternative')}</span>
          </div>
        </>
      )}
    </div>
  )
}
