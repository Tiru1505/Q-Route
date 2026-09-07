/**
 * Shared application state.
 *
 * Deliberately small: routing results, traffic, alerts, and the demo-mode
 * script. Anything a single page owns stays in that page's own useState.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import {
  DEFAULT_END, DEFAULT_START, REROUTED_ROUTE, ROUTES, TRAFFIC_SEGMENTS,
} from '../data/mockData'
import * as api from '../services/api'
import { mapOptimizeResponse } from '../services/backendAdapter'

const AppContext = createContext(null)

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used inside <AppProvider>')
  return ctx
}

const read = (key, fallback) => {
  try {
    const v = localStorage.getItem(key)
    return v === null ? fallback : JSON.parse(v)
  } catch {
    return fallback
  }
}
const write = (key, value) => {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* private mode / blocked storage — the UI still works, it just won't persist */
  }
}

export function AppProvider({ children }) {
  /* --- auth ------------------------------------------------------------
   * DEMO AUTHENTICATION ONLY.
   *
   * By default, user starts as null so that every visitor sees the Login page first.
   * Active sessions persist in sessionStorage so refreshing within the same tab works.
   */
  const [user, setUser] = useState(() => {
    try {
      // Clear legacy auto-login user from localStorage if present
      localStorage.removeItem('qro.user')
      const sess = sessionStorage.getItem('qro.session_user')
      return sess ? JSON.parse(sess) : null
    } catch {
      return null
    }
  })

  useEffect(() => {
    try {
      if (user) {
        sessionStorage.setItem('qro.session_user', JSON.stringify(user))
      } else {
        sessionStorage.removeItem('qro.session_user')
      }
    } catch {
      /* storage blocked — session just won't persist */
    }
  }, [user])

  const signIn = useCallback(async ({ email, name }) => {
    await new Promise((r) => setTimeout(r, 650))     // make the loading state real
    const handle = (email || '').split('@')[0] || 'user'
    const newUser = {
      email: email || 'guest@qro.local',
      name: name || handle.replace(/[._-]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      initials: (name || handle).slice(0, 2).toUpperCase(),
      signedInAt: new Date().toISOString(),
      guest: false,
    }
    setUser(newUser)
    try {
      sessionStorage.setItem('qro.session_user', JSON.stringify(newUser))
    } catch {}
    return true
  }, [])

  const continueAsGuest = useCallback(() => {
    const guestUser = {
      email: 'guest@qro.local',
      name: 'Guest',
      initials: 'GU',
      signedInAt: new Date().toISOString(),
      guest: true,
    }
    setUser(guestUser)
    try {
      sessionStorage.setItem('qro.session_user', JSON.stringify(guestUser))
    } catch {}
  }, [])

  const signOut = useCallback(() => {
    try {
      sessionStorage.removeItem('qro.session_user')
      localStorage.removeItem('qro.user')
    } catch {}
    setUser(null)
  }, [])

  /* --- preferences ------------------------------------------------------ */
  const [theme, setTheme] = useState(() => read('qro.theme', 'dark'))
  const [collapsed, setCollapsed] = useState(() => read('qro.sidebar', false))
  const [settings, setSettings] = useState(() =>
    read('qro.settings', {
      mapStyle: 'standard',
      preferredAlgorithm: 'qpso',
      avoidTolls: false,
      avoidHighways: false,
      congestionSensitivity: 60,
      alertThresholdMin: 5,
      notifyPredictive: true,
      notifyIncidents: true,
      notifyReroute: true,
    })
  )

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    write('qro.theme', theme)
  }, [theme])
  useEffect(() => write('qro.sidebar', collapsed), [collapsed])
  useEffect(() => write('qro.settings', settings), [settings])

  /* --- routing ---------------------------------------------------------- */
  const [start, setStart] = useState(DEFAULT_START)
  const [end, setEnd] = useState(DEFAULT_END)
  const [algorithm, setAlgorithm] = useState('qpso')
  const [mode, setMode] = useState('balanced')

  const [routes, setRoutes] = useState([])
  const [selectedRouteId, setSelectedRouteId] = useState(null)
  const [optimizing, setOptimizing] = useState(false)
  const [error, setError] = useState(null)
  // Ticks on every successful optimisation. Analytics watches it so the
  // charts re-read the server after a new route is stored, instead of
  // showing whatever was true when the page first mounted.
  const [routesVersion, setRoutesVersion] = useState(0)

  /* --- live traffic + alerts ------------------------------------------- */
  const [segments, setSegments] = useState(TRAFFIC_SEGMENTS)
  const [incidents, setIncidents] = useState([])
  const [alerts, setAlerts] = useState([])
  const [predictiveAlert, setPredictiveAlert] = useState(null)

  /* --- rerouting -------------------------------------------------------- */
  const [rerouting, setRerouting] = useState(false)
  const [rerouteResult, setRerouteResult] = useState(null)

  /* --- demo mode -------------------------------------------------------- */
  const [demoMode, setDemoMode] = useState(false)
  const [demoStep, setDemoStep] = useState(null)
  const timers = useRef([])

  const clearTimers = useCallback(() => {
    timers.current.forEach(clearTimeout)
    timers.current = []
  }, [])

  useEffect(() => () => clearTimers(), [clearTimers])

  useEffect(() => {
    let cancelled = false
    api.getTrafficData().then((d) => {
      if (cancelled) return
      setSegments(d.segments)
      setIncidents(d.incidents)
    })
    api.getAlerts().then((a) => !cancelled && setAlerts(a))
    return () => {
      cancelled = true
    }
  }, [])

  const selectedRoute = useMemo(
    () => routes.find((r) => r.id === selectedRouteId) || routes[0] || null,
    [routes, selectedRouteId]
  )

  /** Runs the optimizer. The staged animation is owned by the Dashboard; this
   *  only resolves the data and flips the loading flag. */
  const optimize = useCallback(async () => {
    // Endpoints come from a free-text search box now, so "nothing picked yet"
    // is a real state the optimizer has to refuse rather than crash on.
    if (!start || !end) {
      setError('Choose a start and a destination first.')
      return null
    }
    setOptimizing(true)
    setError(null)
    setRerouteResult(null)
    setPredictiveAlert(null)
    try {
      const res = await api.getRouteOptimization({ start, end, algorithm, mode })
      if (!res || !Array.isArray(res.routes) || !res.routes.length || !res.recommended) {
        throw new Error('The optimizer returned no usable route. Please try again.')
      }
      setRoutes(res.routes)
      setSelectedRouteId(res.recommended.id || res.routes[0].id)
      setRoutesVersion((v) => v + 1)
      return res
    } catch (err) {
      setError(err.message || 'Optimization failed.')
      return null
    } finally {
      setOptimizing(false)
    }
  }, [start, end, algorithm, mode])

  const applyAssistantActions = useCallback((actions = []) => {
    actions.forEach((action) => {
      if (action.type === 'set_start') setStart(action.payload)
      if (action.type === 'set_destination') setEnd(action.payload)
      if (action.type === 'route_result') {
        const { primary, alternatives = [] } = action.payload
        const mapped = mapOptimizeResponse(primary, alternatives, { from: start?.name, to: end?.name, mode })
        setRoutes(mapped.routes)
        setSelectedRouteId(mapped.recommended.id)
        setRoutesVersion((v) => v + 1)
      }
      if (action.type === 'alternatives') {
        const rawRoutes = action.payload.routes || []
        if (rawRoutes.length) {
          const mapped = mapOptimizeResponse(rawRoutes[0], rawRoutes.slice(1), { from: start?.name, to: end?.name, mode })
          setRoutes(mapped.routes)
          setSelectedRouteId(mapped.recommended.id)
        }
      }
    })
  }, [mode, start?.name, end?.name])

  /** Spikes congestion on the active corridor — the trigger for rerouting. */
  const injectCongestion = useCallback(() => {
    setSegments((prev) =>
      prev.map((s) =>
        s.id === 't3' || s.id === 't4'
          ? { ...s, level: 'severe', congestion: 0.94 }
          : s
      )
    )
    setPredictiveAlert({
      id: 'live-1',
      location: 'Mehdipatnam – Masab Tank',
      current: 0.62,
      predicted: 0.94,
      etaMinutes: 15,
      coords: [17.395, 78.436],
    })
  }, [])

  const runReroute = useCallback(async () => {
    setRerouting(true)
    try {
      const res = await api.reroute({ progress: 0.4, spike: true, oldRoute: selectedRoute })
      setRerouteResult(res)
      // shouldReroute === false means the current route is genuinely still the
      // best one. That is a result worth showing, not an error, and there is no
      // replacement route to swap in.
      if (res.newRoute) {
        setRoutes((prev) => [res.newRoute, ...prev.filter((r) => r.id !== res.newRoute.id)])
        setSelectedRouteId(res.newRoute.id)
      }
      return res
    } catch (err) {
      setError(err.message || 'Rerouting failed.')
      return null
    } finally {
      setRerouting(false)
    }
  }, [selectedRoute])

  const resetScenario = useCallback(() => {
    clearTimers()
    setRoutes([])
    setSelectedRouteId(null)
    setRerouteResult(null)
    setPredictiveAlert(null)
    setSegments(TRAFFIC_SEGMENTS)
    setDemoMode(false)
    setDemoStep(null)
  }, [clearTimers])

  /**
   * Deterministic demo: optimize → congestion spike → predictive alert →
   * reroute → done. Fixed timings so it plays identically every run.
   */
  const startDemo = useCallback(async () => {
    clearTimers()
    setDemoMode(true)
    setRerouteResult(null)
    setPredictiveAlert(null)
    setSegments(TRAFFIC_SEGMENTS)
    setRoutes([])

    setDemoStep('optimizing')
    const res = await api.getRouteOptimization({ start, end, algorithm: 'qpso', mode })
    setRoutes(res.routes)
    setSelectedRouteId(res.recommended.id)

    const at = (ms, fn) => timers.current.push(setTimeout(fn, ms))

    at(3600, () => {
      setDemoStep('traffic-rising')
      injectCongestion()
    })
    at(6600, () => setDemoStep('alert'))
    at(9600, async () => {
      setDemoStep('rerouting')
      setRerouting(true)
      // Wrapped because this runs inside a timer: an unhandled rejection here
      // would skip both setRerouting(false) and setDemoStep('done'), leaving
      // the demo spinning on "rerouting" with no way out. A failed reroute
      // should end the demo, not freeze it.
      try {
        const r = await api.reroute({ progress: 0.45, spike: true })
        setRerouteResult(r)
        if (r.newRoute) {
          setRoutes((prev) => [r.newRoute, ...prev.filter((x) => x.id !== r.newRoute.id)])
          setSelectedRouteId(r.newRoute.id)
        }
      } catch (err) {
        setError(err.message || 'Rerouting failed.')
      } finally {
        setRerouting(false)
        setDemoStep('done')
      }
    })
  }, [clearTimers, injectCongestion, start, mode])

  const stopDemo = useCallback(() => {
    clearTimers()
    setDemoMode(false)
    setDemoStep(null)
  }, [clearTimers])

  /** Re-read alerts from the backend. */
  const refreshAlerts = useCallback(async () => {
    try {
      setAlerts(await api.getAlerts())
    } catch {
      /* leave what is on screen — a failed refresh should not empty the list */
    }
  }, [])

  /**
   * Raise an alert deliberately.
   *
   * The alert engine only fires when traffic actually degrades past its policy
   * gates, which cannot be scheduled for a live demonstration. This asks the
   * backend for a real one and then re-reads the list, so what appears came
   * back from the server rather than being faked in the browser.
   */
  const raiseAlert = useCallback(async (scenario) => {
    try {
      await api.triggerAlert(scenario)
      await refreshAlerts()
      return true
    } catch (err) {
      setError(err.message || 'Could not raise the alert.')
      return false
    }
  }, [refreshAlerts])

  /** Clear every stored alert, so a demonstration can be replayed. */
  const wipeAlerts = useCallback(async () => {
    try {
      await api.clearAlerts()
    } catch { /* clearing is best-effort */ }
    setAlerts([])
    setPredictiveAlert(null)
  }, [])

  const dismissAlert = useCallback((id) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id))
  }, [])

  const value = {
    user, signIn, signUp: signIn, continueAsGuest, signOut,
    theme, setTheme,
    collapsed, setCollapsed,
    settings, setSettings,
    start, setStart, end, setEnd,
    algorithm, setAlgorithm, mode, setMode,
    routes, selectedRoute, selectedRouteId, setSelectedRouteId,
    optimizing, optimize, error,
      applyAssistantActions,
    routesVersion,
    segments, incidents, alerts, dismissAlert,
    refreshAlerts, raiseAlert, wipeAlerts,
    predictiveAlert, injectCongestion,
    rerouting, rerouteResult, runReroute,
    demoMode, demoStep, startDemo, stopDemo, resetScenario,
  }

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export { ROUTES, REROUTED_ROUTE }
