import { useEffect, useState } from 'react'
import { Bell, KeyRound, LogOut, Moon, Navigation2, UserRound } from 'lucide-react'
import LanguagePicker from '../../components/LanguagePicker'
import { labelFor } from '../../i18n/labels'
import { useApp } from '../../store/AppContext'
import * as api from '../../services/api'
import { OPTIMIZATION_MODES } from '../../data/mockData'

/**
 * A driver's settings — only ones the app actually applies.
 *
 * Saved on the server with the account (not just this browser):
 *   name, default vehicle, default route preference, and whether the robot
 *   opens itself when a route alert arrives.
 * Password change goes to the server too, for accounts that have one.
 * Theme is a per-browser choice and stays here.
 *
 * The admin Settings page had toll, highway and sensitivity switches that no
 * part of the system reads; they are not offered here.
 */

function Toggle({ on, onChange, label, hint, disabled }) {
  return (
    <div className="row-between" style={{ padding: '9px 0' }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13 }}>{label}</div>
        {hint && <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>{hint}</div>}
      </div>
      <button className="toggle" data-on={on} onClick={() => onChange(!on)} role="switch"
              aria-checked={on} aria-label={label} disabled={disabled} type="button">
        <span />
      </button>
    </div>
  )
}

function Status({ state }) {
  if (!state) return null
  return (
    <p className={`settings-status ${state.ok ? 'is-ok' : 'is-error'}`} role="status">{state.text}</p>
  )
}

export default function UserSettings() {
  const { user, updateUser, theme, setTheme, signOut, setVehicle, setMode, t } = useApp()
  const prefs = user?.preferences || {}
  const offline = !!user?.offline
  const hasPassword = user?.providers?.includes('password')

  const [name, setName] = useState(user?.name || '')
  const [profileState, setProfileState] = useState(null)
  const [vehicles, setVehicles] = useState([])
  const [prefState, setPrefState] = useState(null)
  const [pw, setPw] = useState({ current: '', next: '', again: '' })
  const [pwState, setPwState] = useState(null)
  const [busy, setBusy] = useState(null)

  useEffect(() => {
    api.getVehicles().then((d) => setVehicles(d.vehicles || [])).catch(() => setVehicles([]))
  }, [])

  const saveName = async (e) => {
    e.preventDefault()
    if (!name.trim()) { setProfileState({ ok: false, text: t('userSettings.nameEmpty') }); return }
    setBusy('name')
    try {
      const { user: account } = await api.updateMe({ name: name.trim() })
      updateUser(account)
      setProfileState({ ok: true, text: t('settings.saved') })
    } catch (err) {
      setProfileState({ ok: false, text: err.message })
    } finally {
      setBusy(null)
    }
  }

  const savePreference = async (key, value) => {
    setBusy(key)
    setPrefState(null)
    try {
      const { user: account } = await api.updateMe({ preferences: { [key]: value } })
      updateUser(account)
      // The planner follows at once, not only at the next sign-in.
      if (key === 'vehicle') setVehicle(value)
      if (key === 'mode') setMode(value)
      setPrefState({ ok: true, text: t('settings.savedToAccount') })
    } catch (err) {
      setPrefState({ ok: false, text: err.message })
    } finally {
      setBusy(null)
    }
  }

  const savePassword = async (e) => {
    e.preventDefault()
    if (pw.next.length < 8) { setPwState({ ok: false, text: t('userSettings.passwordShort') }); return }
    if (pw.next !== pw.again) { setPwState({ ok: false, text: t('userSettings.passwordsDiffer') }); return }
    setBusy('password')
    try {
      await api.changePassword({ currentPassword: pw.current, newPassword: pw.next })
      setPw({ current: '', next: '', again: '' })
      setPwState({ ok: true, text: t('userSettings.passwordChanged') })
    } catch (err) {
      setPwState({ ok: false, text: err.message })
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>{t('settings.title')}</h1>
        <p>{offline ? t('userSettings.subtitleOffline') : t('userSettings.subtitleAccount')}</p>
      </div>

      <div className="grid grid-2">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <form className="card" onSubmit={saveName}>
            <div className="card-title"><UserRound size={13} /> {t('userSettings.profile')}</div>
            <div className="field">
              <label htmlFor="profile-name">{t('userSettings.name')}</label>
              <input id="profile-name" className="input" value={name} maxLength={80}
                     onChange={(e) => setName(e.target.value)} disabled={offline} />
            </div>
            <div className="field">
              <label htmlFor="profile-email">{t('userSettings.email')}</label>
              <input id="profile-email" className="input" value={user?.email || ''} readOnly />
              <p className="settings-hint">
                {user?.provider === 'google'
                  ? t('userSettings.emailHintGoogle')
                  : t('userSettings.emailHint')}
              </p>
            </div>
            <button className="btn btn-primary btn-sm" type="submit"
                    disabled={offline || busy === 'name' || name.trim() === user?.name}>
              {t('userSettings.saveName')}
            </button>
            <Status state={profileState} />
          </form>

          <form className="card" onSubmit={savePassword}>
            <div className="card-title"><KeyRound size={13} /> {t('userSettings.password')}</div>
            {hasPassword ? (
              <>
                <div className="field">
                  <label htmlFor="pw-current">{t('userSettings.currentPassword')}</label>
                  <input id="pw-current" type="password" className="input" autoComplete="current-password"
                         value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} />
                </div>
                <div className="field">
                  <label htmlFor="pw-next">{t('userSettings.newPassword')}</label>
                  <input id="pw-next" type="password" className="input" autoComplete="new-password"
                         value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} />
                </div>
                <div className="field">
                  <label htmlFor="pw-again">{t('userSettings.newPasswordAgain')}</label>
                  <input id="pw-again" type="password" className="input" autoComplete="new-password"
                         value={pw.again} onChange={(e) => setPw({ ...pw, again: e.target.value })} />
                </div>
                <button className="btn btn-sm" type="submit"
                        disabled={busy === 'password' || !pw.current || !pw.next}>
                  {t('userSettings.changePassword')}
                </button>
                <Status state={pwState} />
              </>
            ) : (
              <p className="settings-hint">
                {offline
                  ? t('userSettings.offlineNoPassword')
                  : user?.providers?.includes('google')
                    ? t('userSettings.googleNoPassword')
                    : t('userSettings.noPassword')}
              </p>
            )}
          </form>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <LanguagePicker />

          <div className="card">
            <div className="card-title"><Navigation2 size={13} /> {t('userSettings.routePreferences')}</div>
            <div className="field">
              <label htmlFor="pref-vehicle">{t('userSettings.defaultVehicle')}</label>
              <select id="pref-vehicle" className="select" value={prefs.vehicle || 'car'}
                      disabled={offline || busy === 'vehicle' || !vehicles.length}
                      onChange={(e) => savePreference('vehicle', e.target.value)}>
                {(vehicles.length ? vehicles : [{ id: prefs.vehicle || 'car', label: 'Car' }]).map((v) => (
                  <option key={v.id} value={v.id}>{labelFor(t, 'vehicle', v.id, v.label)}</option>
                ))}
              </select>
              <p className="settings-hint">{t('userSettings.vehicleHint')}</p>
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <label>{t('userSettings.defaultRoutePreference')}</label>
              <div className="segmented route-segmented">
                {OPTIMIZATION_MODES.map((m) => (
                  <button key={m.id} type="button" data-active={(prefs.mode || 'balanced') === m.id}
                          disabled={offline || busy === 'mode'}
                          onClick={() => savePreference('mode', m.id)}>
                    {labelFor(t, 'mode', m.id, m.name)}
                  </button>
                ))}
              </div>
            </div>
            <Status state={prefState} />
          </div>

          <div className="card">
            <div className="card-title"><Bell size={13} /> {t('adminSettings.notifications')}</div>
            <Toggle
              label={t('userSettings.autoOpen')}
              hint={t('userSettings.autoOpenHint')}
              on={prefs.autoOpenAlerts !== false}
              disabled={offline || busy === 'autoOpenAlerts'}
              onChange={(v) => savePreference('autoOpenAlerts', v)}
            />
          </div>

          <div className="card">
            <div className="card-title"><Moon size={13} /> {t('settings.appearance')}</div>
            <Toggle label={t('settings.darkMode')} hint={t('settings.darkHint')}
                    on={theme === 'dark'} onChange={(v) => setTheme(v ? 'dark' : 'light')} />
          </div>

          <div className="card">
            <div className="card-title"><LogOut size={13} /> {t('adminSettings.session')}</div>
            <p style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 11 }}>
              {t('userSettings.signedInAs')} <strong>{user?.email}</strong>
            </p>
            <button className="btn btn-sm" type="button" onClick={() => signOut()}>
              <LogOut size={13} /> {t('nav.logout')}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
