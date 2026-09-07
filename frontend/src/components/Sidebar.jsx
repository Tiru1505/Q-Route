import { useCallback, useEffect, useRef, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity, BarChart3, Bell, ChevronLeft, ChevronRight, FlaskConical,
  History as HistoryIcon, LayoutDashboard, Menu, Pin, Route as RouteIcon,
  Settings as SettingsIcon, X,
} from 'lucide-react'
import { useApp } from '../store/AppContext'
import { SYSTEM_STATUS } from '../data/mockData'

export const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/optimizer', label: 'Route Optimizer', icon: RouteIcon },
  { to: '/traffic', label: 'Live Traffic', icon: Activity },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/benchmark', label: 'Benchmark', icon: FlaskConical },
  { to: '/alerts', label: 'Alerts', icon: Bell, showCount: true },
  { to: '/history', label: 'History', icon: HistoryIcon },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
]

export default function Sidebar() {
  const { collapsed, setCollapsed, alerts, theme } = useApp()
  const location = useLocation()
  const closeTimer = useRef(null)
  const [mobileOpen, setMobileOpen] = useState(false)

  /**
   * Fold behaviour: the sidebar opens on hover or focus and folds itself away
   * again shortly after you leave, so it is a slim icon rail while you work and
   * a full menu the moment you reach for it. The map is the point of this
   * screen, and a permanently expanded sidebar eats 244px of it.
   *
   * The pin button still wins: once pinned open, hovering away does nothing.
   * Auto-fold would be infuriating for someone who deliberately opened it.
   */
  const [pinned, setPinned] = useState(() => {
    try { return JSON.parse(localStorage.getItem('qro.sidebarPinned') ?? 'false') }
    catch { return false }
  })

  useEffect(() => {
    try { localStorage.setItem('qro.sidebarPinned', JSON.stringify(pinned)) } catch {}
  }, [pinned])

  const open = useCallback(() => {
    clearTimeout(closeTimer.current)
    setCollapsed(false)
  }, [setCollapsed])

  const scheduleClose = useCallback(() => {
    if (pinned) return
    clearTimeout(closeTimer.current)
    // Small delay so crossing a gap or overshooting the edge does not slam it
    // shut mid-gesture.
    closeTimer.current = setTimeout(() => setCollapsed(true), 450)
  }, [pinned, setCollapsed])

  // Fold once a destination is chosen — the click is the end of the gesture.
  useEffect(() => {
    if (!pinned) setCollapsed(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname])

  useEffect(() => () => clearTimeout(closeTimer.current), [])

  return (
    <>
      <aside
        className="sidebar"
        data-open={mobileOpen}
        data-collapsed={collapsed}
        data-pinned={pinned}
        onMouseEnter={open}
        onMouseLeave={scheduleClose}
        onFocusCapture={open}
        onBlurCapture={scheduleClose}
      >
        <div className="sidebar-head">
          <div className="logo-mark">QR</div>
          <AnimatePresence initial={false}>
            {!collapsed && (
              <motion.div
                className="logo-text"
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.2 }}
              >
                <strong>Quantum Route</strong>
                <span>Optimizer</span>
              </motion.div>
            )}
          </AnimatePresence>

          <button
            className="collapse-btn"
            onClick={() => {
              setPinned((p) => !p)
              setCollapsed(pinned)     // unpinning folds it away immediately
            }}
            aria-label={pinned ? 'Unpin sidebar' : 'Keep sidebar open'}
            title={pinned ? 'Unpin — fold automatically' : 'Pin sidebar open'}
          >
            {pinned ? <Pin size={12} /> : <ChevronRight size={13} />}
          </button>
          <button
            className="mobile-drawer-close"
            type="button"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation menu"
          >
            <X size={16} />
          </button>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end, showCount }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              title={collapsed ? label : undefined}
            >
              <Icon size={17} />
              {!collapsed && (
                <>
                  <span>{label}</span>
                  {showCount && alerts.length > 0 && (
                    <span className="nav-count">{alerts.length}</span>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {!collapsed && (
          <div className="sidebar-foot">
            <div className="row-between">
              <span>Theme</span>
              <span style={{ color: 'var(--text-dim)', textTransform: 'capitalize' }}>{theme}</span>
            </div>
            <div className="row-between">
              <span>Backend</span>
              <span
                className={`badge ${SYSTEM_STATUS.backend === 'live'
                  ? 'badge-green' : 'badge-yellow'}`}
                style={{ padding: '1px 7px' }}
              >
                {SYSTEM_STATUS.backend}
              </span>
            </div>
            <div className="row-between">
              <span>Version</span>
              <span className="mono" style={{ color: 'var(--text-dim)' }}>
                {SYSTEM_STATUS.version}
              </span>
            </div>
          </div>
        )}
      </aside>

      {/* Bottom navigation replaces the sidebar below 900px */}
      <nav className="mobile-nav">
        {NAV_ITEMS.slice(0, 5).map(({ to, label, icon: Icon, end }) => {
          const active = end ? location.pathname === to : location.pathname.startsWith(to)
          return (
            <NavLink key={to} to={to} end={end} className={active ? 'active' : ''}>
              <Icon size={18} />
              <span>{label.split(' ')[0]}</span>
            </NavLink>
          )
        })}
        <button
          className="mobile-more"
          type="button"
          onClick={() => {
            setMobileOpen((value) => !value)
            setCollapsed(false)
          }}
          aria-label="More navigation options"
          aria-expanded={mobileOpen}
        >
          <Menu size={18} />
          <span>More</span>
        </button>
      </nav>
    </>
  )
}
