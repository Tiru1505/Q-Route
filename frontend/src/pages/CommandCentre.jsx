import { useCallback, useEffect, useState } from 'react'
import {
  Activity, AlertTriangle, Brain, CheckCircle2, CircleAlert, Cpu,
  PlayCircle, RefreshCw, Route as RouteIcon, XCircle, Zap,
} from 'lucide-react'
import PipelineStatus, { buildStages } from '../components/PipelineStatus'
import {
  acceptReroute, analyzeTraffic, congestActiveRoute, declineReroute,
  getAgentStatus, getScenarios, getSystemStatus, triggerScenario,
} from '../services/api'
import { useApp } from '../store/AppContext'

/**
 * Command Centre — the one screen that shows the whole system honestly.
 *
 * Three things live here that were previously either missing or implied:
 *
 *   SYSTEM STATUS      what is actually loaded, asked of the backend rather
 *                      than a row of green dots drawn in JSX
 *   SIMULATION         events that really change the graph, every one labelled
 *   AGENT DECISION     the reroute recommendation with its reasoning, and the
 *                      switch/keep choice
 *
 * Nothing on this page has a demo fallback. A fabricated "system online" or a
 * fabricated "12 minutes saved" looks exactly like a real one, and this is the
 * screen whose entire job is to say which parts are real.
 */

const DOT = { ok: 'sd-ok', warn: 'sd-warn', off: 'sd-off' }

function StatusRow({ label, state, detail }) {
  return (
    <div className="status-row">
      <span className={`status-dot ${DOT[state] || DOT.off}`} />
      <span className="status-label">{label}</span>
      <span className="status-detail">{detail}</span>
    </div>
  )
}

export default function CommandCentre() {
  const { start, end, graph, routes, selectedRoute } = useApp()

  const [sys, setSys] = useState(null)
  const [agentInfo, setAgentInfo] = useState(null)
  const [scenarios, setScenarios] = useState(null)
  const [decision, setDecision] = useState(null)
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [note, setNote] = useState(null)

  const refresh = useCallback(async () => {
    const [s, a] = await Promise.allSettled([getSystemStatus(), getAgentStatus(graph)])
    setSys(s.status === 'fulfilled' ? s.value : { unreachable: true })
    setAgentInfo(a.status === 'fulfilled' ? a.value : null)
  }, [graph])

  useEffect(() => {
    refresh()
    getScenarios(graph).then(setScenarios).catch(() => setScenarios(null))
  }, [refresh, graph])

  const run = async (label, fn) => {
    setBusy(label); setError(null); setNote(null)
    try {
      return await fn()
    } catch (e) {
      setError(e.message)
      return null
    } finally {
      setBusy(null)
      refresh()
    }
  }

  const onAnalyse = () => run('analyse', async () => {
    const d = await analyzeTraffic({ graph, force: true })
    setDecision(d)
    return d
  })

  const onScenario = (id) => run(id, async () => {
    const r = await triggerScenario(id, graph)
    setNote(`${r.label} applied — ${r.closedEdges} closed edge(s), ${r.incidents.length} incident(s). SIMULATED.`)
    setDecision(null)
    return r
  })

  const onCongest = () => run('congest', async () => {
    const r = await congestActiveRoute({ level: 0.95, graph })
    setNote(`Congestion applied to the active route (${r.affected} edges). SIMULATED.`)
    return r
  })

  const onSwitch = () => run('switch', async () => {
    const r = await acceptReroute(graph)
    setNote(r.ok ? 'Switched to the recommended route.' : `Not switched: ${r.reason}`)
    setDecision(null)
    return r
  })

  const onKeep = () => run('keep', async () => {
    const r = await declineReroute(graph)
    setNote(r.ok ? 'Keeping the current route. Monitoring continues.' : `${r.reason}`)
    setDecision(null)
    return r
  })

  const adapters = sys?.adapters || {}
  const depends = agentInfo?.depends || {}
  const stages = buildStages({
    agent: decision,
    route: selectedRoute,
    benchmark: null,
    detection: null,
  })

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Command Centre</h1>
          <p className="page-sub">
            Live component status, traffic events, and the agent's rerouting decision.
          </p>
        </div>
        <button className="btn-ghost btn-sm" onClick={refresh}>
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {error && (
        <div className="card" style={{ borderColor: 'var(--severe)', marginBottom: 12 }}>
          <div className="card-title"><CircleAlert size={13} /> {error}</div>
        </div>
      )}
      {note && (
        <div className="card" style={{ borderColor: 'var(--border-strong)', marginBottom: 12 }}>
          <p style={{ fontSize: 12, margin: 0, color: 'var(--text-dim)' }}>{note}</p>
        </div>
      )}

      <div className="grid grid-2">
        {/* ------------------------------------------- system status --- */}
        <div className="card">
          <div className="card-title"><Cpu size={13} /> System status</div>
          {!sys ? (
            <p className="vision-empty">Checking…</p>
          ) : sys.unreachable ? (
            <p className="vision-error"><XCircle size={12} /> Backend unreachable.</p>
          ) : (
            <div className="status-list">
              <StatusRow label="Backend" state="ok" detail={`v${sys.version} · ${sys.environment}`} />
              <StatusRow
                label="Database"
                state={sys.database?.mongodb === 'connected' ? 'ok' : 'off'}
                detail={sys.database?.mongodb ?? 'unknown'}
              />
              <StatusRow label="Road graph" state={adapters.graph === 'osm' ? 'ok' : 'warn'}
                         detail={depends.graph ? `${depends.graph.toLocaleString()} nodes` : adapters.graph} />
              <StatusRow label="Optimiser" state={adapters.optimization === 'osm' ? 'ok' : 'warn'}
                         detail={adapters.optimization} />
              <StatusRow label="Traffic layer" state={adapters.traffic === 'osm' ? 'ok' : 'warn'}
                         detail={adapters.traffic} />
              <StatusRow
                label="LSTM forecaster"
                state={depends.forecaster ? 'ok' : 'off'}
                detail={adapters.prediction || (depends.forecaster ? 'ready' : 'not trained')}
              />
              <StatusRow
                label="YOLO detector"
                state={depends.detector ? 'ok' : 'off'}
                detail={depends.detector ? 'weights loaded' : 'not trained'}
              />
              <StatusRow
                label="AI agent"
                state={agentInfo?.active ? 'ok' : 'warn'}
                detail={agentInfo?.active
                  ? `monitoring · ${Math.round((agentInfo.progress ?? 0) * 100)}% along`
                  : 'no active trip'}
              />
            </div>
          )}
          <p className="vision-hint">
            Read from <code>/api/status</code> and <code>/api/agent/status</code>. A
            component shows offline when it genuinely is — nothing here is drawn green
            by default.
          </p>
        </div>

        {/* ------------------------------------------- simulation ------ */}
        <div className="card">
          <div className="card-title"><PlayCircle size={13} /> Traffic events</div>
          <p className="vision-hint" style={{ marginTop: 0 }}>
            Each event changes the graph for real — closures close edges, congestion
            raises congestion. Routes computed afterwards reflect it.
          </p>
          <div className="sim-grid">
            {(scenarios?.scenarios || []).map((s) => (
              <button
                key={s.id}
                className={`btn-ghost btn-sm${scenarios?.active === s.id ? ' is-active' : ''}`}
                disabled={busy != null}
                onClick={() => onScenario(s.id)}
              >
                {busy === s.id ? '…' : s.label}
              </button>
            ))}
          </div>
          <button
            className="btn-primary btn-sm"
            style={{ marginTop: 10, width: '100%' }}
            disabled={busy != null || !agentInfo?.active}
            onClick={onCongest}
            title={agentInfo?.active ? '' : 'Optimise a route first'}
          >
            <Zap size={12} /> Congest the active route
          </button>
          <p className="vision-note">
            Scenario hotspots sit where real jams form and often miss whichever route
            was chosen. This puts the disruption on the road the driver is on, which is
            what makes rerouting demonstrable. All of it is <strong>SIMULATED</strong>.
          </p>
        </div>
      </div>

      {/* --------------------------------------------- agent ---------- */}
      <div className="card">
        <div className="row-between" style={{ marginBottom: 10 }}>
          <div className="card-title" style={{ margin: 0 }}>
            <Brain size={13} /> AI traffic agent
          </div>
          <button
            className="btn-primary btn-sm"
            disabled={busy != null || !agentInfo?.active}
            onClick={onAnalyse}
            title={agentInfo?.active ? '' : 'Optimise a route first — the agent monitors a journey'}
          >
            {busy === 'analyse' ? 'Analysing…' : 'Analyse now'}
          </button>
        </div>

        {!agentInfo?.active ? (
          <p className="vision-empty">
            No active trip. Optimise a route first — the agent monitors a journey, it
            does not invent one.
          </p>
        ) : !decision ? (
          <p className="vision-empty">Press “Analyse now” to run the decision loop.</p>
        ) : (
          <>
            <div className={`agent-verdict ${decision.decision === 'reroute' ? 'is-reroute' : 'is-keep'}`}>
              {decision.decision === 'reroute'
                ? <AlertTriangle size={15} /> : <CheckCircle2 size={15} />}
              <strong>
                {decision.decision === 'reroute' ? 'Rerouting recommended' : 'Stay on the current route'}
              </strong>
              <span className={`sev sev-${decision.severity}`}>{decision.severity}</span>
            </div>

            <p className="agent-reason">{decision.reason}</p>

            <div className="vision-stats" style={{ marginTop: 12 }}>
              <div><span>{decision.currentEta ?? '—'}</span>current ETA (min)</div>
              <div><span>{decision.alternativeEta ?? '—'}</span>alternative (min)</div>
              <div><span>{decision.timeSaved ?? '—'}</span>saved (min)</div>
              <div><span>{decision.analysisMs}</span>analysis (ms)</div>
            </div>

            {decision.betterButBelowThreshold && (
              <p className="vision-hint">
                A better route exists but the alert policy held its tongue, so
                there is nothing to switch to — the comparison is shown above.
              </p>
            )}

            {/* Only when an alert actually survived the policy. Offering a
                switch with no alert behind it produced a button that failed
                when pressed. */}
            {decision.decision === 'reroute' && decision.alert && (
              <div className="agent-actions">
                <button className="btn-primary btn-sm" disabled={busy != null} onClick={onSwitch}>
                  <RouteIcon size={12} /> Switch route
                </button>
                <button className="btn-ghost btn-sm" disabled={busy != null} onClick={onKeep}>
                  Keep current route
                </button>
              </div>
            )}

            <p className="vision-note">{decision.forecast?.note}</p>
          </>
        )}
      </div>

      {/* --------------------------------------------- pipeline ------- */}
      <div className="card">
        <div className="card-title"><Activity size={13} /> Pipeline</div>
        <PipelineStatus stages={stages} />
        <p className="vision-hint">
          A stage turns green only when its data has actually arrived. Stages showing
          “waiting” have not run in this session.
        </p>
      </div>
    </div>
  )
}
