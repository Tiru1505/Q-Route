import { STRINGS } from './strings'

/**
 * Translation, in about thirty lines.
 *
 * No i18n library: this app needs one dictionary, a list of languages and a
 * fallback, and a library would add a build dependency and a second way of
 * doing things for no gain. `t('trip.eta')` returns the phrase; a key with no
 * translation in the chosen language falls back to English, so a half-finished
 * language is readable rather than full of blanks.
 *
 * Placeholders are named — `t('history.switches', { n: 2 })` — because word
 * order differs between these languages and positional holes cannot move.
 *
 * TWO KINDS OF LANGUAGE
 * ---------------------
 * English, Hindi and Telugu were written for this app and live in strings.js,
 * one line per phrase so a gap is visible while reading. The other twenty —
 * the rest of India's scheduled languages — were translated by machine and
 * NOT checked by a native speaker. They live one file per language in
 * ./machine, are fetched only when chosen (twenty dictionaries are not worth
 * shipping to someone reading one), and the picker says plainly which is which.
 * Quality among them is uneven: expect the major languages to read well and
 * Bodo, Dogri, Santali, Manipuri and Kashmiri to contain mistakes.
 *
 * `rtl` marks the Perso-Arabic scripts. Only the text runs right to left —
 * the browser's own bidirectional handling does that — and the layout stays
 * as it is, so the map and panels are the same for everyone.
 */

export const LANGUAGES = [
  { code: 'en', label: 'English', english: 'English' },
  { code: 'hi', label: 'हिन्दी', english: 'Hindi' },
  { code: 'te', label: 'తెలుగు', english: 'Telugu' },

  { code: 'as', label: 'অসমীয়া', english: 'Assamese', machine: true },
  { code: 'bn', label: 'বাংলা', english: 'Bengali', machine: true },
  { code: 'brx', label: 'बड़ो', english: 'Bodo', machine: true },
  { code: 'doi', label: 'डोगरी', english: 'Dogri', machine: true },
  { code: 'gu', label: 'ગુજરાતી', english: 'Gujarati', machine: true },
  { code: 'kn', label: 'ಕನ್ನಡ', english: 'Kannada', machine: true },
  { code: 'ks', label: 'کٲشُر', english: 'Kashmiri', machine: true, rtl: true },
  { code: 'kok', label: 'कोंकणी', english: 'Konkani', machine: true },
  { code: 'mai', label: 'मैथिली', english: 'Maithili', machine: true },
  { code: 'ml', label: 'മലയാളം', english: 'Malayalam', machine: true },
  { code: 'mni', label: 'ꯃꯤꯇꯩꯂꯣꯟ', english: 'Manipuri', machine: true },
  { code: 'mr', label: 'मराठी', english: 'Marathi', machine: true },
  { code: 'ne', label: 'नेपाली', english: 'Nepali', machine: true },
  { code: 'or', label: 'ଓଡ଼ିଆ', english: 'Odia', machine: true },
  { code: 'pa', label: 'ਪੰਜਾਬੀ', english: 'Punjabi', machine: true },
  { code: 'sa', label: 'संस्कृतम्', english: 'Sanskrit', machine: true },
  { code: 'sat', label: 'ᱥᱟᱱᱛᱟᱲᱤ', english: 'Santali', machine: true },
  { code: 'sd', label: 'سنڌي', english: 'Sindhi', machine: true, rtl: true },
  { code: 'ta', label: 'தமிழ்', english: 'Tamil', machine: true },
  { code: 'ur', label: 'اردو', english: 'Urdu', machine: true, rtl: true },
]

export const DEFAULT_LANGUAGE = 'en'
export const LANGUAGE_CODES = LANGUAGES.map((l) => l.code)

const BY_CODE = Object.fromEntries(LANGUAGES.map((l) => [l.code, l]))

export const isLanguage = (code) => LANGUAGE_CODES.includes(code)
export const isMachine = (code) => !!BY_CODE[code]?.machine
export const isRtl = (code) => !!BY_CODE[code]?.rtl

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

/* ---------------------------------------------- machine-translated dictionaries */

const loaded = {}

/**
 * Fetch a machine-translated dictionary, once. Resolves immediately for the
 * three written into strings.js. Until it arrives, lookups fall back to
 * English, so the page is never blank while the file is on its way.
 */
export async function loadLanguage(code) {
  if (!isMachine(code) || loaded[code]) return
  const module = await import(`./machine/${code}.json`)
  loaded[code] = module.default
}

/** The raw template for a key, in the chosen language or else in English. */
function templateFor(language, key) {
  const entry = STRINGS[key]
  if (!entry) return null
  return entry[language] ?? loaded[language]?.[key] ?? entry[DEFAULT_LANGUAGE] ?? null
}

export function translate(language, key, vars) {
  let text = templateFor(language, key)
  if (text == null) {
    // A key with no entry is a bug in the calling component, not something to
    // hide: show the key so it is caught in review rather than in a demo.
    if (import.meta.env.DEV) console.warn(`i18n: no string for "${key}"`)
    return key
  }
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      text = text.replaceAll(`{${name}}`, String(value))
    }
  }
  return text
}

/**
 * Same lookup as `translate`, but stops short of stringifying the numbers:
 * it splits the raw template on its `{name}` placeholders and returns each
 * piece as plain text or a number, in the template's own order. Nothing here
 * assumes where the number sits — the template says so, whichever way a
 * language orders it — which is what lets callers animate the digits (e.g.
 * SlidingNumber) while still showing the translated unit word around them.
 */
export function translateSegments(language, key, vars) {
  const template = templateFor(language, key) ?? key
  if (!vars) return [{ text: template }]
  const segments = []
  let last = 0
  for (const match of template.matchAll(/\{(\w+)\}/g)) {
    if (match.index > last) segments.push({ text: template.slice(last, match.index) })
    segments.push({ name: match[1], number: vars[match[1]] })
    last = match.index + match[0].length
  }
  if (last < template.length) segments.push({ text: template.slice(last) })
  return segments
}
