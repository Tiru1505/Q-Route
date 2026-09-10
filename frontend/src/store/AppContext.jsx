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

// How often the monitor looks while someone is watching for its alert, and
// how often once they are not. The backend's own default is the relaxed one.
const WATCH_TICK_S = 2
const RELAXED_TICK_S = 15
// The demo's starting traffic, restored on every run.
const DEMO_SCENARIO = 'peak_hour'
// How long the demo waits for the monitor before reporting that it stayed quiet.
const ALERT_WAIT_MS = 25_000

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
      const stored = sess ? JSON.parse(sess) : null
      // Guest sign-in has been removed. A guest session saved before that
      // would otherwise keep working for the rest of the tab's life.
      if (stored?.guest) {
        sessionStorage.removeItem('qro.session_user')
        return null
      }
      return stored
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
  // The traveller's vehicle. Remembered across visits — people rarely change
  // vehicles between trips — and read defensively, because storage can be
  // blocked or throw in private windows and previews.
  const [vehicle, setVehicleState] = useState(() => {
    try { return localStorage.getItem('qroute.vehicle') || 'car' } catch { return 'car' }
  })
  const setVehicle = useCallback((v) => {
    setVehicleState(v)
    try { localStorage.setItem('qroute.vehicle', v) } catch { /* not persisted; still applied */ }
  }, [])
  /* Which road network to route on. 'hyderabad' has every street but stops at
   * the ORR; 'india' reaches the whole country along arterial roads only, so
   * it cannot deliver to an address. Switching it clears the endpoints,
   * because a place found on one network is frequently not routable on the
   * other and a stale pin produces a confidently wrong route. */
  const [graph, setGraphState] = useState('hyderabad')

  const [routes, setRoutes] = useState([])
  const [selectedRouteId, setSelectedRouteId] = useState(null)
  const [optimizing, setOptimizing] = useState(false)
  const [error, setError] = useState(null)
  // Ticks on every successful optimisation. Analytics watches it so the
  // charts re-read the server after a new route is stored, instead of
  // showing whatever was true when the page first mounted.
  const [routesVersion, setRoutesVersion] = useState(0)
  // What the last optimisation actually did — iterations, convergence curve,
  // wall time. Kept so the dashboard can report the run rather than illustrate
  // one, and cleared with every new run so a stale curve never sits beside a
  // fresh route.
  const [lastRun, setLastRun] = useState(null)
  // The most recent detector run, wherever it happened. The Command Centre's
  // pipeline showed INPUT, YOLO and COUNTS permanently waiting because the
  // Lab's result never left the Lab's own component state — the stages were
  // right, they were simply never told.
  const [lastDetection, setLastDetection] = useState(null)

  /* --- live traffic + alerts ------------------------------------------- */
  const [segments, setSegments] = useState(TRAFFIC_SEGMENTS)
  const [incidents, setIncidents] = useState([])
  const [alerts, setAlerts] = useState([])
  // The spike, and what the SYSTEM said about it. Nothing on this side decides
  // that an alert happened: `latestAlert` is set only when the backend's
  // monitor pushes one over the notification socket. The dashboard used to
  // raise its own — two hard-coded mock segments painted red and a fixed
  // "Mehdipatnam – Masab Tank, 62% → 94% in 15 min" that nothing had computed.
  const [spikeAt, setSpikeAt] = useState(null)
  const [spiking, setSpiking] = useState(false)
  const [latestAlert, setLatestAlert] = useState(null)
  const [routeCheck, setRouteCheck] = useState(null)

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
    setLatestAlert(null)
    setRouteCheck(null)
    setSpikeAt(null)
    setLastRun(null)
    try {
      const res = await api.getRouteOptimization({
        start, end, algorithm, mode, vehicle, graph,
        // Tags the saved route so History can show this user's own trips.
        userId: user?.email || null,
      })
      if (!res || !Array.isArray(res.routes) || !res.routes.length || !res.recommended) {
        throw new Error('The optimizer returned no usable route. Please try again.')
      }
      setRoutes(res.routes)
      setSelectedRouteId(res.recommended.id || res.routes[0].id)
      setRoutesVersion((v) => v + 1)
      setLastRun(res.meta || null)
      return res
    } catch (err) {
      setError(err.message || 'Optimization failed.')
      return null
    } finally {
      setOptimizing(false)
    }
  }, [start, end, algorithm, mode, vehicle, graph, user?.email])

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

  /** Re-read the congestion overlay the map draws, from the backend. */
  const refreshTraffic = useCallback(async () => {
    try {
      const d = await api.getTrafficData()
      setSegments(d.segments)
      setIncidents(d.incidents)
    } catch { /* the map keeps its last overlay */ }
  }, [])

  /**
   * Congest the road ahead of the driver — for real, on the backend graph.
   *
   * This does not raise an alert and does not say one is coming. It changes
   * the traffic, makes sure the monitor is watching closely, and stops. Whether
   * anything happens next is the monitor's decision, and if it decides the
   * current route is still the best, that is the answer shown.
   */
  const triggerSpike = useCallback(async ({ progress = 0.3, level = 0.92 } = {}) => {
    if (api.isMockMode()) {
      setError('The traffic spike needs the backend: the alert comes from its monitor, which does not run in offline mode.')
      return false
    }
    setSpiking(true)
    setError(null)
    setRerouteResult(null)
    setRouteCheck(null)
    try {
      await api.startMonitor({ tickSeconds: WATCH_TICK_S, graph })
      // Part-way along, so the jam lands on road still to be driven.
      await api.advanceTrip({ progress, graph })
      // Stamped before the spike, so an alert that arrives within milliseconds
      // of it is still counted as the answer to it.
      setSpikeAt(Date.now())
      await api.congestActiveRoute({ level, graph })
      await refreshTraffic()
      return true
    } catch (err) {
      setSpikeAt(null)
      setError(err.message || 'Could not apply the traffic spike.')
      return false
    } finally {
      setSpiking(false)
    }
  }, [graph, refreshTraffic])

  /**
   * The driver took the suggested route.
   *
   * The map is redrawn from the route the backend says it switched to — the
   * accept response carries it now. Before, accepting changed the trip on the
   * server and returned nothing, so the popup closed and the map went on
   * showing the old road.
   */
  const switchRoute = useCallback(async () => {
    setRerouting(true)
    if (demoMode) setDemoStep('rerouting')
    const before = selectedRoute
    try {
      const res = await api.acceptReroute(graph)
      if (!res?.ok) {
        setError(res?.reason ? `Could not switch: ${res.reason}.` : 'Could not switch route.')
        return null
      }
      if (res.newRoute) {
        // A distinct id: the backend numbers routes from r1, which would
        // replace the original on the map instead of standing beside it.
        const newRoute = { ...res.newRoute, id: `rerouted-${Date.now()}`, label: 'New route', recommended: true }
        setRoutes((prev) => [newRoute, ...prev.map((r) => ({ ...r, recommended: false }))])
        setSelectedRouteId(newRoute.id)
        setRoutesVersion((v) => v + 1)
        setRerouteResult({
          shouldReroute: true,
          oldRoute: before,
          newRoute,
          previousEtaMin: res.previousEtaMin,
          newEtaMin: res.newEtaMin,
          timeSavedMin: res.timeSavedMin,
          savedPct: res.savedPct,
          reason: res.reason,
          isDemoData: false,
        })
      }
      return res
    } catch (err) {
      setError(err.message || 'Could not switch route.')
      return null
    } finally {
      setRerouting(false)
    }
  }, [demoMode, graph, selectedRoute])

  const keepRoute = useCallback(async () => {
    try { await api.declineReroute(graph) } catch { /* monitoring continues either way */ }
  }, [graph])

  /**
   * Every notification the backend pushes passes through here, so the demo
   * can follow what the SYSTEM did rather than a timeline of its own.
   * Stamped with the time it arrived: comparing the server's clock with this
   * one would break the moment they disagree.
   */
  const reportNotification = useCallback((note) => {
    const stamped = { ...note, receivedAt: Date.now() }
    if (note.kind === 'route-check') setRouteCheck(stamped)
    else if (note.actionable) setLatestAlert(stamped)
  }, [])

  const resetScenario = useCallback(() => {
    clearTimers()
    setRoutes([])
    setSelectedRouteId(null)
    setRerouteResult(null)
    setLatestAlert(null)
    setRouteCheck(null)
    setSpikeAt(null)
    setDemoMode(false)
    setDemoStep(null)
    refreshTraffic()
  }, [clearTimers, refreshTraffic])

  /** Back to the everyday monitoring cadence once nobody is watching the demo. */
  const relaxMonitor = useCallback(() => {
    if (!api.isMockMode()) api.startMonitor({ tickSeconds: RELAXED_TICK_S, graph }).catch(() => {})
  }, [graph])

  /**
   * The demonstration, driven by the system rather than a script.
   *
   *   optimise  →  spike the road ahead  →  the MONITOR notices and alerts
   *   →  the route is switched  →  the assistant checks the new road
   *
   * The only timer is the pause before the spike, so the audience sees the
   * route first. Every later step waits for the backend to actually do it:
   * the alert step is reached when the monitor's alert arrives, not at a
   * fixed second. If the monitor decides the route is still the best, the
   * demo says so — that is a real answer, not a failure to paper over.
   */
  const startDemo = useCallback(async () => {
    clearTimers()
    if (api.isMockMode()) {
      setError('Demo Mode needs the backend: the alert comes from its monitor, which does not run in offline mode.')
      return
    }
    setDemoMode(true)
    setError(null)
    setRerouteResult(null)
    setLatestAlert(null)
    setRouteCheck(null)
    setSpikeAt(null)
    setRoutes([])

    try {
      // Every run starts from the same traffic. Spikes persist on the
      // network, so without this each replay would begin in a worse city.
      await api.triggerScenario(DEMO_SCENARIO, graph)
      await refreshTraffic()
    } catch { /* carry on with whatever traffic is loaded */ }

    setDemoStep('optimizing')
    const res = await optimize()
    if (!res) {
      setDemoMode(false)
      setDemoStep(null)
      return
    }

    const at = (ms, fn) => timers.current.push(setTimeout(fn, ms))
    at(3600, async () => {
      setDemoStep('traffic-rising')
      const ok = await triggerSpike()
      if (!ok) {
        setDemoMode(false)
        setDemoStep(null)
        return
      }
      // A monitor that has said nothing in 25 s is itself a result. Say so
      // rather than leave the demo waiting on an alert that is not coming.
      at(ALERT_WAIT_MS, () => {
        setDemoStep((step) => {
          if (step !== 'traffic-rising') return step
          setError('The monitor looked at the congested road and kept the current route — it found no alternative worth the switch.')
          relaxMonitor()
          return 'done'
        })
      })
    })
  }, [clearTimers, graph, optimize, refreshTraffic, relaxMonitor, triggerSpike])

  const stopDemo = useCallback(() => {
    clearTimers()
    setDemoMode(false)
    setDemoStep(null)
    relaxMonitor()
  }, [clearTimers, relaxMonitor])

  // The demo advances on what the backend did. The alert step is reached only
  // by an alert that arrived after this demo's spike.
  useEffect(() => {
    if (!demoMode || demoStep !== 'traffic-rising') return
    if (latestAlert && spikeAt && latestAlert.receivedAt >= spikeAt) setDemoStep('alert')
  }, [demoMode, demoStep, latestAlert, spikeAt])

  // And it ends when the assistant has checked the road the driver switched to.
  useEffect(() => {
    if (!demoMode || !routeCheck || demoStep === 'done') return
    if (demoStep === 'rerouting' || demoStep === 'alert') {
      setDemoStep('done')
      relaxMonitor()
    }
  }, [demoMode, demoStep, routeCheck, relaxMonitor])

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
    setLatestAlert(null)
  }, [])

  const dismissAlert = useCallback((id) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id))
  }, [])

  /* Changing network invalidates the endpoints. A Hyderabad street exists on
   * the city graph and not on the national one; a place 40 km from any
   * arterial road is fine on the city graph and snaps badly on the other. The
   * routes go too, since they were solved on a network we are leaving. */
  const setGraph = useCallback((next) => {
    setGraphState((prev) => {
      if (prev !== next) {
        setStart(null)
        setEnd(null)
        setRoutes([])
        setSelectedRouteId(null)
        setError(null)
      }
      return next
    })
  }, [])

  const value = {
    user, signIn, signUp: signIn, signOut,
    theme, setTheme,
    collapsed, setCollapsed,
    settings, setSettings,
    start, setStart, end, setEnd,
    algorithm, setAlgorithm, mode, setMode, vehicle, setVehicle,
    graph, setGraph,
    routes, selectedRoute, selectedRouteId, setSelectedRouteId,
    optimizing, optimize, error,
      applyAssistantActions,
    routesVersion,
    lastRun,
    lastDetection, setLastDetection,
    segments, incidents, alerts, dismissAlert,
    refreshAlerts, raiseAlert, wipeAlerts,
    spikeAt, spiking, latestAlert, routeCheck, triggerSpike, reportNotification,
    rerouting, rerouteResult, switchRoute, keepRoute,
    demoMode, demoStep, startDemo, stopDemo, resetScenario,
  }

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export { ROUTES, REROUTED_ROUTE }
