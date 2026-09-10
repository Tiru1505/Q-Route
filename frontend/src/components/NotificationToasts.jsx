import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, Bot, CheckCircle2, Route as RouteIcon, X } from 'lucide-react'
import { acceptReroute, declineReroute } from '../services/api'
import { useApp } from '../store/AppContext'

/**
 * Notifications the backend sends without being asked.
 *
 * Everything else in this app asks the API a question and renders the answer.
 * This listens. A jam forming on the driver's route is exactly the case where
 * waiting to be asked is the wrong behaviour, so the monitor pushes and this
 * shows what arrives.
 *
 * The socket reconnects with a widening delay, because a backend restart
 * during a demonstration should heal itself rather than leave a page that
 * looks fine and is quietly deaf.
 *
 * `phrasedBy` is shown on the card. When a language model has reworded the
 * message it says so, and the measured figures sit beside the text — a phrased
 * sentence should always be checkable against what was actually computed.
 */

const ICON = { severe: AlertTriangle, moderate: AlertTriangle, info: CheckCircle2 }
const MAX_VISIBLE = 3
const DISMISS_AFTER_MS = 15_000

function wsUrl() {
  const base = import.meta.env.VITE_API_BASE || '/api'
  if (base.startsWith('http')) {
    return `${base.replace(/^http/, 'ws')}/notifications/ws`
  }
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}${base}/notifications/ws`
}

export default function NotificationToasts() {
  const { graph } = useApp()
  const [toasts, setToasts] = useState([])
  const [connected, setConnected] = useState(false)
  const socketRef = useRef(null)
  const retryRef = useRef(0)
  const timersRef = useRef(new Map())

  const dismiss = useCallback((id) => {
    setToasts((t) => t.filter((x) => x.id !== id))
    const timer = timersRef.current.get(id)
    if (timer) { clearTimeout(timer); timersRef.current.delete(id) }
  }, [])

  const show = useCallback((note) => {
    setToasts((t) => {
      if (t.some((x) => x.id === note.id)) return t
      return [note, ...t].slice(0, MAX_VISIBLE)
    })
    // An actionable alert waits for a decision; anything informational clears
    // itself, or the corner fills with notices nobody needs to act on.
    if (!note.actionable) {
      timersRef.current.set(
        note.id,
        setTimeout(() => dismiss(note.id), DISMISS_AFTER_MS),
      )
    }
  }, [dismiss])

  useEffect(() => {
    let closed = false
    let retryTimer = 0

    const connect = () => {
      if (closed) return
      let ws
      try {
        ws = new WebSocket(wsUrl())
      } catch {
        return
      }
      socketRef.current = ws

      ws.onopen = () => { retryRef.current = 0; setConnected(true) }

      ws.onmessage = (event) => {
        let data
        try { data = JSON.parse(event.data) } catch { return }
        // The backlog is history, not news — showing it as toasts would pop
        // old alerts every time a page loads.
        if (data.type === 'backlog') return
        show(data)
      }

      ws.onclose = () => {
        setConnected(false)
        if (closed) return
        retryRef.current = Math.min(retryRef.current + 1, 6)
        retryTimer = setTimeout(connect, 500 * 2 ** (retryRef.current - 1))
      }

      ws.onerror = () => ws.close()
    }

    connect()
    return () => {
      closed = true
      clearTimeout(retryTimer)
      timersRef.current.forEach(clearTimeout)
      timersRef.current.clear()
      socketRef.current?.close()
    }
  }, [show])

  const act = async (note, accept) => {
    try {
      await (accept ? acceptReroute(graph) : declineReroute(graph))
    } catch { /* the card closes either way; the backend keeps monitoring */ }
    dismiss(note.id)
  }

  if (!toasts.length) return null

  return (
    <div className="toast-stack" aria-live="polite">
      <AnimatePresence initial={false}>
        {toasts.map((note) => {
          const Icon = ICON[note.severity] || CheckCircle2
          return (
            <motion.div
              key={note.id}
              className={`toast toast-${note.severity}`}
              initial={{ opacity: 0, x: 40, scale: 0.97 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 40, scale: 0.97 }}
              transition={{ duration: 0.22 }}
            >
              <div className="toast-head">
                <Icon size={14} />
                <strong>
                  {note.severity === 'info' ? 'Traffic update' : 'Traffic alert'}
                </strong>
                <button className="toast-x" onClick={() => dismiss(note.id)}
                        aria-label="Dismiss">
                  <X size={12} />
                </button>
              </div>

              <p className="toast-text">{note.text}</p>

              {note.timeSaved > 0 && (
                <div className="toast-figures">
                  <span>{note.currentEta} min now</span>
                  <span>→</span>
                  <span>{note.alternativeEta} min</span>
                  <b>saves {note.timeSaved}</b>
                </div>
              )}

              {note.actionable && (
                <div className="toast-actions">
                  <button className="btn-primary btn-sm" onClick={() => act(note, true)}>
                    <RouteIcon size={12} /> Switch route
                  </button>
                  <button className="btn-ghost btn-sm" onClick={() => act(note, false)}>
                    Keep current
                  </button>
                </div>
              )}

              <div className="toast-foot">
                <Bot size={10} />
                {note.phrasedBy === 'llm'
                  ? 'Worded by the assistant — figures are measured'
                  : 'Generated from measured figures'}
                {!connected && ' · reconnecting'}
              </div>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
