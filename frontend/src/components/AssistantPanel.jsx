import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Loader2, MessageCircle, Send, Sparkles, X } from 'lucide-react'
import { useApp } from '../store/AppContext'
import * as api from '../services/api'
import robotImage from '../assets/q-route-ai-robot.png'

const suggestions = [
  'Find a route from HITEC City to Charminar',
  'Can you find another way?',
  'Why is this route better?',
]

function AssistantRobot({ busy, open, onClick }) {
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
      className={`assistant-float-button ${near ? 'is-near' : ''} ${busy ? 'is-thinking' : ''}`}
      type="button"
      onClick={onClick}
      aria-label="Ask Q Route AI"
      aria-expanded={open}
      title="Ask Q Route AI"
    >
      <span className="assistant-pulse" aria-hidden="true" />
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
  const { start, end, selectedRoute, routes, segments, incidents, applyAssistantActions } = useApp()
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(false)

  async function submit(text = draft) {
    const content = text.trim()
    if (!content || busy) return
    const nextMessages = [...messages, { role: 'user', content }]
    setMessages(nextMessages)
    setDraft('')
    setError(null)
    setBusy(true)
    try {
      const response = await api.assistantChat({
        messages: nextMessages,
        context: {
          start,
          destination: end,
          selected_route: selectedRoute,
          current_route: selectedRoute,
          routes,
          traffic: { segments, incidents },
        },
      })
      applyAssistantActions(response.actions)
      setMessages([...nextMessages, { role: 'assistant', content: response.message }])
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

            <div className="assistant-thread" aria-live="polite">
              {!messages.length && (
                <div className="assistant-empty">
                  <strong>Ask anything about your route.</strong>
                  <span>I can understand locations, preferences, traffic, alternatives, and the route currently on your map.</span>
                </div>
              )}
              {messages.map((message, index) => (
                <div key={`${message.role}-${index}`} className={`assistant-message ${message.role}`}>
                  {message.content}
                </div>
              ))}
              {busy && <div className="assistant-message assistant"><Loader2 size={13} className="spin" /> Checking the live route data...</div>}
            </div>

            {!messages.length && (
              <div className="assistant-suggestions">
                {suggestions.map((suggestion) => <button key={suggestion} type="button" onClick={() => submit(suggestion)}>{suggestion}</button>)}
              </div>
            )}

            {error && <p className="assistant-error">{error}</p>}
            <form className="assistant-composer" onSubmit={(event) => { event.preventDefault(); submit() }}>
              <input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Ask anything about your route..." aria-label="Ask anything about your route" disabled={busy} />
              <button className="icon-btn" type="submit" aria-label="Send message" title="Send message" disabled={busy || !draft.trim()}><Send size={15} /></button>
            </form>
          </motion.section>
        )}
      </AnimatePresence>

      <AssistantRobot busy={busy} open={open} onClick={() => setOpen((value) => !value)} />
    </div>
  )
}
