import { STRINGS } from './strings'

/**
 * Translation, in about thirty lines.
 *
 * No i18n library: this app needs one dictionary, three languages and a
 * fallback, and a library would add a build dependency and a second way of
 * doing things for no gain. `t('trip.eta')` returns the phrase; a key with no
 * translation in the chosen language falls back to English, so a half-finished
 * language is readable rather than full of blanks.
 *
 * Placeholders are named — `t('history.switches', { n: 2 })` — because word
 * order differs between these languages and positional holes cannot move.
 */

export const LANGUAGES = [
  { code: 'en', label: 'English', english: 'English' },
  { code: 'hi', label: 'हिन्दी', english: 'Hindi' },
  { code: 'te', label: 'తెలుగు', english: 'Telugu' },
]

export const DEFAULT_LANGUAGE = 'en'
export const LANGUAGE_CODES = LANGUAGES.map((l) => l.code)

export const isLanguage = (code) => LANGUAGE_CODES.includes(code)

/** The stored choice, or the browser's language when it is one we speak. */
export function initialLanguage() {
  try {
    const saved = localStorage.getItem('qro.language')
    if (isLanguage(saved)) return saved
  } catch { /* storage blocked — fall through to the browser's own setting */ }
  const preferred = (navigator.languages || [navigator.language || ''])
    .map((tag) => String(tag).split('-')[0])
    .find(isLanguage)
  return preferred || DEFAULT_LANGUAGE
}

export function translate(language, key, vars) {
  const entry = STRINGS[key]
  if (!entry) {
    // A key with no entry is a bug in the calling component, not something to
    // hide: show the key so it is caught in review rather than in a demo.
    if (import.meta.env.DEV) console.warn(`i18n: no string for "${key}"`)
    return key
  }
  let text = entry[language] ?? entry[DEFAULT_LANGUAGE] ?? key
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      text = text.replaceAll(`{${name}}`, String(value))
    }
  }
  return text
}
