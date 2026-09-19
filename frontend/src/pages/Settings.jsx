import { Bell, Map, Moon, RotateCcw, Sliders, Zap } from 'lucide-react'
import LanguagePicker from '../components/LanguagePicker'
import { useApp } from '../store/AppContext'
import { ALGORITHMS } from '../data/mockData'

function Toggle({ on, onChange, label, hint }) {
  return (
    <div className="row-between" style={{ padding: '9px 0' }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13 }}>{label}</div>
        {hint && <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>{hint}</div>}
      </div>
      <button
        className="toggle"
        data-on={on}
        onClick={() => onChange(!on)}
        role="switch"
        aria-checked={on}
        aria-label={label}
      >
        <span />
      </button>
    </div>
  )
}

export default function Settings() {
  const { theme, setTheme, settings, setSettings, resetScenario, t } = useApp()
  const set = (k, v) => setSettings((s) => ({ ...s, [k]: v }))

  return (
    <>
      <div className="page-head">
        <h1>{t('settings.title')}</h1>
        <p>{t('adminSettings.subtitle')}</p>
      </div>

      <div className="grid grid-2">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <LanguagePicker />

          <div className="card">
            <div className="card-title">
              <Moon size={13} />
              {t('settings.appearance')}
            </div>
            <Toggle
              label={t('settings.darkMode')}
              hint={t('adminSettings.darkHint')}
              on={theme === 'dark'}
              onChange={(v) => setTheme(v ? 'dark' : 'light')}
            />
            <div className="field" style={{ marginTop: 8 }}>
              <label htmlFor="mapstyle">{t('adminSettings.mapStyle')}</label>
              <select
                id="mapstyle"
                className="select"
                value={settings.mapStyle}
                onChange={(e) => set('mapStyle', e.target.value)}
              >
                <option value="standard">OpenStreetMap Standard</option>
                <option value="humanitarian">Humanitarian OSM</option>
              </select>
            </div>
          </div>

          <div className="card">
            <div className="card-title">
              <Zap size={13} />
              {t('adminSettings.optimization')}
            </div>
            <div className="field">
              <label htmlFor="prefalgo">{t('adminSettings.preferredAlgorithm')}</label>
              <select
                id="prefalgo"
                className="select"
                value={settings.preferredAlgorithm}
                onChange={(e) => set('preferredAlgorithm', e.target.value)}
              >
                {ALGORITHMS.map((a) => (
                  <option key={a.id} value={a.id}>{a.full}</option>
                ))}
              </select>
            </div>
            <Toggle
              label={t('adminSettings.avoidTolls')}
              on={settings.avoidTolls}
              onChange={(v) => set('avoidTolls', v)}
            />
            <Toggle
              label={t('adminSettings.avoidHighways')}
              on={settings.avoidHighways}
              onChange={(v) => set('avoidHighways', v)}
            />
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="card">
            <div className="card-title">
              <Sliders size={13} />
              {t('adminSettings.sensitivity')}
            </div>

            <div className="field">
              <div className="row-between" style={{ marginBottom: 7 }}>
                <label style={{ margin: 0 }}>{t('adminSettings.congestionSensitivity')}</label>
                <span className="mono" style={{ fontSize: 12, color: 'var(--brand)', fontWeight: 600 }}>
                  {settings.congestionSensitivity}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={settings.congestionSensitivity}
                onChange={(e) => set('congestionSensitivity', Number(e.target.value))}
              />
              <p style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 6 }}>
                {t('adminSettings.congestionHint')}
              </p>
            </div>

            <div className="field" style={{ marginBottom: 0 }}>
              <div className="row-between" style={{ marginBottom: 7 }}>
                <label style={{ margin: 0 }}>{t('adminSettings.alertThreshold')}</label>
                <span className="mono" style={{ fontSize: 12, color: 'var(--brand)', fontWeight: 600 }}>
                  {settings.alertThresholdMin} min
                </span>
              </div>
              <input
                type="range"
                min="1"
                max="20"
                value={settings.alertThresholdMin}
                onChange={(e) => set('alertThresholdMin', Number(e.target.value))}
              />
              <p style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 6 }}>
                {t('adminSettings.alertHint')}
              </p>
            </div>
          </div>

          <div className="card">
            <div className="card-title">
              <Bell size={13} />
              {t('adminSettings.notifications')}
            </div>
            <Toggle
              label={t('adminSettings.predictiveAlerts')}
              hint={t('adminSettings.predictiveHint')}
              on={settings.notifyPredictive}
              onChange={(v) => set('notifyPredictive', v)}
            />
            <Toggle
              label={t('adminSettings.incidentAlerts')}
              hint={t('adminSettings.incidentHint')}
              on={settings.notifyIncidents}
              onChange={(v) => set('notifyIncidents', v)}
            />
            <Toggle
              label={t('adminSettings.routeChange')}
              hint={t('adminSettings.routeChangeHint')}
              on={settings.notifyReroute}
              onChange={(v) => set('notifyReroute', v)}
            />
          </div>

          <div className="card">
            <div className="card-title">
              <Map size={13} />
              {t('adminSettings.session')}
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 11 }}>
              {t('adminSettings.sessionHint')}
            </p>
            <button className="btn btn-sm" onClick={resetScenario}>
              <RotateCcw size={13} /> {t('adminSettings.resetScenario')}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
