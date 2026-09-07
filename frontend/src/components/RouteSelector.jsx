import {
  ArrowUpDown,
  Flag,
  MapPin,
  Navigation,
  Play,
  RotateCcw,
  Zap,
} from 'lucide-react'
import PlaceInput from './PlaceInput'
import { ALGORITHMS, OPTIMIZATION_MODES } from '../data/mockData'
import { useApp } from '../store/AppContext'

/** Two places are the same trip endpoint if they land on the same spot. */
const samePlace = (a, b) => {
  if (!a || !b) return false
  if (a.id && b.id) return a.id === b.id
  return Math.abs(a.lat - b.lat) < 1e-6 && Math.abs(a.lon - b.lon) < 1e-6
}

export default function RouteSelector({ onOptimize, busy }) {
  const {
    start,
    setStart,
    end,
    setEnd,
    algorithm,
    setAlgorithm,
    mode,
    setMode,
    demoMode,
    startDemo,
    stopDemo,
    resetScenario,
  } = useApp()

  const swap = () => {
    setStart(end)
    setEnd(start)
  }

  const activeAlgo = ALGORITHMS.find((a) => a.id === algorithm)

  const incomplete = !start || !end
  const identical = samePlace(start, end)
  const ready = !incomplete && !identical

  return (
    <div className="card route-selector-card">

      {/* HEADER */}
      <div className="card-title route-selector-title">
        <Navigation size={13} />
        <span>Route Planner</span>
      </div>

      {/* START LOCATION */}
      <PlaceInput
        id="start"
        label="Start location"
        value={start}
        onChange={setStart}
        placeholder="Type start location in Hyderabad…"
        icon={<MapPin size={14} />}
      />

      {/* SWAP BUTTON */}
      <div className="route-swap-wrapper">
        <button
          className="icon-btn route-swap-btn"
          onClick={swap}
          aria-label="Swap start and destination"
          title="Swap locations"
        >
          <ArrowUpDown size={14} />
        </button>
      </div>

      {/* DESTINATION */}
      <PlaceInput
        id="end"
        label="Destination"
        value={end}
        onChange={setEnd}
        placeholder="Type destination in Hyderabad…"
        icon={<Flag size={14} />}
      />

      {/* ALGORITHM */}
      <div className="field route-field">
        <label htmlFor="algo">Algorithm</label>

        <select
          id="algo"
          className="select route-select"
          value={algorithm}
          onChange={(e) => setAlgorithm(e.target.value)}
        >
          {ALGORITHMS.map((a) => (
            <option key={a.id} value={a.id}>
              {a.full}
            </option>
          ))}
        </select>

        {activeAlgo?.quantum && (
          <div className="badge badge-quantum quantum-badge">
            <Zap size={9} />
            Quantum-inspired
          </div>
        )}
      </div>

      {/* OPTIMIZATION OBJECTIVE */}
      <div className="field route-field">
        <label>Optimization objective</label>

        <div className="segmented route-segmented">
          {OPTIMIZATION_MODES.map((m) => (
            <button
              key={m.id}
              data-active={mode === m.id}
              onClick={() => setMode(m.id)}
              title={`time ${m.weights.time} · distance ${m.weights.distance} · congestion ${m.weights.congestion}`}
            >
              {m.name}
            </button>
          ))}
        </div>
      </div>

      {/* OPTIMIZE BUTTON */}
      <button
        className="btn btn-primary btn-block optimize-route-btn"
        onClick={onOptimize}
        disabled={busy || !ready}
      >
        {busy ? (
          <Zap size={15} className="spin" style={{ color: '#FFB347' }} />
        ) : (
          <Navigation size={15} />
        )}

        <span>
          {busy ? 'Optimizing…' : 'Optimize Route'}
        </span>
      </button>

      {/* WHY THE BUTTON IS DISABLED */}
      {!busy && incomplete && (
        <p className="route-warning">
          Choose a start and a destination.
        </p>
      )}
      {!busy && !incomplete && identical && (
        <p className="route-warning">
          Start and destination must differ.
        </p>
      )}

      {/* DEMO + RESET */}
      <div className="route-actions">

        <button
          className={`btn btn-sm demo-btn ${
            demoMode ? '' : 'btn-quantum'
          }`}
          onClick={demoMode ? stopDemo : startDemo}
        >
          <Play size={13} />

          <span>
            {demoMode ? 'Stop Demo' : 'Demo Mode'}
          </span>
        </button>

        <button
          className="btn btn-sm reset-btn"
          onClick={resetScenario}
          aria-label="Reset scenario"
          title="Reset scenario"
        >
          <RotateCcw size={13} />
        </button>

      </div>
    </div>
  )
}