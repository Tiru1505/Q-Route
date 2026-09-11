import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Loader2, MessageCircle, Send, Sparkles, X } from 'lucide-react'
import { useApp } from '../store/AppContext'
import * as api from '../services/api'
import useNotificationSocket from '../hooks/useNotificationSocket'
import robotImage from '../assets/q-route-ai-robot.png'
import RobotNotice from './RobotNotice'

/**
 * The robot, and what it is allowed to say.
 *
 * Answers come from `/assistant/ask`, which reads the backend's own state —
 * the agent's decision, the forecaster's output, the active trip. That is why
 * the panel works with no AI key: the questions a driver asks are ones the
 * system has already computed answers to, and routing them through a language
 * model would replace a measured number with a recalled one.
 *
 * Each reply carries how it was produced, and the panel shows it. A judge
 * asking "did the AI make that up?" should be able to read the answer off the
 * screen.
 *
 * On opening, the robot speaks first. Congestion forming ahead is not
 * something a driver should have to think to ask about.
 *
 * And it does not wait to be opened. When the monitor pushes an alert, or the
 * check of a route the driver has just switched to, the robot opens itself and
 * says it in the thread — with the Switch / Keep buttons on that message. If
 * the driver closes the panel with an alert still unanswered, the robot keeps
 * a red badge until it is.
 */

const DEFAULT_SUGGESTIONS = [
  'Will there be congestion ahead?',
  'Should I reroute?',
  'How long is left?',
  'What have you counted so far?',
]

const SOURCE_LABEL = {
  measured: 'From measured system state',
  llm: 'Worded by the assistant',
  error: 'Could not be checked',
  unmatched: 'Outside what I track',
}

function AssistantRobot({ busy, open, alerting, onClick }) {
  const stageRef = useRef(null)
  const targetRef = useRef({ x: 0, y: 0 })
  const currentRef = useRef({ x: 0, y: 0 })
  const frameRef = useRef(null)
  const [blinking, setBlinking] = useState(false)
  const [near, setNear] = useState(false)

  useEffect(() => {
    const stage = stageRef.current
    if (!stage) return undefined

    const update = () => {
      const rect = stage.getBoundingClientRect()
      const centerX = rect.left + rect.width / 2
      const centerY = rect.top + rect.height / 2
      const dx = Math.max(-1, Math.min(1, (targetRef.current.x - centerX) / 220))
      const dy = Math.max(-1, Math.min(1, (targetRef.current.y - centerY) / 220))
      const distanceX = Math.max(rect.left - targetRef.current.x, 0, targetRef.current.x - rect.right)
      const distanceY = Math.max(rect.top - targetRef.current.y, 0, targetRef.current.y - rect.bottom)
      const proximity = Math.max(0, 1 - Math.hypot(distanceX, distanceY) / 180)

      currentRef.current.x += (dx * 3 - currentRef.current.x) * 0.12
      currentRef.current.y += (dy * 2 - currentRef.current.y) * 0.12
      stage.style.setProperty('--eye-x', `${currentRef.current.x.toFixed(2)}px`)
      stage.style.setProperty('--eye-y', `${currentRef.current.y.toFixed(2)}px`)
      stage.style.setProperty('--robot-tilt', `${(dx * 2.2 * proximity).toFixed(2)}deg`)
      stage.style.setProperty('--robot-scale', (1 + proximity * 0.035).toFixed(3))
      stage.style.setProperty('--robot-near', proximity.toFixed(2))
      setNear((value) => {
        const nextValue = proximity > 0.05
        return value === nextValue ? value : nextValue
      })
      frameRef.current = requestAnimationFrame(update)
    }

    const handleMouseMove = (event) => {
      targetRef.current = { x: event.clientX, y: event.clientY }
    }

    document.addEventListener('mousemove', handleMouseMove)
    frameRef.current = requestAnimationFrame(update)
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      cancelAnimationFrame(frameRef.current)
    }
  }, [])

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined
    let timeoutId
    const scheduleBlink = () => {
      timeoutId = window.setTimeout(() => {
        setBlinking(true)
        window.setTimeout(() => setBlinking(false), 120)
        scheduleBlink()
      }, 3000 + Math.random() * 3000)
    }
    scheduleBlink()
    return () => window.clearTimeout(timeoutId)
  }, [])

  return (
    <button
      ref={stageRef}
      className={`assistant-float-button ${near ? 'is-near' : ''} ${busy ? 'is-thinking' : ''} ${alerting ? 'is-alerting' : ''}`}
      type="button"
      onClick={onClick}
      aria-label={alerting ? 'Q Route AI has a traffic alert for you' : 'Ask Q Route AI'}
      aria-expanded={open}
      title={alerting ? 'Traffic alert waiting' : 'Ask Q Route AI'}
    >
      <span className="assistant-pulse" aria-hidden="true" />
      {alerting && !open && <span className="assistant-badge" aria-hidden="true">!</span>}
      <span className="assistant-robot-art">
        <span className={`assistant-eye-layer ${blinking ? 'is-blinking' : ''}`} aria-hidden="true">
          <span className="assistant-eye assistant-eye-left" />
          <span className="assistant-eye assistant-eye-right" />
        </span>
        <img className="assistant-robot-image" src={robotImage} alt="Q Route AI" />
        <span className={`assistant-hand-layer ${near || open ? 'is-waving' : ''} ${busy ? 'is-thinking' : ''}`} aria-hidden="true">
          <img src={robotImage} alt="" />
        </span>
      </span>
    </button>
  )
}

export default function AssistantPanel() {
  const {
    graph, start, end, selectedRoute, routes, segments, incidents,
    applyAssistantActions, demoMode, switchRoute, keepRoute, reportNotification,
    latestAlert, user,
  } = useApp()
  // A user may prefer the badge to the robot opening itself (Settings).
  const autoOpenRef = useRef(true)
  autoOpenRef.current = user?.preferences?.autoOpenAlerts !== false
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(false)
  const [chips, setChips] = useState(DEFAULT_SUGGESTIONS)
  const briefedRef = useRef(false)
  const threadRef = useRef(null)

  // Keep the newest reply in view. Without this a long answer arrives below
  // the fold and the panel looks like it did nothing.
  useEffect(() => {
    const thread = threadRef.current
    if (thread) thread.scrollTop = thread.scrollHeight
  }, [messages, busy])

  // Speak first. The prediction is the reason this thing exists, so opening the
  // panel should show it rather than an empty box inviting a question.
  useEffect(() => {
    if (!open || briefedRef.current) return
    briefedRef.current = true
    let cancelled = false
    setBusy(true)
    api.getAssistantBriefing(graph)
      .then((res) => {
        if (cancelled || !res?.text) return
        setMessages((m) => (m.length ? m : [{
          role: 'assistant', content: res.text, source: res.source, greeting: true,
        }]))
        if (res.suggestions?.length) setChips(res.suggestions)
      })
      .catch(() => { /* an unreachable briefing is not worth an error banner */ })
      .finally(() => { if (!cancelled) setBusy(false) })
    return () => { cancelled = true }
  }, [open, graph])

  /**
   * The robot delivers what the backend pushed.
   *
   * Reported to the app first, so the demo moves on the SYSTEM's alert — the
   * only signal that one happened. A new alert retires any older one still
   * waiting: accepting always acts on the latest suggestion, so an old
   * message's button would switch to a route it never described.
   */
  const deliver = useCallback((note) => {
    reportNotification(note)
    setMessages((m) => {
      if (m.some((x) => x.id === note.id)) return m
      const earlier = note.actionable
        ? m.map((x) => (x.status === 'pending' ? { ...x, status: 'superseded' } : x))
        : m
      return [...earlier, {
        id: note.id, role: 'assistant', note, status: note.actionable ? 'pending' : null,
      }]
    })
    // The alert is the briefing: fetching one now would only be discarded.
    briefedRef.current = true
    if (autoOpenRef.current) setOpen(true)
  }, [reportNotification])

  // Answered somewhere else — the dashboard's recommendation card — so this
  // message stops offering buttons for a decision already made.
  useEffect(() => {
    if (!latestAlert?.resolved) return
    const status = latestAlert.resolved === 'accepted' ? 'switched' : 'kept'
    setMessages((m) => m.map((x) => (
      x.id === latestAlert.id && x.status === 'pending' ? { ...x, status } : x)))
  }, [latestAlert])

  const connected = useNotificationSocket(deliver)

  // Switching goes through the app, not straight to the API, so the map is
  // redrawn with the route the backend switched to.
  const act = useCallback(async (id, accept) => {
    setMessages((m) => m.map((x) => (x.id === id ? { ...x, status: 'working' } : x)))
    const res = await (accept ? switchRoute() : keepRoute())
    let status = res?.ok ? (accept ? 'switched' : 'kept') : 'failed'
    let outcome = null
    if (!res?.ok) {
      outcome = res?.reason ? `That did not go through: ${res.reason}.` : null
    } else if (accept && res.newEtaMin != null && res.previousEtaMin != null) {
      outcome = `Switched. ${Math.round(res.newEtaMin)} min on the new route instead of `
        + `${Math.round(res.previousEtaMin)} — it is drawn on the map. I will check it next.`
    }
    setMessages((m) => m.map((x) => (x.id === id ? { ...x, status, outcome } : x)))
  }, [switchRoute, keepRoute])

  const alerting = messages.some((m) => m.status === 'pending')

  async function submit(text = draft) {
    const content = text.trim()
    if (!content || busy) return
    // Appended, never rebuilt from a copy: an alert can land while the answer
    // is in flight, and rebuilding would erase it.
    setMessages((m) => [...m, { role: 'user', content }])
    setDraft('')
    setError(null)
    setBusy(true)
    try {
      const response = await api.assistantAsk({
        question: content,
        graph,
        context: {
          start,
          destination: end,
          selected_route: selectedRoute,
          current_route: selectedRoute,
          routes,
          traffic: { segments, incidents },
        },
      })
      // Only the model path returns actions; a state-backed answer reports,
      // it does not steer the map.
      if (response.actions?.length) applyAssistantActions(response.actions)
      setMessages((m) => [...m, {
        role: 'assistant', content: response.text, source: response.source,
      }])
      setChips(response.suggestions?.length ? response.suggestions : DEFAULT_SUGGESTIONS)
    } catch (err) {
      setError(err.message || 'The assistant is unavailable.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="assistant-float">
      <AnimatePresence>
        {open && (
          <motion.section
            className="assistant-panel"
            aria-label="AI route assistant"
            initial={{ opacity: 0, y: 18, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 18, scale: 0.96 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="assistant-heading">
              <div className="assistant-title"><MessageCircle size={14} /><span>Q Route AI</span></div>
              <span className="assistant-status"><Sparkles size={11} /> AI</span>
              <button className="assistant-close" type="button" onClick={() => setOpen(false)} aria-label="Close Q Route AI" title="Close"><X size={15} /></button>
            </div>

            <div className="assistant-thread" aria-live="polite" ref={threadRef}>
              {!messages.length && !busy && (
                <div className="assistant-empty">
                  <strong>Ask me about the road ahead.</strong>
                  <span>I read the forecast, the agent&apos;s decision and the live traffic layer directly — every figure I give you is measured, not guessed.</span>
                </div>
              )}
              {messages.map((message, index) => (message.note ? (
                <RobotNotice key={message.id} message={message} demoMode={demoMode}
                             connected={connected} onAct={act} />
              ) : (
                <div key={`${message.role}-${index}`} className={`assistant-message ${message.role}`}>
                  {message.content}
                  {message.role === 'assistant' && message.source && (
                    <span className="assistant-provenance">
                      {SOURCE_LABEL[message.source] || message.source}
                    </span>
                  )}
                </div>
              )))}
              {busy && <div className="assistant-message assistant"><Loader2 size={13} className="spin" /> Checking the live route data...</div>}
            </div>

            <div className="assistant-suggestions">
              {chips.map((suggestion) => (
                <button key={suggestion} type="button" disabled={busy} onClick={() => submit(suggestion)}>
                  {suggestion}
                </button>
              ))}
            </div>

            {error && <p className="assistant-error">{error}</p>}
            <form className="assistant-composer" onSubmit={(event) => { event.preventDefault(); submit() }}>
              {/* Enter is handled here rather than left to the form. Implicit
                  submission clicks the default submit button, and that button
                  is disabled while the draft is empty — so a keystroke landing
                  before React re-enables it is silently swallowed. */}
              <input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    submit(event.currentTarget.value)
                  }
                }}
                placeholder="Ask about congestion, rerouting, or your ETA..."
                aria-label="Ask the assistant about your route"
                disabled={busy}
              />
              <button className="icon-btn" type="submit" aria-label="Send message" title="Send message" disabled={busy || !draft.trim()}><Send size={15} /></button>
            </form>
          </motion.section>
        )}
      </AnimatePresence>

      <AssistantRobot busy={busy} open={open} alerting={alerting}
                      onClick={() => setOpen((value) => !value)} />
    </div>
  )
}
