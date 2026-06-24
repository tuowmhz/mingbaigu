import { useEffect, useState } from 'react'
import { fetchSummary } from '../api/client'

function Sparkline({ data, up, ticker }) {
  if (!data || data.length < 2) return null
  const w = 200, h = 42
  const min = Math.min(...data), max = Math.max(...data)
  const span = max - min || 1
  const xy = data.map((v, i) => [
    (i / (data.length - 1)) * w,
    3 + (h - 6) * (1 - (v - min) / span),
  ])
  const pts = xy.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const area = `M0,${h} L${pts.replace(/ /g, ' L')} L${w},${h} Z`
  const color = up ? 'var(--up)' : 'var(--down)'
  const gid = `spark-${ticker}`
  return (
    <svg className="sparkline" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" height={h}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={up ? '#00d68f' : '#ff5470'} stopOpacity="0.30" />
          <stop offset="100%" stopColor={up ? '#00d68f' : '#ff5470'} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gid})`} />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.8"
        strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={xy[xy.length - 1][0]} cy={xy[xy.length - 1][1]} r="2.4" fill={color} />
    </svg>
  )
}

export default function StockCard({ stock, active, onClick, idx = 0, onRemove }) {
  const [summary, setSummary] = useState(null)

  useEffect(() => {
    let alive = true
    fetchSummary(stock.ticker)
      .then((s) => alive && setSummary(s))
      .catch(() => {})
    return () => { alive = false }
  }, [stock.ticker])

  const up = stock.change_pct >= 0
  const judge = summary?.judge
  const pred = summary?.prediction

  return (
    <div className={`card ${active ? 'active' : ''}`} onClick={onClick}
      style={{ animationDelay: `${idx * 55}ms` }}>
      {onRemove && (
        <button className="card-remove" title="移出自选"
          onClick={(e) => { e.stopPropagation(); onRemove() }}></button>
      )}
      <div className="card-top">
        <span>
          <span className="ticker">{stock.ticker}</span>
          <span className="name-cn">{stock.name_cn}</span>
        </span>
        <span className={`chg ${up ? 'up' : 'down'}`}>
          {up ? '+' : ''}{stock.change_pct}%
        </span>
      </div>
      <div className="price">{stock.currency || '$'}{stock.price}</div>
      <Sparkline data={stock.sparkline} up={up} ticker={stock.ticker} />
      <div className="badges">
        {judge ? (
          <span className={`badge ${judge.verdict}`}>
            {judge.verdict_cn} · 置信{judge.confidence_label}
          </span>
        ) : (
          <span className="badge"><span className="spin" /> 分析中</span>
        )}
        {pred && (
          <span className="badge">
            模型: {pred.direction === 'up' ? '↑' : '↓'}{' '}
            {Math.round(Math.max(pred.prob_up, 1 - pred.prob_up) * 100)}%
          </span>
        )}
        {summary?.news_label && summary.news_label !== '无数据' && (
          <span className={`badge ${
            summary.news_score >= 0.4 ? 'bullish' : summary.news_score <= -0.4 ? 'bearish' : ''
          }`}>消息面{summary.news_label}</span>
        )}
      </div>
    </div>
  )
}
