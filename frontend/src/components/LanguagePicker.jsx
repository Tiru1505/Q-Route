import { Languages, TriangleAlert } from 'lucide-react'
import { LANGUAGES, isMachine } from '../i18n'
import { useApp } from '../store/AppContext'

/**
 * The language control, shared by both Settings pages.
 *
 * Each language is written in its own script, because someone looking for
 * Telugu is looking for "తెలుగు" — a list in English of languages you may not
 * read is the one list that cannot help you. The English name is kept beside
 * it for everyone else.
 *
 * A select rather than a row of buttons: that worked for three languages and
 * does not for twenty-three.
 *
 * Grouped by how each was made. Three were written for this app; twenty were
 * translated by machine and never checked by a native speaker, and a driver
 * choosing one of those — particularly for the emergency panel — is owed that
 * fact up front rather than discovering it in a mistranslated phrase.
 *
 * The note underneath says what is translated and what is not. The traffic
 * alerts and the assistant's answers are written by the server from measured
 * figures and are still English; finding that out mid-demo would be worse
 * than reading it here.
 */
const REVIEWED = LANGUAGES.filter((l) => !l.machine)
const MACHINE = LANGUAGES.filter((l) => l.machine)

export default function LanguagePicker({ card = true }) {
  const { language, setLanguage, t } = useApp()

  const option = (l) => (
    <option key={l.code} value={l.code} lang={l.code}>
      {l.label === l.english ? l.label : `${l.label} — ${l.english}`}
    </option>
  )

  const body = (
    <div className="field" style={{ marginBottom: 0 }}>
      <label htmlFor="language-picker">{t('settings.interfaceLanguage')}</label>
      <select
        id="language-picker"
        className="select"
        value={language}
        onChange={(e) => setLanguage(e.target.value)}
      >
        <optgroup label={t('settings.langReviewed')}>{REVIEWED.map(option)}</optgroup>
        <optgroup label={t('settings.langMachine')}>{MACHINE.map(option)}</optgroup>
      </select>

      {isMachine(language) && (
        <p className="settings-hint language-machine-note" role="note">
          <TriangleAlert size={12} aria-hidden="true" />
          {t('settings.machineNote')}
        </p>
      )}
      <p className="settings-hint">{t('settings.languageHint')}</p>
    </div>
  )

  if (!card) return body
  return (
    <div className="card">
      <div className="card-title"><Languages size={13} /> {t('settings.language')}</div>
      {body}
    </div>
  )
}
