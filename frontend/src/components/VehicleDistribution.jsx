import { BarChart, Bar, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Info } from 'lucide-react'

/**
 * The vehicle mix — how many, and how much road they take.
 *
 * WHY TWO BARS PER CLASS
 * ----------------------
 * A count chart alone is misleading on Indian roads. Two-wheelers dominate
 * every frame by number and contribute comparatively little congestion; a
 * handful of buses can take more road space than fifty bikes. Showing only
 * counts invites the reader to blame the tallest bar, which is usually the
 * wrong one.
 *
 * So each class gets its share of the COUNT and its share of the PCU side by
 * side. Where the two differ is where the interesting traffic is.
 *
 * WHERE THE NUMBERS COME FROM
 * ---------------------------
 * All of it — the PCU factors, both shares, the per-vehicle average — is
 * computed by the backend beside the factor table the cost model itself uses.
 * Nothing here multiplies anything. A PCU table copied into this file would
 * eventually disagree with the one doing the routing, and the chart would go
 * on looking perfectly reasonable while describing a different road.
 */

const COUNT_COLOR = 'var(--vd-count, #38bdf8)'
const PCU_COLOR = 'var(--vd-pcu, #f59e0b)'

function Row({ label, value }) {
  return (
    <div className="vd-stat">
      <span>{label}</span>
      <b>{value}</b>
    </div>
  )
}

export default function VehicleDistribution({ distribution, lstmCounts, measures }) {
  const classes = distribution?.classes || []

  if (!classes.length) {
    return (
      <div className="vd-empty">
        No vehicles were detected, so there is no mix to break down.
      </div>
    )
  }

  const data = classes.map((c) => ({
    name: c.name,
    count: c.count,
    countPct: +(c.countShare * 100).toFixed(1),
    pcuPct: +(c.pcuShare * 100).toFixed(1),
    pcu: c.pcu,
    factor: c.pcuFactor,
    lstmClass: c.lstmClass,
  }))

  // The class whose road impact most exceeds its head count. This is the
  // sentence a judge remembers, so it is stated rather than left to be read
  // off two bars.
  const widest = data.reduce(
    (a, b) => (b.pcuPct - b.countPct > a.pcuPct - a.countPct ? b : a),
    data[0],
  )
  const gap = +(widest.pcuPct - widest.countPct).toFixed(1)

  const lstm = Object.entries(lstmCounts || {}).filter(([, v]) => v > 0)

  return (
    <div className="vd">
      <div className="vd-head">
        <h4>Vehicle distribution</h4>
        <span className="vd-measures">
          {measures === 'flow' ? 'vehicles crossing the line' : 'vehicles present'}
        </span>
      </div>

      <div className="vd-chart">
        <ResponsiveContainer width="100%" height={190}>
          <BarChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
            <XAxis
              dataKey="name"
              tick={{ fontSize: 10, fill: 'var(--text-dim)' }}
              axisLine={false}
              tickLine={false}
              interval={0}
            />
            {/* Pinned to 0-100 because these ARE percentages. An auto domain
                rescales the axis with the data, so the same bar height would
                mean a different share from one upload to the next. */}
            <YAxis
              width={34}
              unit="%"
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tick={{ fontSize: 9, fill: 'var(--text-dim)' }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              cursor={{ fill: 'rgba(255,255,255,0.04)' }}
              contentStyle={{
                background: 'var(--panel)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                fontSize: 11,
              }}
              formatter={(value, key, item) => {
                const d = item.payload
                if (key === 'countPct') return [`${value}%  (${d.count} vehicles)`, 'Share of count']
                return [`${value}%  (${d.pcu} PCU @ ${d.factor}×)`, 'Share of road space']
              }}
            />
            {/* Animation off. The page wrapper animates in with framer-motion at
                the same moment, and Recharts' bar growth was being cut short by
                it — bars froze at a fraction of their true height, which on a
                chart about proportions is not a cosmetic bug. */}
            <Bar dataKey="countPct" name="Share of count" radius={[3, 3, 0, 0]}
                 isAnimationActive={false}>
              {data.map((d) => <Cell key={d.name} fill={COUNT_COLOR} />)}
            </Bar>
            <Bar dataKey="pcuPct" name="Share of road space" radius={[3, 3, 0, 0]}
                 isAnimationActive={false}>
              {data.map((d) => <Cell key={d.name} fill={PCU_COLOR} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="vd-legend">
        <span><i style={{ background: COUNT_COLOR }} /> Share of count</span>
        <span><i style={{ background: PCU_COLOR }} /> Share of road space (PCU)</span>
      </div>

      <div className="vd-stats">
        <Row label="Vehicles" value={distribution.totalVehicles} />
        <Row label="Total PCU" value={distribution.totalPcu} />
        <Row label="PCU per vehicle" value={distribution.pcuPerVehicle} />
      </div>

      {gap > 1 && (
        <p className="vd-callout">
          <Info size={12} />
          <span>
            <b>{widest.name}</b> is {widest.countPct}% of the vehicles but{' '}
            <b>{widest.pcuPct}%</b> of the road space — {gap} points more impact
            than head count suggests, at {widest.factor}× a car.
          </span>
        </p>
      )}

      {lstm.length > 0 && (
        <div className="vd-lstm">
          <div className="vd-lstm-head">
            Folded into the four classes the forecaster was trained on
          </div>
          <div className="vd-lstm-row">
            {lstm.map(([k, v]) => (
              <span key={k} className="vd-lstm-chip">
                {k.replace('Count', '')} <b>{v}</b>
              </span>
            ))}
          </div>
        </div>
      )}

      <p className="vd-note">{distribution.note}</p>
    </div>
  )
}
