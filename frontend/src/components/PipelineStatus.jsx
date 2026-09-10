import { Check, CircleDashed, Loader2, X } from 'lucide-react'

/**
 * The Q-Route pipeline, stage by stage.
 *
 * Each stage reports what it actually knows. A stage with no data shows
 * "waiting" rather than a tick — a green tick beside a stage that never ran is
 * the single most misleading thing this component could do, because the whole
 * purpose of showing the pipeline is to make it obvious which parts are real.
 *
 * Stages are derived from live responses: the detector's own output, the
 * forecaster's, the agent's decision, the route the optimiser returned.
 * Nothing here is scheduled or animated to look busy.
 */

const STATE = {
  ready: { icon: Check, cls: 'ps-ok' },
  running: { icon: Loader2, cls: 'ps-run' },
  waiting: { icon: CircleDashed, cls: 'ps-wait' },
  error: { icon: X, cls: 'ps-err' },
}

export default function PipelineStatus({ stages = [], compact = false }) {
  return (
    <div className={`pipeline${compact ? ' is-compact' : ''}`}>
      {stages.map((s, i) => {
        const meta = STATE[s.state] || STATE.waiting
        const Icon = meta.icon
        return (
          <div key={s.id ?? i} className={`ps-stage ${meta.cls}`}>
            <div className="ps-head">
              <Icon size={12} className={s.state === 'running' ? 'spin' : undefined} />
              <span className="ps-name">{s.label}</span>
            </div>
            <div className="ps-value">{s.value ?? '—'}</div>
            {s.note && <div className="ps-note">{s.note}</div>}
          </div>
        )
      })}
    </div>
  )
}

/**
 * Build the stage list from whatever the app currently holds.
 *
 * Written as a pure function of real state so a stage cannot be marked ready
 * by anything other than data arriving.
 */
export function buildStages({ detection, forecast, agent, route, benchmark } = {}) {
  const vehicles = detection?.totalVehicles
  const measures = detection?.measures
  const fc = agent?.forecast

  return [
    {
      id: 'input',
      label: 'INPUT',
      state: detection ? 'ready' : 'waiting',
      value: detection ? (detection.kind === 'video' ? 'Clip' : 'Image') : 'No upload',
      note: detection ? `${detection.framesProcessed} frame${detection.framesProcessed === 1 ? '' : 's'}` : 'Upload in Road Vision',
    },
    {
      id: 'yolo',
      label: 'YOLO',
      state: detection ? 'ready' : 'waiting',
      value: vehicles != null ? `${vehicles} vehicles` : '—',
      note: measures ? `measures ${measures}` : null,
    },
    {
      id: 'counts',
      label: 'COUNTS → PCU',
      state: detection ? 'ready' : 'waiting',
      value: detection?.pcu != null ? `${detection.pcu} PCU` : '—',
      note: detection?.congestion ? `${Math.round(detection.congestion.congestion * 100)}% congestion` : null,
    },
    {
      id: 'lstm',
      label: 'LSTM',
      state: forecast ? 'ready' : (fc?.applied ? 'ready' : 'waiting'),
      value: fc?.applied
        ? `${Math.round(fc.predictedMean * 100)}% at +${fc.horizonMin}m`
        : (forecast ? 'forecast ready' : 'no history'),
      note: fc?.applied ? `${fc.samples} points sampled` : 'needs a run of counts',
    },
    {
      id: 'agent',
      label: 'AI AGENT',
      state: agent ? (agent.decision === 'reroute' ? 'ready' : 'ready') : 'waiting',
      value: agent ? (agent.decision === 'reroute' ? 'Reroute' : 'Keep route') : '—',
      note: agent?.severity ? `severity ${agent.severity}` : null,
    },
    {
      id: 'graph',
      label: 'DYNAMIC GRAPH',
      state: fc?.edgesUpdated ? 'ready' : 'waiting',
      value: fc?.edgesUpdated ? `${fc.edgesUpdated} edges` : '—',
      note: fc?.edgesUpdated ? 'reverted after analysis' : null,
    },
    {
      id: 'qpso',
      label: 'OPTIMISER',
      state: route ? 'ready' : 'waiting',
      value: route ? `${route.distanceKm ?? route.distance_km ?? '—'} km` : '—',
      note: agent?.algorithm ? `alt via ${agent.algorithm}` : null,
    },
    {
      id: 'alert',
      label: 'ALERT',
      state: agent?.alert ? 'ready' : (agent ? 'waiting' : 'waiting'),
      value: agent?.timeSaved != null && agent.timeSaved > 0
        ? `${agent.timeSaved} min saved`
        : (agent ? 'none raised' : '—'),
      note: agent?.suppressedBecause || null,
    },
    {
      id: 'benchmark',
      label: 'BENCHMARK',
      state: benchmark ? 'ready' : 'waiting',
      value: benchmark?.rows?.length ? `${benchmark.rows.length} algorithms` : '—',
      note: benchmark?.trials ? `${benchmark.trials} trials` : null,
    },
  ]
}
