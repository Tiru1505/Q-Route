import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Check, Loader2, MapPin, Star, X } from 'lucide-react'
import { searchPlaces } from '../services/api'

/**
 * Free-text place search with a suggestion list.
 *
 * The value handed back is always a resolved place — {id, name, address, lat,
 * lon, coords} — never the raw text. That matters: the optimizer routes by
 * coordinate, so an unresolved string would have nowhere to start. Typing
 * without picking a suggestion therefore clears the value, and the parent can
 * see that nothing is selected.
 *
 * Suggestions come from /api/places/search, which merges the curated Hyderabad
 * landmarks with OpenStreetMap results and drops anything that is not on the
 * routing graph.
 */
export default function PlaceInput({
  label,
  value,
  onChange,
  placeholder = 'Type a place…',
  icon = <MapPin size={14} />,
  id: idProp,
  // Scopes the search to the road network the route will run on. A result
  // outside it is not routable, so offering it would produce a route that
  // silently begins somewhere else.
  graph = null,
}) {
  const autoId = useId()
  const id = idProp || autoId

  const [query, setQuery] = useState(value?.name || '')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [active, setActive] = useState(-1)
  const [touched, setTouched] = useState(false)

  const boxRef = useRef(null)
  const inputRef = useRef(null)
  const listRef = useRef(null)
  // Guards against a slow response for "hi" landing after a fast one for "hitec".
  const seqRef = useRef(0)

  // Keep the text in step when the value is changed from outside (swap button,
  // demo mode, restoring a saved trip).
  useEffect(() => {
    setQuery(value?.name || '')
  }, [value?.id, value?.name])

  const run = useCallback(async (text) => {
    const seq = ++seqRef.current
    setBusy(true)
    try {
      const found = await searchPlaces(text, 8, graph)
      if (seq === seqRef.current) setResults(found)
    } catch {
      if (seq === seqRef.current) setResults([])
    } finally {
      if (seq === seqRef.current) setBusy(false)
    }
  }, [graph])

  // Debounced so a burst of keystrokes makes one request, not eight.
  useEffect(() => {
    if (!open) return undefined
    const t = setTimeout(() => run(query), query.trim() ? 320 : 0)
    return () => clearTimeout(t)
  }, [query, open, run])

  // Click-outside closes the list.
  useEffect(() => {
    if (!open) return undefined
    const onDown = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  // Keep the highlighted row in view during keyboard navigation.
  useEffect(() => {
    if (active < 0 || !listRef.current) return
    listRef.current.children[active]?.scrollIntoView({ block: 'nearest' })
  }, [active])

  const pick = (place) => {
    onChange({ ...place, coords: [place.lat, place.lon] })
    setQuery(place.name)
    setOpen(false)
    setActive(-1)
    setTouched(false)
  }

  const onType = (e) => {
    setQuery(e.target.value)
    setOpen(true)
    setActive(-1)
    setTouched(true)
    // The text no longer describes the selected place, so drop it.
    if (value) onChange(null)
  }

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      if (!open) { setOpen(true); return }
      if (!results.length) return
      const step = e.key === 'ArrowDown' ? 1 : -1
      setActive((i) => (i + step + results.length) % results.length)
      return
    }
    if (e.key === 'Enter') {
      if (open && active >= 0 && results[active]) {
        e.preventDefault()
        pick(results[active])
      } else if (open && results.length === 1) {
        e.preventDefault()
        pick(results[0])
      }
      return
    }
    if (e.key === 'Escape') {
      setOpen(false)
      setActive(-1)
    }
  }

  const clear = () => {
    setQuery('')
    onChange(null)
    setResults([])
    setTouched(false)
    setOpen(true)
    inputRef.current?.focus()
  }

  const unresolved = touched && !value && query.trim().length > 0

  return (
    <div className="field place-field" ref={boxRef}>
      <label htmlFor={id}>{label}</label>

      <div
        className={`place-input-wrap${open ? ' open' : ''}${value ? ' resolved' : ''}`}
      >
        <span className="place-input-icon">{icon}</span>

        <input
          id={id}
          ref={inputRef}
          className="place-input"
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-autocomplete="list"
          aria-controls={`${id}-list`}
          autoComplete="off"
          spellCheck="false"
          value={query}
          placeholder={placeholder}
          onChange={onType}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
        />

        <span className="place-input-tail">
          {busy && <Loader2 size={13} className="spin" />}
          {!busy && value && <Check size={13} className="place-ok" />}
          {!busy && !value && query && (
            <button type="button" className="place-clear" onClick={clear} aria-label="Clear">
              <X size={13} />
            </button>
          )}
        </span>
      </div>

      {open && (
        <div className="place-menu">
          {results.length > 0 ? (
            <ul className="place-list" id={`${id}-list`} role="listbox" ref={listRef}>
              {results.map((r, i) => (
                <li
                  key={r.id}
                  role="option"
                  aria-selected={i === active}
                  className={`place-option${i === active ? ' active' : ''}`}
                  onMouseEnter={() => setActive(i)}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => pick(r)}
                >
                  <span className="place-option-icon">
                    {r.source === 'preset' ? <Star size={12} /> : <MapPin size={12} />}
                  </span>
                  <span className="place-option-text">
                    <strong>{r.name}</strong>
                    <small>{r.address}</small>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="place-empty">
              {busy
                ? 'Searching…'
                : query.trim().length < 3
                  ? 'Keep typing to search the whole city.'
                  : 'No routable place found in the Hyderabad network.'}
            </p>
          )}
        </div>
      )}

      {unresolved && !open && (
        <p className="place-hint">Pick a suggestion so we know where that is.</p>
      )}
    </div>
  )
}
