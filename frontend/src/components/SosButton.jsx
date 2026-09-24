import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Ambulance, Copy, Check, Phone, ShieldAlert, TriangleAlert, X } from 'lucide-react'
import { useApp } from '../store/AppContext'

/**
 * Emergency dialling for the driver.
 *
 * `tel:` hands the number to the phone's own dialler — nothing is placed from
 * here, nothing is sent anywhere, and no call is recorded. Opening the panel
 * takes one tap and dialling takes a second: a single stray tap on a moving
 * vehicle should not ring the police.
 *
 * The position shown is the BROWSER's real geolocation, asked for only when
 * the panel opens. It is deliberately not the simulated car on the map — a
 * demo position read out to an ambulance operator would be worse than no
 * position at all.
 */

const NUMBERS = [
  { key: 'all', dial: '112', labelKey: 'sos.all', icon: TriangleAlert, tone: 'brand' },
  { key: 'police', dial: '100', labelKey: 'sos.police', icon: ShieldAlert, tone: 'blue' },
  { key: 'ambulance', dial: '108', labelKey: 'sos.ambulance', icon: Ambulance, tone: 'severe' },
]

export default function SosButton() {
  const { t } = useApp()
  const [open, setOpen] = useState(false)
  const [fix, setFix] = useState(null)      // { lat, lon, accuracy } once located
  const [located, setLocated] = useState('idle')  // idle | locating | ok | denied
  const [copied, setCopied] = useState(false)
  const panelRef = useRef(null)

  // Asked for only while the panel is open: an emergency panel is the one place
  // a location prompt is expected, and the app never tracks position otherwise.
  useEffect(() => {
    if (!open || !navigator.geolocation) {
      if (open) setLocated('denied')
      return
    }
    setLocated('locating')
    let cancelled = false
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        if (cancelled) return
        setFix({ lat: coords.latitude, lon: coords.longitude, accuracy: coords.accuracy })
        setLocated('ok')
      },
      () => !cancelled && setLocated('denied'),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 },
    )
    return () => { cancelled = true }
  }, [open])

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const coords = fix ? `${fix.lat.toFixed(5)}, ${fix.lon.toFixed(5)}` : null

  const copy = useCallback(() => {
    if (!coords) return
    navigator.clipboard?.writeText(coords).then(
      () => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      },
      () => {},
    )
  }, [coords])

  return (
    <>
      <button
        type="button"
        className="sos-fab"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={t('sos.open')}
      >
        <Phone size={15} aria-hidden="true" />
        <span>SOS</span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            ref={panelRef}
            className="card sos-panel"
            role="dialog"
            aria-label={t('sos.title')}
            initial={{ opacity: 0, y: 10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="sos-head">
              <strong>{t('sos.title')}</strong>
              <button type="button" onClick={() => setOpen(false)} aria-label={t('sos.close')}>
                <X size={14} />
              </button>
            </div>
            <p className="sos-sub">{t('sos.subtitle')}</p>

            <div className="sos-numbers">
              {NUMBERS.map(({ key, dial, labelKey, icon: Icon, tone }) => (
                <a key={key} className="sos-dial" data-tone={tone} href={`tel:${dial}`}>
                  <Icon size={16} aria-hidden="true" />
                  <span>{t(labelKey)}</span>
                  <b>{dial}</b>
                </a>
              ))}
            </div>

            <div className="sos-where">
              {located === 'locating' && <small>{t('sos.locating')}</small>}
              {located === 'denied' && <small>{t('sos.locationDenied')}</small>}
              {located === 'ok' && coords && (
                <>
                  <small>{t('sos.location')}</small>
                  <div className="sos-coords">
                    <code className="mono">{coords}</code>
                    <button type="button" onClick={copy} aria-label={t('sos.copy')}>
                      {copied ? <Check size={12} /> : <Copy size={12} />}
                      {copied ? t('sos.copied') : t('sos.copy')}
                    </button>
                  </div>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
