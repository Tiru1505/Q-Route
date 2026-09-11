import { useEffect, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { getAuthConfig, signInWithGoogle } from '../services/api'
import { useApp } from '../store/AppContext'

/**
 * "Continue with Google", for real.
 *
 * Google Identity Services draws the button and, when the user picks an
 * account, hands back a signed ID token. That token goes to /api/auth/google,
 * where the server checks Google's signature, that it was issued for this
 * app's client ID, that it has not expired and that the email is verified.
 * Only the user the server returns is signed in — the browser decides nothing.
 *
 * The button is Google's own rather than a styled copy: the ID-token flow is
 * started from Google's rendered button, and Google's branding terms expect it.
 *
 * With no client ID configured on the server, the old button stays, disabled,
 * with the reason beside it. A button that looks live and does nothing is the
 * failure this replaces.
 */

const GIS_SRC = 'https://accounts.google.com/gsi/client'
let gisLoading = null

function loadGis() {
  if (window.google?.accounts?.id) return Promise.resolve()
  if (!gisLoading) {
    gisLoading = new Promise((resolve, reject) => {
      const s = document.createElement('script')
      s.src = GIS_SRC
      s.async = true
      s.defer = true
      s.onload = () => resolve()
      s.onerror = () => {
        gisLoading = null
        reject(new Error('Could not load Google sign-in. Check the connection and try again.'))
      }
      document.head.appendChild(s)
    })
  }
  return gisLoading
}

function GoogleMark() {
  return (
    <svg className="login-google-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M21.35 12.23c0-.73-.07-1.43-.21-2.1H12v4h5.24a4.48 4.48 0 0 1-1.94 2.94v2.45h3.14c1.84-1.69 2.91-4.18 2.91-7.29Z" />
      <path fill="#34A853" d="M12 21.5c2.63 0 4.84-.87 6.45-2.36l-3.14-2.45c-.87.58-1.98.92-3.31.92-2.54 0-4.69-1.72-5.46-4.03H3.3v2.53A9.74 9.74 0 0 0 12 21.5Z" />
      <path fill="#FBBC05" d="M6.54 13.58A5.86 5.86 0 0 1 6.24 12c0-.55.1-1.09.3-1.58V7.89H3.3A9.5 9.5 0 0 0 2.25 12c0 1.48.36 2.88 1.05 4.11l3.24-2.53Z" />
      <path fill="#EA4335" d="M12 6.39c1.43 0 2.71.49 3.72 1.45l2.79-2.79C16.84 3.48 14.63 2.5 12 2.5a9.74 9.74 0 0 0-8.7 5.39l3.24 2.53C7.31 8.11 9.46 6.39 12 6.39Z" />
    </svg>
  )
}

export default function GoogleSignInButton({ onError }) {
  const { completeSignIn } = useApp()
  const holder = useRef(null)
  const onErrorRef = useRef(onError)
  onErrorRef.current = onError
  // loading | ready | verifying | off | failed
  const [state, setState] = useState('loading')
  const [note, setNote] = useState(null)

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const cfg = await getAuthConfig()
        if (!alive) return
        if (!cfg?.google?.enabled) {
          setState('off')
          setNote(cfg?.offline
            ? 'Google sign-in needs the backend, which is not running in offline mode.'
            : 'Google sign-in is not configured on the server yet (GOOGLE_CLIENT_ID).')
          return
        }
        await loadGis()
        if (!alive || !holder.current) return

        window.google.accounts.id.initialize({
          client_id: cfg.google.clientId,
          auto_select: false,
          cancel_on_tap_outside: true,
          ux_mode: 'popup',
          callback: async ({ credential }) => {
            setState('verifying')
            try {
              const { user } = await signInWithGoogle(credential)
              completeSignIn(user)
            } catch (err) {
              setState('ready')
              onErrorRef.current?.(err.message || 'Google sign-in failed.')
            }
          },
        })
        window.google.accounts.id.renderButton(holder.current, {
          theme: 'filled_black',
          size: 'large',
          text: 'continue_with',
          shape: 'rectangular',
          logo_alignment: 'left',
          // GIS accepts 200-400 px and does not follow its container.
          width: Math.max(200, Math.min(holder.current.offsetWidth || 320, 400)),
        })
        setState('ready')
      } catch (err) {
        if (!alive) return
        setState('failed')
        setNote(err.message || 'Google sign-in is unavailable.')
      }
    })()
    return () => { alive = false }
  }, [completeSignIn])

  const live = state === 'ready' || state === 'verifying'

  return (
    <div className="google-signin">
      {/* Always mounted: Google renders its button into this element. */}
      <div ref={holder} className="google-signin-slot" hidden={!live} />

      {state === 'verifying' && (
        <p className="google-signin-note"><Loader2 size={12} className="spin" /> Verifying with Google…</p>
      )}

      {!live && (
        <>
          <button className="btn btn-block login-google-btn" type="button" disabled>
            {state === 'loading' ? <Loader2 size={15} className="spin" /> : <GoogleMark />}
            Continue with Google
          </button>
          {note && <p className="google-signin-note">{note}</p>}
        </>
      )}
    </div>
  )
}
