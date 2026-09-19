import { Languages } from 'lucide-react'
import { LANGUAGES } from '../i18n'
import { useApp } from '../store/AppContext'

/**
 * The language control, shared by both Settings pages.
 *
 * Each language is written in its own script, because someone looking for
 * Telugu is looking for "తెలుగు" — a list in English of languages you may not
 * read is the one list that cannot help you.
 *
 * The note underneath says what is translated and what is not. The traffic
 * alerts and the assistant's answers are written by the server from measured
 * figures and are still English; finding that out mid-demo would be worse
 * than reading it here.
 */
export default function LanguagePicker({ card = true }) {
  const { language, setLanguage, t } = useApp()

  const body = (
    <>
      <div className="field" style={{ marginBottom: 0 }}>
        <label htmlFor="language-picker">{t('settings.interfaceLanguage')}</label>
        <div className="segmented language-segmented" id="language-picker" role="group"
             aria-label={t('settings.interfaceLanguage')}>
          {LANGUAGES.map((l) => (
            <button
              key={l.code}
              type="button"
              lang={l.code}
              data-active={language === l.code}
              onClick={() => setLanguage(l.code)}
              title={l.english}
            >
              {l.label}
            </button>
          ))}
        </div>
        <p className="settings-hint">{t('settings.languageHint')}</p>
      </div>
    </>
  )

  if (!card) return body
  return (
    <div className="card">
      <div className="card-title"><Languages size={13} /> {t('settings.language')}</div>
      {body}
    </div>
  )
}
