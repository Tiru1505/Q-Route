import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Eye,
  EyeOff,
  Lock,
  Mail,
  User,
} from 'lucide-react'

const MESSAGES = {
  idle: 'Hi there! 👋',
  name: 'What is your full name? 🖋️',
  email: 'Enter your email address 📧',
  password: 'Turning around! Your password is 100% private 🙈🔒',
  email2: 'Welcome back! Good to see you 😊',
  password2: 'Turning around! Your password is 100% private 🙈🔒',
}

export function Robot({ turned }) {
  const robotZoneRef = useRef(null)
  const leftEyeRef = useRef(null)
  const rightEyeRef = useRef(null)

  useEffect(() => {
    const handleMouseMove = (event) => {
      if (!robotZoneRef.current) return

      const rect = robotZoneRef.current.getBoundingClientRect()
      const cx = rect.left + rect.width / 2
      const cy = rect.top + rect.height / 2
      const dx = Math.max(-1, Math.min(1, (event.clientX - cx) / 220))
      const dy = Math.max(-1, Math.min(1, (event.clientY - cy) / 220))
      const transform = `translate(${dx * 3}px, ${dy * 2}px)`

      if (leftEyeRef.current) leftEyeRef.current.style.transform = transform
      if (rightEyeRef.current) rightEyeRef.current.style.transform = transform
    }

    document.addEventListener('mousemove', handleMouseMove)
    return () => document.removeEventListener('mousemove', handleMouseMove)
  }, [])

  return (
    <div ref={robotZoneRef} className="qro-robot-zone">
      <motion.div className={`qro-robot ${turned ? 'turned' : ''}`}>
        <div className="qro-robot-face">
          <div className="qro-antenna"><span /></div>
          <div className="qro-robot-head">
            <div className="qro-visor">
              <span ref={leftEyeRef} className="qro-eye" />
              <span ref={rightEyeRef} className="qro-eye" />
            </div>
          </div>
          <div className="qro-ear qro-ear-left" />
          <div className="qro-ear qro-ear-right" />
          <div className="qro-robot-body">
            <div className="qro-bolt qro-bolt-left" />
            <div className="qro-bolt qro-bolt-right" />
            <div className="qro-body-panel">QRO</div>
          </div>
        </div>

        <div className="qro-robot-back">
          <div className="qro-antenna"><span /></div>
          <div className="qro-robot-head">
            <div className="qro-headband" />
          </div>
          <div className="qro-ear qro-ear-left" />
          <div className="qro-ear qro-ear-right" />
          <div className="qro-robot-body">
            <div className="qro-bolt qro-bolt-left" />
            <div className="qro-bolt qro-bolt-right" />
            <div className="qro-body-panel">QRO</div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}


function AnimatedField({
  type = 'text',
  value,
  onChange,
  placeholder,
  icon,
  field,
  showPassword,
  setShowPassword,
}) {
  const [focused, setFocused] = useState(false)
  const [bubble, setBubble] = useState('')

  useEffect(() => {
    if (focused) {
      setBubble(MESSAGES[field])
    }
  }, [focused, field])

  return (
    <div className="qro-animated-field">

      <label>
        {field === 'name'
          ? 'Full Name'
          : field === 'email' || field === 'email2'
            ? 'Email Address'
            : 'Password'}
      </label>

      <div
        className={`qro-input-wrap ${
          focused ? 'focused' : ''
        }`}
      >

        {icon}

        <input
          type={
            field.startsWith('password')
              ? showPassword
                ? 'text'
                : 'password'
              : type
          }
          value={value}
          placeholder={placeholder}
          onChange={onChange}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
        />

        {field.startsWith('password') && (
          <button
            type="button"
            className="qro-eye-toggle"
            onClick={() =>
              setShowPassword((value) => !value)
            }
          >
            {showPassword ? (
              <EyeOff size={17} />
            ) : (
              <Eye size={17} />
            )}
          </button>
        )}

      </div>

    </div>
  )
}


export default function AnimatedAuthForm({
  mode,
  setMode,
  name,
  email,
  password,
  setName,
  setEmail,
  setPassword,
  showPassword,
  setShowPassword,
  onSubmit,
  busy,
}) {

  const [turned, setTurned] = useState(false)

  const [bubble, setBubble] = useState(
    mode === 'signin'
      ? MESSAGES.email2
      : MESSAGES.idle
  )

  useEffect(() => {
    setTurned(false)

    setBubble(
      mode === 'signin'
        ? MESSAGES.email2
        : MESSAGES.idle
    )
  }, [mode])

  const handlePasswordFocus = () => {
    setTurned(true)

    setBubble(
      mode === 'signin'
        ? MESSAGES.password2
        : MESSAGES.password
    )
  }

  const handleEmailFocus = () => {
    setTurned(false)

    setBubble(
      mode === 'signin'
        ? MESSAGES.email2
        : MESSAGES.email
    )
  }

  const handleNameFocus = () => {
    setTurned(false)
    setBubble(MESSAGES.name)
  }

  return (
    <div className="qro-auth-animation">

      {/* ===============================================
          HEADLINE
      =============================================== */}

      <div className="qro-animation-headline">

        <h1>
          <span className="qro-headline-second">
            Q Route
            <span className="qro-type-cursor" />
          </span>
        </h1>

      </div>


      {/* ===============================================
          SPEECH BUBBLE
      =============================================== */}

      <AnimatePresence mode="wait">

        <motion.div
          key={bubble}
          className="qro-speech-bubble"
          initial={{
            opacity: 0,
            y: 8,
            scale: 0.95,
          }}
          animate={{
            opacity: 1,
            y: 0,
            scale: 1,
          }}
          exit={{
            opacity: 0,
            y: -5,
            scale: 0.96,
          }}
          transition={{
            duration: 0.22,
          }}
        >
          {bubble}
        </motion.div>

      </AnimatePresence>


      {/* ===============================================
          ROBOT
      =============================================== */}

      <Robot turned={turned} />


      {/* ===============================================
          FORM
      =============================================== */}

      <motion.div
        className="qro-animation-form"
        initial={{
          opacity: 0,
          y: 20,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        transition={{
          duration: 0.6,
          delay: 0.2,
        }}
      >

        <form onSubmit={onSubmit}>

          <AnimatePresence mode="wait">

            <motion.div
              key={mode}
              initial={{
                opacity: 0,
                x: mode === 'signin' ? 25 : -25,
              }}
              animate={{
                opacity: 1,
                x: 0,
              }}
              exit={{
                opacity: 0,
                x: mode === 'signin' ? -25 : 25,
              }}
              transition={{
                duration: 0.35,
              }}
            >

              {mode === 'signup' && (
                <div
                  onFocus={handleNameFocus}
                >
                  <AnimatedField
                    field="name"
                    value={name}
                    onChange={(e) =>
                      setName(e.target.value)
                    }
                    placeholder="e.g. Your Name"
                    icon={<User size={16} />}
                    showPassword={false}
                    setShowPassword={setShowPassword}
                  />
                </div>
              )}


              <div
                onFocus={handleEmailFocus}
              >
                <AnimatedField
                  field={
                    mode === 'signin'
                      ? 'email2'
                      : 'email'
                  }
                  type="email"
                  value={email}
                  onChange={(e) =>
                    setEmail(e.target.value)
                  }
                  placeholder="you@example.com"
                  icon={<Mail size={16} />}
                  showPassword={showPassword}
                  setShowPassword={setShowPassword}
                />
              </div>


              <div
                onFocus={handlePasswordFocus}
              >
                <AnimatedField
                  field={
                    mode === 'signin'
                      ? 'password2'
                      : 'password'
                  }
                  value={password}
                  onChange={(e) =>
                    setPassword(e.target.value)
                  }
                  placeholder="At least 4 characters"
                  icon={<Lock size={16} />}
                  showPassword={showPassword}
                  setShowPassword={setShowPassword}
                />
              </div>


              <motion.button
                type="submit"
                className="qro-animated-submit"
                disabled={busy}
                whileHover={{
                  scale: 1.02,
                }}
                whileTap={{
                  scale: 0.97,
                }}
              >

                {busy
                  ? 'Processing…'
                  : mode === 'signin'
                    ? 'Sign In'
                    : 'Create Account'}

                <span>→</span>

              </motion.button>

            </motion.div>

          </AnimatePresence>

        </form>


        <div className="qro-animation-switch">

          {mode === 'signin' ? (
            <>
              Don't have an account?

              <button
  type="button"
  onClick={() => {
    setMode('signup')
    setBubble(MESSAGES.idle)
  }}
>
  Register
</button>
            </>
          ) : (
            <>
              Already have an account?

              <button
  type="button"
  onClick={() => {
    setMode('signin')
    setBubble(MESSAGES.email2)
  }}
>
  Sign In
</button>
            </>
          )}

        </div>

      </motion.div>

    </div>
  )
}