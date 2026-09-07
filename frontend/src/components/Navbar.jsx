import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { Bell, LogOut, Moon, Settings as SettingsIcon, Sun, TriangleAlert } from 'lucide-react'
import { useApp } from '../store/AppContext'
import { NAV_ITEMS } from './Sidebar'
import { TRAFFIC_COLORS } from '../data/mockData'

/** Average congestion across all segments → a single city-wide status word. */
function cityStatus(segments) {
  if (!segments.length) return { label: 'Unknown', level: 'low' }
  const avg = segments.reduce((s, x) => s + x.congestion, 0) / segments.length
  if (avg < 0.3) return { label: 'Light traffic', level: 'low' }
  if (avg < 0.5) return { label: 'Moderate traffic', level: 'moderate' }
  if (avg < 0.7) return { label: 'Heavy traffic', level: 'heavy' }
  return { label: 'Severe congestion', level: 'severe' }
}

/**
 * Animated brand mark: a nucleus with an electron on an elliptical orbit.
 *
 * Drawn as inline SVG rather than shipped as an asset so it inherits the theme
 * tokens and costs no extra request. Motion is slow and continuous — a logo
 * that demands attention is a logo you stop noticing.
 */
function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 40 40" width="34" height="34">
        <defs>
          <linearGradient id="qrGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--blue)" />
            <stop offset="55%" stopColor="var(--cyan)" />
            <stop offset="100%" stopColor="var(--quantum)" />
          </linearGradient>
        </defs>

        <ellipse cx="20" cy="20" rx="15" ry="7" fill="none"
                 stroke="url(#qrGrad)" strokeWidth="1.6" opacity="0.75"
                 transform="rotate(-28 20 20)" />
        <ellipse cx="20" cy="20" rx="15" ry="7" fill="none"
                 stroke="url(#qrGrad)" strokeWidth="1.6" opacity="0.45"
                 transform="rotate(38 20 20)" />

        <circle cx="20" cy="20" r="4.6" fill="url(#qrGrad)" />
        <circle cx="20" cy="20" r="4.6" fill="none"
                stroke="var(--cyan)" strokeWidth="0.8" opacity="0.6">
          <animate attributeName="r" values="4.6;7.4;4.6" dur="3.4s"
                   repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.6;0;0.6" dur="3.4s"
                   repeatCount="indefinite" />
        </circle>

        <g transform="rotate(-28 20 20)">
          <circle r="2.3" fill="var(--quantum)">
            <animateMotion dur="4.2s" repeatCount="indefinite"
                           path="M 5,20 a 15,7 0 1,0 30,0 a 15,7 0 1,0 -30,0" />
          </circle>
        </g>
      </svg>
    </span>
  )
}

export default function Navbar() {
  const { alerts, dismissAlert, theme, setTheme, segments, user, signOut } = useApp()
  const [open, setOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const ref = useRef(null)
  const location = useLocation()
  const navigate = useNavigate()

  const current = NAV_ITEMS.find((n) =>
    n.end ? location.pathname === n.to : location.pathname.startsWith(n.to)
  )
  const status = cityStatus(segments)

  useEffect(() => {
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false)
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  useEffect(() => {
    const page = document.querySelector('.page')
    if (!page) return undefined

    const onScroll = () => setScrolled(page.scrollTop > 8)
    page.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    return () => page.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header className={`navbar${scrolled ? ' is-scrolled' : ''}`}>
      <div className="navbar-left">
        <BrandMark />
        <div className="navbar-brand-text">
          <strong>Q Route</strong>
          <span>QUANTUM ROUTE OPTIMIZER</span>
        </div>
        <span className="navbar-divider" aria-hidden="true" />
        <h2 className="navbar-page-title">{current?.label || 'Dashboard'}</h2>
      </div>

      <div className="navbar-right" ref={ref}>
        <div className="live-chip">
          <span className="dot pulse" style={{ background: 'currentColor' }} />
          <span>LIVE</span>
        </div>

        <div
          className="traffic-status-chip"
          title={`City-wide traffic status: ${status.label}`}
        >
          <span className="dot" style={{ background: TRAFFIC_COLORS[status.level] }} />
          <span>{status.label}</span>
        </div>

        <button
          className="icon-btn"
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>

        <button
          className="icon-btn"
          onClick={() => { setOpen((v) => !v); setMenuOpen(false) }}
          aria-label="Notifications"
        >
          <Bell size={16} />
          {alerts.length > 0 && <span className="badge-dot" />}
        </button>

        <button
          className="avatar"
          onClick={() => { setMenuOpen((v) => !v); setOpen(false) }}
          aria-label="Account menu"
          aria-expanded={menuOpen}
        >
          {user?.initials || 'QR'}
        </button>

        <AnimatePresence>
          {menuOpen && (
            <motion.div
              className="user-menu"
              initial={{ opacity: 0, y: -8, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.98 }}
              transition={{ duration: 0.16 }}
            >
              <div className="user-menu-head">
                <div className="avatar" style={{ cursor: 'default' }}>
                  {user?.initials}
                </div>
                <div style={{ minWidth: 0 }}>
                  <strong>{user?.name}</strong>
                  <span
                    style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                  >
                    {user?.email}
                  </span>
                </div>
              </div>

              {user?.guest && (
                <div
                  className="badge badge-yellow"
                  style={{ margin: '0 9px 7px', display: 'flex', justifyContent: 'center' }}
                >
                  Guest session
                </div>
              )}

              <button
                className="item"
                onClick={() => { setMenuOpen(false); navigate('/settings') }}
              >
                <SettingsIcon size={14} /> Settings
              </button>
              <button className="item danger" onClick={signOut}>
                <LogOut size={14} /> Sign out
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {open && (
            <motion.div
              className="notif-panel"
              initial={{ opacity: 0, y: -8, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.98 }}
              transition={{ duration: 0.18 }}
            >
              <div className="card-title" style={{ padding: '4px 8px', marginBottom: 4 }}>
                Notifications ({alerts.length})
              </div>
              {alerts.length === 0 ? (
                <div className="empty" style={{ padding: 24 }}>
                  <Bell size={22} />
                  <span style={{ fontSize: 12 }}>You're all caught up</span>
                </div>
              ) : (
                alerts.map((a) => (
                  <motion.div
                    key={a.id}
                    className="notif-item"
                    layout
                    exit={{ opacity: 0, x: 30 }}
                    onClick={() => dismissAlert(a.id)}
                  >
                    <TriangleAlert size={15} style={{ color: TRAFFIC_COLORS[a.severity], flexShrink: 0, marginTop: 2 }} />
                    <div style={{ minWidth: 0 }}>
                      <h5>{a.title}</h5>
                      <p>{a.location}</p>
                      <time>{a.time}</time>
                    </div>
                  </motion.div>
                ))
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </header>
  )
}
