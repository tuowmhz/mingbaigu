import { useEffect, useRef, useState } from 'react'

const QUICK = ['AAPL', 'NVDA', 'TSLA', 'JPM', '贵州茅台', '招商银行', '宁德时代', '比亚迪']

const SYMBOLS = { USD: '$', CNY: '¥', HKD: 'HK$' }

function fmtMoney(v, currency = 'USD') {
  if (v == null) return '-'
  const sym = SYMBOLS[currency] || `${currency} `
  const a = Math.abs(v)
  if (a >= 1e12) return `${sym}${(v / 1e12).toFixed(2)}万亿`
  if (a >= 1e8) return `${sym}${(v / 1e8).toFixed(0)}亿`
  return `${sym}${(v / 1e4).toFixed(0)}万`
}

function AnnualTable({ annual, currency }) {
  if (!annual?.length) return null
  return (
    <div className="panel">
      <h3>近 {annual.length} 个财年一览</h3>
      <table className="bank-table">
        <thead>
          <tr><th>财年</th><th>收入</th><th>净利润</th><th>毛利率</th><th>净利率</th></tr>
        </thead>
        <tbody>
          {annual.map((a) => (
            <tr key={a.year}>
              <td>{a.year}</td>
              <td>{fmtMoney(a.revenue, currency)}</td>
              <td style={{ color: a.net_income >= 0 ? 'inherit' : 'var(--down)' }}>{fmtMoney(a.net_income, currency)}</td>
              <td>{a.gross_margin == null ? '-' : `${(a.gross_margin * 100).toFixed(0)}%`}</td>
              <td>{a.net_margin == null ? '-' : `${(a.net_margin * 100).toFixed(1)}%`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function EarningsView({ initialQuery }) {
  const [input, setInput] = useState(initialQuery || '')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const seq = useRef(0)

  const search = (q) => {
    const query = (q || '').trim()
    if (!query) return
    const mySeq = ++seq.current
    setLoading(true)
    setError(null)
    fetch(`/api/earnings/${encodeURIComponent(query)}`)
      .then(async (res) => {
        if (!res.ok) throw new Error((await res.json()).detail || `API ${res.status}`)
        return res.json()
      })
      .then((d) => { if (seq.current === mySeq) { setData(d); setLoading(false) } })
      .catch((e) => { if (seq.current === mySeq) { setError(e.message); setLoading(false) } })
  }

  useEffect(() => {
    if (initialQuery) { setInput(initialQuery); search(initialQuery) }
  }, [initialQuery])

  return (
    <div className="detail">
      <div className="detail-header">
        <h2>财报拆解</h2>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>
          输入任意美股或A股公司，自动拆解三大报表并用人话讲清楚
        </span>
      </div>

      <div className="search-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && search(input)}
          placeholder="输入代码或名字：AAPL / 600519 / 贵州茅台 …"
        />
        <button onClick={() => search(input)}>拆解</button>
      </div>
      <div className="quick-chips">
        {QUICK.map((t) => (
          <span className="chip" key={t} onClick={() => { setInput(t); search(t) }}>{t}</span>
        ))}
      </div>

      {loading && (
        <div className="loading"><span className="spin" /> 正在抓取并拆解财报…</div>
      )}
      {error && <div className="error">{error}</div>}

      {data && !loading && (
        <>
          <div className="detail-header" style={{ marginTop: 16 }}>
            <h2>{data.ticker} · {data.name_cn || data.name}</h2>
            <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>
              {data.sector || ''} · 市值 {fmtMoney(data.market_cap, data.trade_currency || data.currency)} · {data.source}
            </span>
          </div>

          <div className="judge-box" style={{ margin: '10px 0 16px' }}>
            <div className="judge-line"><span>一句话总结：</span></div>
            <div style={{ marginTop: 4 }}>{data.verdict.summary}</div>
            <div className="adv-columns" style={{ marginTop: 10 }}>
              <div className="adv-col bull">
                <h4>✅ 加分项</h4>
                <ul>
                  {data.verdict.pluses.map((p, i) => <li key={i}>{p}</li>)}
                  {!data.verdict.pluses.length && <li>没有突出的加分项</li>}
                </ul>
              </div>
              <div className="adv-col bear">
                <h4>⚠减分项</h4>
                <ul>
                  {data.verdict.minuses.map((p, i) => <li key={i}>{p}</li>)}
                  {!data.verdict.minuses.length && <li>没有明显的减分项</li>}
                </ul>
              </div>
            </div>
          </div>

          <div className="detail-grid">
            <div>
              {data.sections.slice(0, 3).map((s) => (
                <div className="panel explain" key={s.key}>
                  <h3>{s.title}</h3>
                  {s.narrative.map((l, i) => <p key={i}>{l}</p>)}
                </div>
              ))}
            </div>
            <div>
              <AnnualTable annual={data.annual} currency={data.currency} />
              {data.sections.slice(3).map((s) => (
                <div className="panel explain" key={s.key}>
                  <h3>{s.title}</h3>
                  {s.narrative.map((l, i) => <p key={i}>{l}</p>)}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
