import { useState } from 'react'
import { motion } from 'framer-motion'
import AnimatedAuthForm from '../components/AnimatedAuthForm'
import {
  ArrowRight, Atom, Bell, Eye, EyeOff, GitBranch, Loader2, Lock, Mail,
  ShieldAlert, User, Zap,
} from 'lucide-react'
import { useApp } from '../store/AppContext'
import { SYSTEM_STATUS } from '../data/mockData'

export default function Login() {
  const { signIn } = useApp()

  const [mode, setMode] = useState('signin') // 'signin' | 'signup'
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)


  // Fixed positions so the particles don't jump on every keystroke.
  

  const submit = async (e) => {
    e.preventDefault()
    setError(null)

    if (mode === 'signup' && !name.trim()) {
      setError('Please enter your name.')
      return
    }
    if (!/^\S+@\S+\.\S+$/.test(email)) {
      setError('Enter a valid email address.')
      return
    }
    if (password.length < 4) {
      setError('Password must be at least 4 characters.')
      return
    }

    setBusy(true)
    try {
      await signIn({ email, name: mode === 'signup' ? name.trim() : '' })
    } catch {
      setError('Sign-in failed. Please try again.')
    } finally {
      setBusy(false)
    }
  }
  const switchMode = (newMode) => {
  setMode(newMode)
  setError(null)
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
    <div className="qro-mode-tabs">
      <button
        className={mode === 'signin' ? 'active' : ''}
        onClick={() => switchMode('signin')}
        type="button"
      >
        Sign In
      </button>

      <button
        className={mode === 'signup' ? 'active' : ''}
        onClick={() => switchMode('signup')}
        type="button"
      >
        Register
      </button>
    </div>

    <AnimatedAuthForm
      mode={mode}
      setMode={setMode}
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
    />



    {error && <p className="login-auth-error" role="status">{error}</p>}

    {/* NOTE FOR DEVELOPERS (removed from the UI at the team's request):
        there is no auth backend. Nothing here validates a credential, and the
        password is never stored or transmitted — only a name/email/initials
        object goes into localStorage. Replace signIn() in store/AppContext.jsx
        with a real backend call before this is deployed anywhere public. */}

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