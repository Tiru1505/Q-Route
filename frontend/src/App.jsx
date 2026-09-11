import React, { Suspense, lazy } from 'react'
import { Link, Navigate, Route, Routes, useLocation, useOutlet } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { ShieldAlert } from 'lucide-react'
import Sidebar, { NAV_ITEMS, USER_NAV_ITEMS } from './components/Sidebar'
import Navbar from './components/Navbar'
import LoadingScreen from './components/LoadingScreen'
import AssistantPanel from './components/AssistantPanel'
import { useApp } from './store/AppContext'
import Login from './pages/Login'

class AppErrorBoundary extends React.Component {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  handleRetry = () => {
    this.setState({ failed: false })
  }

  render() {
    if (this.state.failed) {
      return (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          minHeight: '100vh', padding: 24,
          background: 'var(--bg, #0a0a0f)',
        }}>
          <div className="card" style={{
            maxWidth: 420, textAlign: 'center', padding: '32px 28px',
            borderColor: 'rgba(239,68,68,.3)',
          }}>
            <strong style={{ fontSize: 15, display: 'block', marginBottom: 8 }}>
              Q Route could not render this view.
            </strong>
            <p style={{ fontSize: 12.5, color: 'var(--text-dim)', marginBottom: 16 }}>
              An unexpected error occurred. Your data is safe — try again or refresh the page.
            </p>
            <button className="btn btn-primary" onClick={this.handleRetry}
              style={{ marginRight: 8 }}>
              Try Again
            </button>
            <button className="btn" onClick={() => window.location.reload()}>
              Refresh Page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

// The admin console — every page the app had before roles, unchanged.
const Dashboard = lazy(() => import('./pages/Dashboard'))
const LiveTraffic = lazy(() => import('./pages/LiveTraffic'))
const Analytics = lazy(() => import('./pages/Analytics'))
const RoadVision = lazy(() => import('./pages/RoadVision'))
const Benchmark = lazy(() => import('./pages/Benchmark'))
const Alerts = lazy(() => import('./pages/Alerts'))
const History = lazy(() => import('./pages/History'))
const Settings = lazy(() => import('./pages/Settings'))

// The driver's app.
const UserDashboard = lazy(() => import('./pages/user/UserDashboard'))
const TripHistory = lazy(() => import('./pages/user/TripHistory'))
const UserSettings = lazy(() => import('./pages/user/UserSettings'))

const pageMotion = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.26, ease: [0.22, 1, 0.36, 1] },
}

const homeFor = (user) => (user?.role === 'admin' ? '/admin/dashboard' : '/user/dashboard')

/**
 * Only this role's pages render. The check is for the interface; the server
 * refuses the same requests on its own (app/core/security.py), so a page
 * reached by editing the address still cannot do anything it should not.
 */
function RequireRole({ role, children }) {
  const { user } = useApp()
  if (user.role === role) return children
  // A user reaching for an admin page is told so; an admin opening the user
  // app is simply taken to their own dashboard.
  return role === 'admin'
    ? <Navigate to="/unauthorized" replace />
    : <Navigate to="/admin/dashboard" replace />
}

/** Sidebar + navbar + robot around a role's pages, with the page transition. */
function Shell({ items, variant, settingsPath }) {
  const location = useLocation()
  // useOutlet, frozen per route, so the exiting page keeps its own content
  // while it animates out instead of briefly showing the next one.
  const outlet = useOutlet()
  return (
    <div className="app">
      <Sidebar items={items} variant={variant} />
      <div className="main">
        <Navbar items={items} settingsPath={settingsPath} />
        <Suspense fallback={<LoadingScreen />}>
          <AnimatePresence mode="wait">
            <motion.div key={location.pathname} className="page" {...pageMotion}>
              {outlet}
            </motion.div>
          </AnimatePresence>
        </Suspense>
        {/* Listens rather than asks — the backend pushes when traffic on the
            active route deteriorates, and the robot delivers it. */}
        <AssistantPanel />
      </div>
    </div>
  )
}

function Unauthorized() {
  const { user } = useApp()
  return (
    <div className="unauthorized-page">
      <div className="card unauthorized-card" role="alert">
        <ShieldAlert size={26} style={{ color: 'var(--severe)' }} />
        <h1>Admins only</h1>
        <p>
          This page belongs to the admin console. You are signed in as
          {' '}<strong>{user?.email}</strong>, which is a user account.
        </p>
        <Link className="btn btn-primary" to={homeFor(user)}>Back to your dashboard</Link>
      </div>
    </div>
  )
}

// Paths from before roles existed, so old links and bookmarks still land.
const LEGACY = ['traffic', 'analytics', 'vision', 'benchmark', 'alerts', 'history', 'settings']
const USER_LEGACY = { history: '/user/history', settings: '/user/settings' }

export default function App() {
  const { user } = useApp()

  // Signed out: only the sign-in and registration screens exist. Any other
  // address shows sign-in and keeps the address, so it opens after signing in.
  if (!user) {
    return (
      <Routes>
        <Route path="/register" element={<Login initialMode="signup" />} />
        <Route path="/admin/*" element={<Login initialMode="admin" />} />
        <Route path="*" element={<Login />} />
      </Routes>
    )
  }

  const home = homeFor(user)
  return (
    <AppErrorBoundary>
      <Routes>
        <Route path="/" element={<Navigate to={home} replace />} />
        <Route path="/login" element={<Navigate to={home} replace />} />
        <Route path="/register" element={<Navigate to={home} replace />} />
        <Route path="/unauthorized" element={<Unauthorized />} />

        <Route
          path="/user"
          element={(
            <RequireRole role="user">
              <Shell items={USER_NAV_ITEMS} variant="user" settingsPath="/user/settings" />
            </RequireRole>
          )}
        >
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<UserDashboard />} />
          <Route path="history" element={<TripHistory />} />
          <Route path="settings" element={<UserSettings />} />
          <Route path="*" element={<Navigate to="dashboard" replace />} />
        </Route>

        <Route
          path="/admin"
          element={(
            <RequireRole role="admin">
              <Shell items={NAV_ITEMS} variant="admin" settingsPath="/admin/settings" />
            </RequireRole>
          )}
        >
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="traffic" element={<LiveTraffic />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="vision" element={<RoadVision />} />
          <Route path="benchmark" element={<Benchmark />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="history" element={<History />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="dashboard" replace />} />
        </Route>

        {LEGACY.map((page) => (
          <Route
            key={page}
            path={`/${page}`}
            element={(
              <Navigate
                replace
                to={user.role === 'admin' ? `/admin/${page}` : (USER_LEGACY[page] || home)}
              />
            )}
          />
        ))}
        <Route path="*" element={<Navigate to={home} replace />} />
      </Routes>
    </AppErrorBoundary>
  )
}
