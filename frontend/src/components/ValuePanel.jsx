import { useEffect, useState } from 'react'

const STATUS = { pass: ['✅', 'var(--up)'], fail: ['❌', 'var(--down)'], neutral: ['➖', 'var(--neutral)'] }

export default function ValuePanel({ ticker }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    setLoading(true)
    setData(null)
    fetch(`/api/value/${ticker}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (alive) { setData(d); setLoading(false) } })
      .catch(() => alive && setLoading(false))
    return () => { alive = false }
  }, [ticker])

  if (loading) return <div className="panel"><h3>价值投资视角</h3><div className="judge-notes"><span className="spin" /> 体检中…</div></div>
  if (!data) return null

  const scoreColor = data.score >= 70 ? 'var(--up)' : data.score >= 40 ? 'var(--neutral)' : 'var(--down)'

  return (
    <div className="panel">
      <h3>价值投资视角（{data.n_pass}/{data.n_total} 项达标）</h3>
      <div className="judge-line" style={{ marginBottom: 8 }}>
        <span className="verdict" style={{ color: scoreColor }}>{data.score} 分</span>
        {data.graham && (
          <span style={{ fontSize: 12.5, color: 'var(--text-dim)' }}>
            格雷厄姆合理价 ≈ {data.graham.number}（现价 {data.graham.price}，
            {data.graham.margin > 0 ? '低估' : '高出'} {Math.abs(data.graham.margin * 100).toFixed(0)}%）
          </span>
        )}
      </div>
      {data.checks.map((c, i) => {
        const [icon, color] = STATUS[c.status] || STATUS.neutral
        return (
          <div key={i} style={{ marginBottom: 8, fontSize: 12.8 }}>
            <span style={{ color, fontWeight: 700 }}>{icon} {c.name}</span>
            <div className="judge-notes" style={{ marginTop: 2 }}>{c.detail}</div>
          </div>
        )
      })}
      <div className="explain" style={{ marginTop: 10 }}>
        <p><b>结论：</b>{data.verdict}</p>
      </div>
      <div className="judge-notes">· {data.philosophy}{data.note ? ` · ${data.note}` : ''}</div>
    </div>
  )
}
