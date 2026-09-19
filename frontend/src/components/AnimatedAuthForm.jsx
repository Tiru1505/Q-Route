import { useEffect, useRef, useState } from 'react'
import { useApp } from '../store/AppContext'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Eye,
  EyeOff,
  Lock,
  Mail,
  User,
} from 'lucide-react'

// What the robot says, by field. Keys rather than sentences: the bubble is
// translated like everything else on the page.
const MESSAGE_KEYS = {
  idle: 'auth.msgIdle',
  name: 'auth.msgName',
  email: 'auth.msgEmail',
  password: 'auth.msgPassword',
  email2: 'auth.msgWelcomeBack',
  password2: 'auth.msgPassword',
  passwordConfirm: 'auth.msgConfirm',
  admin: 'auth.msgAdmin',
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
  const { t } = useApp()
  const [focused, setFocused] = useState(false)
  const [bubble, setBubble] = useState('')

  useEffect(() => {
    if (focused) {
      setBubble(t(MESSAGE_KEYS[field]))
    }
  }, [focused, field, t])

  return (
    <div className="qro-animated-field">

      <label>
        {field === 'name'
          ? t('auth.fullName')
          : field === 'email' || field === 'email2'
            ? t('auth.emailAddress')
            : field === 'passwordConfirm'
              ? t('auth.confirmPassword')
              : t('auth.password')}
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
  confirmPassword = '',
  setConfirmPassword = () => {},
  submitLabel = null,
  minPassword = 8,
}) {
  const { t } = useApp()
  // Admin access is a sign-in with a different door, not a different form.
  const signinLike = mode !== 'signup'
  const greeting = mode === 'admin' ? t('auth.msgAdmin') : t('auth.msgWelcomeBack')

  const [turned, setTurned] = useState(false)

  const [bubble, setBubble] = useState(
    signinLike
      ? greeting
      : t('auth.msgIdle')
  )

  useEffect(() => {
    setTurned(false)

    setBubble(
      signinLike
        ? greeting
        : t('auth.msgIdle')
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode])

  const handlePasswordFocus = () => {
    setTurned(true)

    setBubble(t('auth.msgPassword'))
  }

  const handleEmailFocus = () => {
    setTurned(false)

    setBubble(
      signinLike
        ? greeting
        : t('auth.msgEmail')
    )
  }

  const handleNameFocus = () => {
    setTurned(false)
    setBubble(t('auth.msgName'))
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
                x: signinLike ? 25 : -25,
              }}
              animate={{
                opacity: 1,
                x: 0,
              }}
              exit={{
                opacity: 0,
                x: signinLike ? -25 : 25,
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
                    placeholder={t('auth.namePlaceholder')}
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
                    signinLike
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
                    signinLike
                      ? 'password2'
                      : 'password'
                  }
                  value={password}
                  onChange={(e) =>
                    setPassword(e.target.value)
                  }
                  placeholder={signinLike
                    ? t('auth.yourPassword')
                    : t('auth.passwordMin', { n: minPassword })}
                  icon={<Lock size={16} />}
                  showPassword={showPassword}
                  setShowPassword={setShowPassword}
                />
              </div>

              {mode === 'signup' && (
                <div onFocus={() => { setTurned(true); setBubble(MESSAGES.passwordConfirm) }}>
                  <AnimatedField
                    field="passwordConfirm"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder={t('auth.passwordAgain')}
                    icon={<Lock size={16} />}
                    showPassword={showPassword}
                    setShowPassword={setShowPassword}
                  />
                </div>
              )}


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
                  ? t('auth.processing')
                  : submitLabel || (signinLike ? t('login.signIn') : t('auth.createAccount'))}

                <span>→</span>

              </motion.button>

            </motion.div>

          </AnimatePresence>

        </form>


        <div className="qro-animation-switch">

          {mode === 'admin' ? (
            <>
              {t('auth.notAdmin')}

              <button
                type="button"
                onClick={() => setMode('signin')}
              >
                {t('auth.signInAsUser')}
              </button>
            </>
          ) : mode === 'signin' ? (
            <>
              {t('auth.noAccount')}

              <button
  type="button"
  onClick={() => {
    setMode('signup')
    setBubble(t('auth.msgIdle'))
  }}
>
  {t('auth.registerLink')}
</button>
            </>
          ) : (
            <>
              {t('auth.haveAccount')}

              <button
  type="button"
  onClick={() => {
    setMode('signin')
    setBubble(greeting)
  }}
>
  {t('login.signIn')}
</button>
            </>
          )}

        </div>

      </motion.div>

    </div>
  )
}