import { Bell, Map, Moon, RotateCcw, Sliders, Zap } from 'lucide-react'
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
  const { theme, setTheme, settings, setSettings, resetScenario } = useApp()
  const set = (k, v) => setSettings((s) => ({ ...s, [k]: v }))

  return (
    <>
      <div className="page-head">
        <h1>Settings</h1>
        <p>Preferences are stored in this browser only.</p>
      </div>

      <div className="grid grid-2">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="card">
            <div className="card-title">
              <Moon size={13} />
              Appearance
            </div>
            <Toggle
              label="Dark mode"
              hint="The interface is designed dark-first."
              on={theme === 'dark'}
              onChange={(v) => setTheme(v ? 'dark' : 'light')}
            />
            <div className="field" style={{ marginTop: 8 }}>
              <label htmlFor="mapstyle">Map style</label>
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
              Optimization
            </div>
            <div className="field">
              <label htmlFor="prefalgo">Preferred algorithm</label>
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
              label="Avoid toll roads"
              on={settings.avoidTolls}
              onChange={(v) => set('avoidTolls', v)}
            />
            <Toggle
              label="Avoid highways"
              on={settings.avoidHighways}
              onChange={(v) => set('avoidHighways', v)}
            />
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="card">
            <div className="card-title">
              <Sliders size={13} />
              Sensitivity
            </div>

            <div className="field">
              <div className="row-between" style={{ marginBottom: 7 }}>
                <label style={{ margin: 0 }}>Congestion sensitivity</label>
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
                How strongly congestion is weighted relative to time and distance.
              </p>
            </div>

            <div className="field" style={{ marginBottom: 0 }}>
              <div className="row-between" style={{ marginBottom: 7 }}>
                <label style={{ margin: 0 }}>Alert threshold</label>
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
                Only alert when an alternative saves at least this much time. Higher
                values mean fewer, more meaningful alerts.
              </p>
            </div>
          </div>

          <div className="card">
            <div className="card-title">
              <Bell size={13} />
              Notifications
            </div>
            <Toggle
              label="Predictive alerts"
              hint="Forecast congestion before it happens."
              on={settings.notifyPredictive}
              onChange={(v) => set('notifyPredictive', v)}
            />
            <Toggle
              label="Incident alerts"
              hint="Accidents, closures and waterlogging."
              on={settings.notifyIncidents}
              onChange={(v) => set('notifyIncidents', v)}
            />
            <Toggle
              label="Route change suggestions"
              hint="Notify when a better route appears."
              on={settings.notifyReroute}
              onChange={(v) => set('notifyReroute', v)}
            />
          </div>

          <div className="card">
            <div className="card-title">
              <Map size={13} />
              Session
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 11 }}>
              Clear the current routes, traffic simulation and alerts.
            </p>
            <button className="btn btn-sm" onClick={resetScenario}>
              <RotateCcw size={13} /> Reset Scenario
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
