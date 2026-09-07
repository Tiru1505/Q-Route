import React, { Suspense, lazy } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import Sidebar from './components/Sidebar'
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

const Dashboard = lazy(() => import('./pages/Dashboard'))
const RouteOptimizer = lazy(() => import('./pages/RouteOptimizer'))
const LiveTraffic = lazy(() => import('./pages/LiveTraffic'))
const Analytics = lazy(() => import('./pages/Analytics'))
const Benchmark = lazy(() => import('./pages/Benchmark'))
const Alerts = lazy(() => import('./pages/Alerts'))
const History = lazy(() => import('./pages/History'))
const Settings = lazy(() => import('./pages/Settings'))

const pageMotion = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.26, ease: [0.22, 1, 0.36, 1] },
}

export default function App() {
  const location = useLocation()
  const { user } = useApp()

  // Unauthenticated users only ever see the sign-in screen first.
  if (!user) {
    return <Login />
  }

  return (
    <AppErrorBoundary>
      <div className="app">
        <Sidebar />
        <div className="main">
          <Navbar />
          <Suspense fallback={<LoadingScreen />}>
            <AnimatePresence mode="wait">
              <motion.div key={location.pathname} className="page" {...pageMotion}>
                <Routes location={location}>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/optimizer" element={<RouteOptimizer />} />
                  <Route path="/traffic" element={<LiveTraffic />} />
                  <Route path="/analytics" element={<Analytics />} />
                  <Route path="/benchmark" element={<Benchmark />} />
                  <Route path="/alerts" element={<Alerts />} />
                  <Route path="/history" element={<History />} />
                  <Route path="/settings" element={<Settings />} />
                  <Route path="*" element={<Dashboard />} />
                </Routes>
              </motion.div>
            </AnimatePresence>
          </Suspense>
          <AssistantPanel />
        </div>
      </div>
    </AppErrorBoundary>
  )
}
