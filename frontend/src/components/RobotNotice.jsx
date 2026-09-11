import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Bot, CheckCircle2, Loader2, Route as RouteIcon } from 'lucide-react'

/**
 * A notification, delivered by the robot as one of its own messages.
 *
 * The robot used to answer only when asked, and alerts arrived as popups
 * stacked above it — two voices for one system. Now the monitor's alert and
 * the check of a new route are things the robot says, in its thread, with the
 * decision buttons attached to the message they belong to.
 *
 * What it says is the backend's text, unchanged. `phrasedBy` says whether a
 * language model reworded it; either way the measured figures sit beside the
 * words, so a phrased sentence can be checked against what was computed.
 */

// In Demo Mode an alert switches by itself after this long, so the whole flow
// runs untouched — visibly, and the presenter can still press either button.
const DEMO_AUTO_SWITCH_S = 6

const OUTCOME = {
  switched: 'Switched. The new route is drawn on the map.',
  kept: 'Kept your current route. I am still watching it.',
  superseded: 'A newer alert replaced this one.',
  failed: 'That did not go through.',
}

/** The demo's countdown. Fires once; acting on the alert unmounts it. */
function AutoSwitch({ seconds, onFire }) {
  const [left, setLeft] = useState(seconds)
  const fired = useRef(false)
  useEffect(() => {
    const id = setInterval(() => setLeft((n) => n - 1), 1000)
    return () => clearInterval(id)
  }, [])
  useEffect(() => {
    if (left <= 0 && !fired.current) {
      fired.current = true
      onFire()
    }
  }, [left, onFire])
  return <div className="robot-notice-auto">Demo: switching automatically in {Math.max(left, 0)}s</div>
}

function clock(epochSeconds) {
  if (!epochSeconds) return ''
  return new Date(epochSeconds * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const round = (n) => (typeof n === 'number' ? Math.round(n) : n)

export default function RobotNotice({ message, demoMode, connected, onAct }) {
  const { note, status, outcome } = message
  const isCheck = note.kind === 'route-check'
  const tone = isCheck ? 'check' : note.severity || 'info'
  const Icon = isCheck ? Bot : tone === 'info' ? CheckCircle2 : AlertTriangle
  const title = isCheck
    ? 'I checked your new route'
    : tone === 'info' ? 'Traffic update' : 'Traffic alert on your route'
  const open = status === 'pending' || status === 'working'

  return (
    <div
      className={`assistant-message assistant robot-notice robot-notice-${tone}`}
      role={note.actionable ? 'alert' : 'status'}
    >
      <div className="robot-notice-head">
        <Icon size={13} aria-hidden="true" />
        <strong>{title}</strong>
        <time>{clock(note.at)}</time>
      </div>

      <p className="robot-notice-text">{note.text}</p>

      {!isCheck && note.timeSaved > 0 && (
        <div className="robot-notice-figures">
          <span>{round(note.currentEta)} min now</span>
          <span aria-hidden="true">→</span>
          <span>{round(note.alternativeEta)} min</span>
          <b>saves {round(note.timeSaved)} min</b>
        </div>
      )}

      {status === 'pending' && demoMode && (
        <AutoSwitch seconds={DEMO_AUTO_SWITCH_S} onFire={() => onAct(message.id, true)} />
      )}

      {open && (
        <div className="robot-notice-actions">
          <button className="btn-primary btn-sm" type="button" disabled={status === 'working'}
                  onClick={() => onAct(message.id, true)}>
            {status === 'working' ? <Loader2 size={12} className="spin" /> : <RouteIcon size={12} />}
            Switch route
          </button>
          <button className="btn-ghost btn-sm" type="button" disabled={status === 'working'}
                  onClick={() => onAct(message.id, false)}>
            Keep current
          </button>
        </div>
      )}

      {OUTCOME[status] && (
        <div className={`robot-notice-outcome is-${status}`}>{outcome || OUTCOME[status]}</div>
      )}

      <span className="assistant-provenance">
        {note.phrasedBy === 'llm'
          ? 'Worded by the assistant — figures are measured'
          : 'Generated from measured figures'}
        {!connected && ' · reconnecting'}
      </span>
    </div>
  )
}
