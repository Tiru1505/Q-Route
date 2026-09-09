import { useEffect, useState } from 'react'
import {
  Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, ReferenceLine,
} from 'recharts'
import { Brain, CircleCheck, CircleX } from 'lucide-react'
import { getForecast } from '../services/api'

const LEVEL = {
  low: 'var(--low)',
  normal: 'var(--low)',
  high: 'var(--heavy)',
  heavy: 'var(--severe)',
}

/**
 * The trained LSTM forecasting traffic it has never seen.
 *
 * This is a replay of recorded held-out days, which is the whole reason the
 * card can show the real outcome beside the prediction — a forecast displayed
 * without its outcome is only a claim. It is labelled as replay rather than
 * live, because the model needs three hours of recent vehicle counts for a road
 * and no live road in this system supplies that yet.
 */
export default function ForecastCard({ intervalMs = 6000 }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    const pull = () =>
      getForecast()
        .then((d) => !cancelled && (d?.unavailable ? setError('not trained') : setData(d)))
        .catch((e) => !cancelled && setError(e.message))
    pull()
    const t = setInterval(pull, intervalMs)
    return () => { cancelled = true; clearInterval(t) }
  }, [intervalMs])

  if (error) {
    return (
      <div className="card chart-card">
        <div className="card-title"><Brain size={13} /> Traffic Forecast</div>
        <p style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 8 }}>
          Forecaster unavailable — train it with <code>scripts/train_lstm_india.py</code>.
        </p>
      </div>
    )
  }
  if (!data) {
    return (
      <div className="card chart-card">
        <div className="card-title"><Brain size={13} /> Traffic Forecast</div>
        <p style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 8 }}>Loading…</p>
      </div>
    )
  }

  // History is observed; the forecast steps carry both prediction and outcome.
  const series = [
    ...data.history.map((h, i) => ({
      t: i === data.history.length - 1 ? 'now' : `-${(data.history.length - 1 - i) * 15}m`,
      observed: h.pcu,
    })),
    ...data.forecast.map((f, i) => ({
      t: `+${f.minutesAhead}m`,
      predicted: f.pcu,
      actual: data.actual[i]?.pcu,
    })),
  ]
  // Join the observed line to the forecast so the chart reads as one story.
  const lastObserved = data.history[data.history.length - 1]?.pcu
  series[data.history.length - 1].predicted = lastObserved
  series[data.history.length - 1].actual = lastObserved

  const [hits, total] = String(data.correctThisWindow || '0/0').split('/')

  return (
    <div className="card chart-card">
      <div className="row-between" style={{ marginBottom: 10 }}>
        <div className="card-title" style={{ margin: 0 }}>
          <Brain size={13} />
          Traffic Forecast — next 60 min
        </div>
        <span className="forecast-clock">
          {data.clock?.day} {data.clock?.time}
        </span>
      </div>

      <div className="chart-box-sm">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={series} margin={{ top: 6, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="gObs" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--fc-observed)" stopOpacity={0.28} />
                <stop offset="100%" stopColor="var(--fc-observed)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            {/* The history window follows the trained weights, so this chart is 8
                points wide with a one-hour model and 16 with a three-hour one.
                A fixed interval labelled only three points on the short one. */}
            <XAxis dataKey="t" axisLine={false} tickLine={false} tick={{ fontSize: 10 }}
                   interval={series.length > 10 ? 2 : 0} />
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10 }} unit=" PCU" width={62} />
            <Tooltip
              contentStyle={{
                background: 'var(--surface-elevated, var(--panel-solid))',
                border: '1px solid var(--border)', borderRadius: 8,
                fontSize: 12, color: 'var(--text)',
              }}
            />
            <ReferenceLine x="now" stroke="var(--text-faint)" strokeDasharray="3 3" />
            <Area type="monotone" dataKey="observed" name="Observed"
                  stroke="var(--fc-observed)" strokeWidth={2} fill="url(#gObs)" connectNulls={false} />
            <Line type="monotone" dataKey="predicted" name="Forecast"
                  stroke="var(--fc-forecast)" strokeWidth={2.2} strokeDasharray="5 4"
                  dot={{ r: 3 }} connectNulls />
            <Line type="monotone" dataKey="actual" name="What happened"
                  stroke="var(--fc-actual)" strokeWidth={2} dot={{ r: 3 }} connectNulls />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="forecast-legend">
        <span><i style={{ background: 'var(--fc-observed)' }} /> Observed</span>
        <span><i style={{ background: 'var(--fc-forecast)' }} /> Forecast</span>
        <span><i style={{ background: 'var(--fc-actual)' }} /> What happened</span>
      </div>

      <div className="forecast-rows">
        {data.forecast.map((f, i) => {
          const truth = data.actual[i]
          const right = truth && f.situation === truth.situation
          return (
            <div key={f.minutesAhead} className="forecast-row">
              <span className="fr-h">+{f.minutesAhead}m</span>
              <span className="fr-p" style={{ color: LEVEL[f.situation] }}>{f.situation}</span>
              <span className="fr-a">{truth?.situation}</span>
              {right
                ? <CircleCheck size={13} style={{ color: 'var(--low)' }} />
                : <CircleX size={13} style={{ color: 'var(--severe)' }} />}
            </div>
          )
        })}
      </div>

      <p className="forecast-note">
        <strong>{hits} of {total} correct</strong> in this window. Replay of {data.heldOut} —
        the model never saw these days in training, which is why the real outcome
        can be shown next to the forecast. Not a live feed.
      </p>
    </div>
  )
}
