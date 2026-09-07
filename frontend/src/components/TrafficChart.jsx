import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

const legendStyle = { fontSize: 11.5, color: 'var(--text-dim)' }
const axisTick = { fill: 'var(--text-dim)', fontSize: 11 }
const gridStroke = 'var(--border)'

const tooltipStyle = {
  background: 'var(--surface-elevated)',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  fontSize: 12,
  color: 'var(--text-primary)',
  boxShadow: '0 8px 24px rgba(0, 0, 0, 0.65)',
}

export function TrafficTrendChart({ data = [], height = 260 }) {
  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
          <defs>
            <linearGradient id="gTrendQuantum" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#E83E8C" stopOpacity={0.35} />
              <stop offset="70%" stopColor="#FF6B35" stopOpacity={0.08} />
              <stop offset="100%" stopColor="#FF6B35" stopOpacity={0.01} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
          <XAxis dataKey="hour" axisLine={false} tickLine={false} tick={axisTick} />
          <YAxis axisLine={false} tickLine={false} tick={axisTick} unit="%" />
          <Tooltip contentStyle={tooltipStyle} />
          <Area
            type="monotone"
            dataKey="congestion"
            name="Congestion %"
            stroke="#FF6B35"
            strokeWidth={2.5}
            fill="url(#gTrendQuantum)"
            animationDuration={850}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

export function RoutePerformanceChart({ data = [], height = 260 }) {
  if (!data.length) {
    return (
      <div
        style={{
          width: '100%', height, display: 'grid', placeItems: 'center',
          textAlign: 'center', padding: 16,
        }}
      >
        <p style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.5 }}>
          No routes optimized yet.<br />
          Run the optimizer to generate recent route performance records.
        </p>
      </div>
    )
  }

  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
          <XAxis
            dataKey="route"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: 'var(--text-dim)' }}
            interval={0}
            angle={-25}
            textAnchor="end"
            height={82}
          />
          <YAxis axisLine={false} tickLine={false} tick={axisTick} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'var(--panel-hover)' }} />
          <Legend wrapperStyle={legendStyle} />
          <Bar dataKey="distance" name="Distance (km)" fill="#FF6B35" radius={[4, 4, 0, 0]} animationDuration={800} />
          <Bar dataKey="time" name="Time (min)" fill="#E83E8C" radius={[4, 4, 0, 0]} animationDuration={800} animationBegin={120} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function TrafficDistributionChart({ data = [], height = 260 }) {
  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius="50%"
            outerRadius="76%"
            paddingAngle={2}
            stroke="var(--surface)"
            strokeWidth={1}
            animationDuration={800}
            label={({ name, value }) => `${name} ${value}%`}
            labelLine={{ stroke: 'var(--border)' }}
          >
            {data.map((d) => (
              <Cell key={d.name} fill={d.color} />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${v}%`} />
          <Legend wrapperStyle={legendStyle} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

export function ScalabilityChart({ data = [], height = 280 }) {
  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 12, left: -10, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
          <XAxis
            dataKey="nodes"
            axisLine={false}
            tickLine={false}
            tick={axisTick}
            label={{ value: 'Network size (nodes)', position: 'insideBottom', offset: -2, fill: 'var(--text-dim)', fontSize: 11 }}
          />
          <YAxis axisLine={false} tickLine={false} tick={axisTick} unit="ms" />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'var(--panel-hover)' }} />
          <Legend wrapperStyle={legendStyle} />
          <Bar dataKey="dijkstra" name="Dijkstra" fill="#64748B" radius={[4, 4, 0, 0]} />
          <Bar dataKey="qpso" name="QPSO" fill="#E83E8C" radius={[4, 4, 0, 0]} />
          <Bar dataKey="pso" name="PSO" fill="#FF6B35" radius={[4, 4, 0, 0]} />
          <Bar dataKey="ga" name="GA" fill="#FFB347" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
