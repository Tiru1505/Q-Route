import { useCallback, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  AlertTriangle, Brain, CircleAlert, Film, Image as ImageIcon, Loader2,
  MapPin, RotateCcw, ScanEye, Upload,
} from 'lucide-react'
import {
  analyseRoadMedia, getCities, getRoads, getVisionStatus, resetVisionSession,
} from '../services/api'
import VehicleDistribution from '../components/VehicleDistribution'

/**
 * Road Vision — the trained detector, run on media the visitor supplies.
 *
 * The page is built around one distinction that the backend enforces and the
 * UI has to make visible, or the numbers mislead:
 *
 *   a photo  measures OCCUPANCY -> congestion right now
 *   a clip   measures FLOW      -> feeds the forecaster
 *
 * So a photo never produces a forecast here, however many are uploaded. That is
 * a property of what a photograph contains, and saying so on screen is the
 * difference between a demo and a magic trick.
 */

const LEVEL_COLOR = {
  low: 'var(--low)',
  moderate: 'var(--moderate)',
  heavy: 'var(--heavy)',
  severe: 'var(--severe)',
  normal: 'var(--low)',
  high: 'var(--heavy)',
}

const MAX_MB = 40
const sessionId = () => `sess-${Math.random().toString(36).slice(2, 10)}`

export default function RoadVision() {
  const [status, setStatus] = useState(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [session] = useState(sessionId)
  const [segmentM, setSegmentM] = useState(100)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  /* Where the footage was taken. A count with no road attached cannot become
   * an observation, cannot accumulate into a series, and cannot be written
   * back onto the graph — so the analyse button waits for both. */
  const [cities, setCities] = useState([])
  const [city, setCity] = useState('')
  const [roadQuery, setRoadQuery] = useState('')
  const [roads, setRoads] = useState(null)
  const [roadId, setRoadId] = useState('')

  useEffect(() => {
    getVisionStatus().then(setStatus).catch(() => setStatus({ available: false }))
    getCities()
      .then((d) => {
        setCities(d.cities || [])
        const first = (d.cities || []).find((c) => c.available)
        if (first) setCity(first.id)
      })
      .catch(() => setCities([]))
  }, [])

  // Road list follows the city, and re-queries as the user types. Debounced
  // because the index is thousands of roads and every keystroke would
  // otherwise ask for all of them again.
  useEffect(() => {
    if (!city) { setRoads(null); return undefined }
    let cancelled = false
    setRoadId('')
    const t = setTimeout(() => {
      getRoads(city, roadQuery, 60)
        .then((d) => !cancelled && setRoads(d))
        .catch(() => !cancelled && setRoads(null))
    }, roadQuery ? 280 : 0)
    return () => { cancelled = true; clearTimeout(t) }
  }, [city, roadQuery])

  const send = useCallback(async (file) => {
    if (!file) return
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`That file is ${(file.size / 1e6).toFixed(1)} MB. The limit is ${MAX_MB} MB.`)
      return
    }
    setError(null)
    setBusy(true)
    try {
      const d = await analyseRoadMedia(file, { session, segmentM, city, roadId })
      setResult({ ...d, fileName: file.name })
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }, [session, segmentM, city, roadId])

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    send(e.dataTransfer.files?.[0])
  }

  const clearWindow = async () => {
    await resetVisionSession(session)
    setResult((r) => (r ? { ...r, window: { have: 0, need: r.window?.need ?? 4 } } : r))
  }

  const win = result?.window
  const forecast = win?.forecast

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Traffic Analysis Lab</h1>
          <p className="page-sub">
            Pick where the footage was taken, upload it, and the trained detector
            counts the vehicles the traffic model turns into congestion.
          </p>
        </div>
      </div>

      {status && !status.available && (
        <div className="card" style={{ borderColor: 'var(--severe)' }}>
          <div className="card-title"><CircleAlert size={13} /> Detector unavailable</div>
          <p style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 8 }}>
            {status.reason || 'Train it with scripts/train_yolo.py'}
          </p>
        </div>
      )}

      <div className="grid grid-2">
        {/* ------------------------------------------------ upload ----- */}
        <div className="card">
          <div className="card-title"><MapPin size={13} /> Location</div>
          <div className="lab-location">
            <div className="field route-field" style={{ display: 'block' }}>
              <label htmlFor="lab-city">City</label>
              <select
                id="lab-city" className="select route-select"
                value={city} onChange={(e) => setCity(e.target.value)}
              >
                <option value="">Select a city…</option>
                {cities.map((c) => (
                  <option key={c.id} value={c.id} disabled={!c.available}>
                    {c.label}{c.available ? '' : ' — no graph built'}
                  </option>
                ))}
              </select>
            </div>

            <div className="field route-field" style={{ display: 'block' }}>
              <label htmlFor="lab-road">Road</label>
              <input
                id="lab-road" className="select route-select" type="text"
                placeholder={city ? 'Type to filter roads…' : 'Pick a city first'}
                value={roadQuery} disabled={!city}
                onChange={(e) => setRoadQuery(e.target.value)}
              />
              <select
                className="select route-select" style={{ marginTop: 6 }}
                value={roadId} disabled={!roads?.roads?.length}
                onChange={(e) => setRoadId(e.target.value)}
                size={1}
              >
                <option value="">
                  {roads?.roads?.length
                    ? `Select a road… (${roads.total.toLocaleString()} indexed)`
                    : 'No roads loaded'}
                </option>
                {(roads?.roads || []).map((r) => (
                  <option key={r.road_id} value={r.road_id}>
                    {r.name} · {r.segments} seg
                  </option>
                ))}
              </select>
            </div>
          </div>
          {roads?.coverage && (
            <p className="vision-hint">{roads.coverage}.</p>
          )}
          {!roadId && (
            <p className="vision-hint">
              A count with no road attached is a detection, not an observation — it
              cannot accumulate into a series or reach the graph. Pick one before
              analysing.
            </p>
          )}
        </div>

        <div className="card">
          <div className="card-title"><Upload size={13} /> Upload</div>

          <div
            className={`vision-drop${dragging ? ' is-dragging' : ''}${busy ? ' is-busy' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => !busy && inputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && inputRef.current?.click()}
          >
            <input
              ref={inputRef} type="file" hidden
              accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm"
              onChange={(e) => { send(e.target.files?.[0]); e.target.value = '' }}
            />
            {busy ? (
              <>
                <Loader2 size={26} className="spin" />
                <strong>Analysing…</strong>
                <span>A clip is processed frame by frame on CPU — this can take a minute.</span>
              </>
            ) : (
              <>
                <ScanEye size={26} />
                <strong>Drop a road photo or clip</strong>
                <span>JPEG, PNG or MP4 · up to {MAX_MB} MB</span>
              </>
            )}
          </div>

          <div className="vision-field">
            <label htmlFor="segm">Visible road length</label>
            <input
              id="segm" type="number" min={10} max={1000} step={10} value={segmentM}
              onChange={(e) => setSegmentM(Number(e.target.value) || 100)}
            />
            <span>metres</span>
          </div>
          <p className="vision-hint">
            Used for photos only. Density is vehicles per kilometre, so the stretch of
            road in the frame has to be stated — it cannot be recovered from pixels.
          </p>

          {error && (
            <p className="vision-error"><AlertTriangle size={12} /> {error}</p>
          )}

          {/* what each kind of upload can and cannot do */}
          <div className="vision-explain">
            <div>
              <ImageIcon size={13} />
              <div>
                <strong>A photo</strong> shows what is <em>present</em> — occupancy.
                That gives congestion right now.
              </div>
            </div>
            <div>
              <Film size={13} />
              <div>
                <strong>A clip</strong> shows what <em>passes</em> — flow. That is what
                the forecaster was trained on, so clips build toward a prediction.
              </div>
            </div>
          </div>
        </div>

        {/* ------------------------------------------------ result ----- */}
        <div className="card">
          <div className="card-title"><ScanEye size={13} /> Detection</div>
          {!result ? (
            <p className="vision-empty">Nothing analysed yet.</p>
          ) : (
            <>
              {result.annotated && (
                <img
                  className="vision-shot"
                  src={`data:image/jpeg;base64,${result.annotated}`}
                  alt="Detected vehicles"
                />
              )}
              {result.located && (
                <div className="lab-origin">
                  <MapPin size={11} />
                  <span>
                    <strong>{result.roadName}</strong> · {result.city}
                    {' · '}{result.lat}, {result.lon}
                  </span>
                  <em>{new Date(result.observedAt).toLocaleTimeString()}</em>
                </div>
              )}
              <div className="vision-stats">
                <div><span>{result.totalVehicles}</span>vehicles</div>
                <div><span>{result.pcu}</span>PCU</div>
                <div><span>{result.framesProcessed}</span>{result.kind === 'video' ? 'frames' : 'frame'}</div>
                <div><span>{(result.elapsedMs / 1000).toFixed(1)}s</span>to analyse</div>
              </div>

              <div className="vision-chips">
                {Object.entries(result.counts || {}).map(([k, v]) => (
                  <span key={k} className="vision-chip">{k} <b>{v}</b></span>
                ))}
                {!Object.keys(result.counts || {}).length && (
                  <span className="vision-chip muted">no vehicles detected</span>
                )}
              </div>

              <VehicleDistribution
                distribution={result.distribution}
                lstmCounts={result.lstmCounts}
                measures={result.measures}
              />

              {result.congestion && (
                <div className="vision-congestion">
                  <div className="vc-head">
                    <span>Congestion now</span>
                    <strong style={{ color: LEVEL_COLOR[result.congestion.level] }}>
                      {result.congestion.level}
                    </strong>
                  </div>
                  <div className="vc-bar">
                    <div style={{
                      width: `${Math.min(result.congestion.congestion * 100, 100)}%`,
                      background: LEVEL_COLOR[result.congestion.level],
                    }} />
                  </div>
                  <div className="vc-nums">
                    <span>{result.congestion.densityPcuKm} PCU/km</span>
                    <span>{(result.congestion.congestion * 100).toFixed(0)}%</span>
                    <span>≈{result.congestion.speedKph} km/h</span>
                  </div>
                  <p className="vision-hint">{result.congestion.assumptions.note}</p>
                </div>
              )}

              {result.kind === 'video' && (
                <div className="vision-flow">
                  <div className="vf-row">
                    <span>Crossed the line</span><b>{result.crossings}</b>
                  </div>
                  <div className="vf-row">
                    <span>Clip length</span><b>{result.durationS}s</b>
                  </div>
                  <div className="vf-row">
                    <span>Scaled to 15 min</span>
                    <b>{Object.values(result.per15Min || {}).reduce((a, b) => a + b, 0)} vehicles</b>
                  </div>
                  <p className="vision-hint">{result.flowNote}</p>
                  {result.flowWarning && (
                    <p className="vision-error"><AlertTriangle size={12} /> {result.flowWarning}</p>
                  )}
                </div>
              )}

              {result.forecastNote && (
                <p className="vision-note">{result.forecastNote}</p>
              )}
            </>
          )}
        </div>
      </div>

      {/* ------------------------------------------------- forecast ----- */}
      {win && (
        <div className="card">
          <div className="row-between" style={{ marginBottom: 10 }}>
            <div className="card-title" style={{ margin: 0 }}>
              <Brain size={13} /> Forecast from your clips
            </div>
            <button className="btn-ghost btn-sm" onClick={clearWindow}>
              <RotateCcw size={12} /> Reset
            </button>
          </div>

          <div className="vision-steps">
            {Array.from({ length: win.need || 0 }).map((_, i) => (
              <div key={i} className={`vs-dot${i < (win.have || 0) ? ' filled' : ''}`} />
            ))}
            <span>{win.have} of {win.need} clips</span>
          </div>
          <p className="vision-hint">{win.note}</p>

          <AnimatePresence>
            {forecast && (
              <motion.div
                initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
              >
                <div className="forecast-rows" style={{ marginTop: 14 }}>
                  {forecast.steps.map((s) => (
                    <div key={s.minutesAhead} className="forecast-row">
                      <span className="fr-h">+{s.minutesAhead}m</span>
                      <span className="fr-p" style={{ color: LEVEL_COLOR[s.situation] }}>
                        {s.situation}
                      </span>
                      <span className="fr-a">{s.pcu} PCU</span>
                      <span className="fr-a">{Math.round(s.confidence * 100)}%</span>
                    </div>
                  ))}
                </div>
                <p className="vision-note">{forecast.clockUsed.note}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {status?.available && (
        <div className="card">
          <div className="card-title"><CircleAlert size={13} /> What this detector can and cannot do</div>
          <p className="vision-note" style={{ marginTop: 8 }}>{status.note}</p>
          <div className="vision-chips" style={{ marginTop: 10 }}>
            {(status.classes || []).map((c) => (
              <span key={c} className="vision-chip muted">{c}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
