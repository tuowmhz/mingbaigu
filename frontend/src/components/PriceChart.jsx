import {
  Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

export default function PriceChart({ series }) {
  if (!series?.length) return null
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={series} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="closeArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#5ea0ff" stopOpacity={0.28} />
            <stop offset="100%" stopColor="#5ea0ff" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="rgba(255,255,255,.06)" strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fill: '#8b96a8', fontSize: 11 }} minTickGap={50}
          axisLine={{ stroke: 'rgba(255,255,255,.1)' }} tickLine={false} />
        <YAxis
          domain={['auto', 'auto']}
          tick={{ fill: '#8b96a8', fontSize: 11 }}
          width={56}
          tickFormatter={(v) => `$${v}`}
          axisLine={false} tickLine={false}
        />
        <Tooltip
          contentStyle={{
            background: 'rgba(13,17,28,.92)', backdropFilter: 'blur(12px)',
            border: '1px solid rgba(255,255,255,.12)', borderRadius: 12,
            boxShadow: '0 8px 32px rgba(0,0,0,.5)',
          }}
          labelStyle={{ color: '#8b96a8' }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Area type="monotone" dataKey="close" name="收盘价" stroke="#5ea0ff"
          strokeWidth={2} fill="url(#closeArea)" dot={false} />
        <Line type="monotone" dataKey="sma20" name="20日均线" stroke="#ffb02e" dot={false} strokeWidth={1.1} />
        <Line type="monotone" dataKey="sma50" name="50日均线" stroke="#a78bfa" dot={false} strokeWidth={1.1} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
