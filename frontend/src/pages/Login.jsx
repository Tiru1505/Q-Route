import { useState } from 'react'
import { motion } from 'framer-motion'
import AnimatedAuthForm from '../components/AnimatedAuthForm'
import {
  ArrowRight, Atom, Bell, Eye, EyeOff, GitBranch, Loader2, Lock, Mail,
  ShieldAlert, User, Zap,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../store/AppContext'
import GoogleSignInButton from '../components/GoogleSignInButton'
import { SYSTEM_STATUS } from '../data/mockData'
import * as api from '../services/api'

const MIN_PASSWORD = 8

/**
 * Three doors, one account system.
 *
 *   Sign In            any account; the server's answer decides where you land
 *   Register as User   name, email, password (twice) — always a USER account
 *   Admin Access       a sign-in that only admits accounts the server says
 *                      are admins. There is no admin registration: admin
 *                      accounts are issued by whoever runs the server.
 *
 * Nothing on this page decides a role. It sends credentials and shows what
 * the server returned.
 */
export default function Login({ initialMode = 'signin' }) {
  const { signIn, register, completeSignIn, sessionNote } = useApp()
  const navigate = useNavigate()

  const [mode, setMode] = useState(initialMode) // 'signin' | 'signup' | 'admin'
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  /** The Admin tab admits admins only; anyone else is told, and not signed in. */
  const admitAdminOnly = (session) => {
    if (session?.user?.role !== 'admin') {
      setError('This account does not have admin access. Use the Sign In tab.')
      return false
    }
    completeSignIn(session)
    return true
  }

  const submit = async (e) => {
    e.preventDefault()
    setError(null)

    if (mode === 'signup' && !name.trim()) {
      setError('Please enter your name.')
      return
    }
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
      setError('Enter a valid email address.')
      return
    }
    if (mode === 'signup') {
      if (password.length < MIN_PASSWORD) {
        setError(`Use a password of at least ${MIN_PASSWORD} characters.`)
        return
      }
      if (password !== confirmPassword) {
        setError('The two passwords do not match.')
        return
      }
    } else if (!password) {
      setError('Enter your password.')
      return
    }

    setBusy(true)
    try {
      if (mode === 'signup') {
        await register({ name: name.trim(), email: email.trim(), password })
      } else if (mode === 'admin') {
        if (api.isMockMode()) {
          setError('Admin access needs the server; offline mode has no admins.')
          return
        }
        admitAdminOnly(await api.loginAccount({ email: email.trim(), password }))
      } else {
        await signIn({ email: email.trim(), password })
      }
    } catch (err) {
      setError(err?.message && err.status !== 0
        ? err.message
        : 'Cannot reach the Q Route server. Is the backend running?')
    } finally {
      setBusy(false)
    }
  }

  const switchMode = (newMode) => {
    setMode(newMode)
    setError(null)
    setConfirmPassword('')
    // Keep the address honest about which door is open.
    navigate(newMode === 'signup' ? '/register' : '/login', { replace: true })
  }

  return (
    <div className="login">
      {/* Full-screen animated background */}
      <div className="login-brand">
        <div className="qro-network" aria-hidden="true">

  {/* Ambient glow */}
  <div className="qro-network-glow" />

  <svg
    className="qro-network-svg"
    viewBox="0 0 800 700"
    preserveAspectRatio="xMidYMid slice"
  >

    {/* Road network */}
    <g className="qro-roads">

      <motion.path
        d="M80 150 L220 90 L390 160 L560 90 L730 170"
        pathLength="1"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 0.65 }}
        transition={{ duration: 2, ease: 'easeInOut' }}
      />

      <motion.path
        d="M70 350 L210 270 L390 320 L540 240 L740 350"
        pathLength="1"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 0.55 }}
        transition={{ duration: 2.2, delay: 0.3, ease: 'easeInOut' }}
      />

      <motion.path
        d="M110 560 L250 450 L400 510 L570 420 L720 540"
        pathLength="1"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 0.5 }}
        transition={{ duration: 2.3, delay: 0.5, ease: 'easeInOut' }}
      />

      {/* Vertical roads */}
      <motion.path
        d="M220 90 L210 270 L250 450"
        pathLength="1"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.8, delay: 0.8 }}
      />

      <motion.path
        d="M390 160 L390 320 L400 510"
        pathLength="1"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.8, delay: 1 }}
      />

      <motion.path
        d="M560 90 L540 240 L570 420"
        pathLength="1"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.8, delay: 1.2 }}
      />

    </g>

    {/* Animated optimal route */}
    <motion.path
      className="qro-optimal-route"
      d="M80 150 L220 90 L390 160 L540 240 L570 420 L720 540"
      pathLength="1"
      initial={{ pathLength: 0, opacity: 0 }}
      animate={{
        pathLength: [0, 1, 1],
        opacity: [0, 0.55, 0.55],
      }}
      transition={{
        duration: 5,
        delay: 1.8,
        repeat: Infinity,
        repeatDelay: 2,
        ease: 'easeInOut',
      }}
    />

    {/* Network nodes */}
    {[
      [80, 150],
      [220, 90],
      [390, 160],
      [560, 90],
      [730, 170],
      [70, 350],
      [210, 270],
      [390, 320],
      [540, 240],
      [740, 350],
      [110, 560],
      [250, 450],
      [400, 510],
      [570, 420],
      [720, 540],
    ].map(([cx, cy], i) => (
      <motion.g
        key={`${cx}-${cy}`}
        initial={{ opacity: 0, scale: 0 }}
        animate={{
          opacity: [0.35, 0.9, 0.35],
          scale: [0.9, 1.15, 0.9],
        }}
        transition={{
          duration: 2.5 + (i % 3) * 0.5,
          delay: 1 + i * 0.08,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        style={{ transformOrigin: `${cx}px ${cy}px` }}
      >
        <circle
          cx={cx}
          cy={cy}
          r="4"
          className="qro-node"
        />

        <circle
          cx={cx}
          cy={cy}
          r="10"
          className="qro-node-ring"
        />
      </motion.g>
    ))}

    {/* Moving traffic particles */}
    <circle className="qro-particle qro-particle-one" r="5">
      <animateMotion
        dur="5s"
        repeatCount="indefinite"
        path="M80 150 L220 90 L390 160 L540 240 L570 420 L720 540"
      />
    </circle>

    <circle className="qro-particle qro-particle-two" r="4">
      <animateMotion
        dur="6.5s"
        begin="1.5s"
        repeatCount="indefinite"
        path="M70 350 L210 270 L390 320 L540 240 L740 350"
      />
    </circle>

    <circle className="qro-particle qro-particle-three" r="3">
      <animateMotion
        dur="7s"
        begin="3s"
        repeatCount="indefinite"
        path="M110 560 L250 450 L400 510 L570 420 L720 540"
      />
    </circle>

  </svg>

</div>
      </div>

      {/* -------------------------------------------------- form panel */}

<div className="login-form-side login-form-centered">
  <motion.div
    className="login-card"
    initial={{ opacity: 0, y: 18 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{
      duration: 0.44,
      delay: 0.1,
      ease: [0.22, 1, 0.36, 1],
    }}
  >
    <div className="qro-mode-tabs qro-mode-tabs-3" role="tablist" aria-label="How to sign in">
      <button
        className={mode === 'signin' ? 'active' : ''}
        onClick={() => switchMode('signin')}
        type="button"
        role="tab"
        aria-selected={mode === 'signin'}
      >
        Sign In
      </button>

      <button
        className={mode === 'signup' ? 'active' : ''}
        onClick={() => switchMode('signup')}
        type="button"
        role="tab"
        aria-selected={mode === 'signup'}
      >
        Register as User
      </button>

      <button
        className={mode === 'admin' ? 'active' : ''}
        onClick={() => switchMode('admin')}
        type="button"
        role="tab"
        aria-selected={mode === 'admin'}
      >
        <ShieldAlert size={12} /> Admin Access
      </button>
    </div>

    {sessionNote && <p className="login-auth-note" role="status">{sessionNote}</p>}

    {mode === 'admin' && (
      <p className="login-admin-note">
        For the traffic control room. Admin accounts are issued by whoever runs
        the Q Route server, so there is no admin sign-up.
      </p>
    )}

    <AnimatedAuthForm
      mode={mode}
      setMode={switchMode}
      name={name}
      email={email}
      password={password}
      setName={setName}
      setEmail={setEmail}
      setPassword={setPassword}
      showPassword={showPassword}
      setShowPassword={setShowPassword}
      onSubmit={submit}
      busy={busy}
      confirmPassword={confirmPassword}
      setConfirmPassword={setConfirmPassword}
      minPassword={MIN_PASSWORD}
      submitLabel={mode === 'admin' ? 'Sign in as admin' : null}
    />

    <div className="login-divider">or</div>

    <GoogleSignInButton
      onError={setError}
      onVerified={mode === 'admin' ? admitAdminOnly : undefined}
    />

    {error && <p className="login-auth-error" role="status">{error}</p>}

    {/* Credentials go to /api/auth/*: the server hashes passwords (PBKDF2),
        issues a signed session, and decides the role. */}

    <p
      style={{
        textAlign: 'center',
        fontSize: 10.5,
        color: 'var(--text-faint)',
        marginTop: 18,
      }}
    >
      Q Route {SYSTEM_STATUS.version} · Problem Statement 26137
    </p>
  </motion.div>
  </div>

</div>
  )
}