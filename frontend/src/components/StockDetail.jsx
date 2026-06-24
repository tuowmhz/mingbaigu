import { useEffect, useState } from 'react'
import { fetchStock } from '../api/client'
import PriceChart from './PriceChart.jsx'
import ValuePanel from './ValuePanel.jsx'

function Explain({ title, lines }) {
  if (!lines?.length) return null
  return (
    <div className="panel explain">
      <h3>{title}</h3>
      {lines.map((l, i) => <p key={i}>{l}</p>)}
    </div>
  )
}

function Gauge({ value, cls }) {
  const r = 40
  const c = 2 * Math.PI * r
  const colors = { bullish: '#00d68f', bearish: '#ff5470', neutral: '#ffb02e' }
  const color = colors[cls] || '#5ea0ff'
  const v = Math.min(1, Math.max(0.02, value))
  return (
    <svg className="gauge" viewBox="0 0 100 100">
      <circle cx="50" cy="50" r={r} fill="none" stroke="rgba(255,255,255,.08)" strokeWidth="8" />
      <circle cx="50" cy="50" r={r} fill="none" stroke={color} strokeWidth="8"
        strokeLinecap="round" strokeDasharray={`${c * v} ${c}`}
        transform="rotate(-90 50 50)"
        style={{ filter: `drop-shadow(0 0 6px ${color})` }} />
      <text x="50" y="46" textAnchor="middle" dominantBaseline="central">
        {Math.round(value * 100)}%
      </text>
      <text className="gauge-label" x="50" y="66" textAnchor="middle">置信度</text>
    </svg>
  )
}

function Adversarial({ adv }) {
  if (!adv) return null
  const { bull_case, bear_case, judge } = adv
  return (
    <div className="panel">
      <h3>对抗验证：多头 vs 空头</h3>
      <div className="adv-columns">
        <div className="adv-col bull">
          <h4>多头论据（{judge.bull_score} 分）</h4>
          <ul>
            {bull_case.map((a, i) => (
              <li key={i}><span className="adv-dim">[{a.dimension}]</span> {a.text}</li>
            ))}
            {!bull_case.length && <li>找不到像样的看多理由</li>}
          </ul>
        </div>
        <div className="adv-col bear">
          <h4>空头论据（{judge.bear_score} 分）</h4>
          <ul>
            {bear_case.map((a, i) => (
              <li key={i}><span className="adv-dim">[{a.dimension}]</span> {a.text}</li>
            ))}
            {!bear_case.length && <li>找不到像样的看空理由</li>}
          </ul>
        </div>
      </div>
      <div className="judge-box">
        <Gauge value={judge.confidence} cls={judge.verdict} />
        <div className="judge-main">
          <div className="judge-line">
            <span>裁判裁决：</span>
            <span className={`verdict ${judge.verdict}`}>{judge.verdict_cn}</span>
            <span style={{ color: 'var(--text-dim)', fontSize: 12.5 }}>置信度{judge.confidence_label}</span>
          </div>
          {judge.notes?.map((n, i) => <div className="judge-notes" key={i}>· {n}</div>)}
        </div>
      </div>
    </div>
  )
}

function NewsSignal({ signal }) {
  if (!signal) return null
  const cls = signal.score >= 0.4 ? 'bullish' : signal.score <= -0.4 ? 'bearish' : 'neutral'
  const pos = Math.max(2, Math.min(98, ((signal.score + 3) / 6) * 100))
  return (
    <div className="panel">
      <h3>消息面研判</h3>
      <div className="judge-line" style={{ marginBottom: 6 }}>
        <span className={`verdict ${cls}`}>{signal.direction_cn}</span>
        <span>信号分 {signal.score > 0 ? '+' : ''}{signal.score}</span>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>
          基于 {signal.n_items} 条新闻 · 72小时半衰期加权
          {signal.sentiment_engine && ` · 情绪引擎：${signal.sentiment_engine}`}
        </span>
      </div>
      <div className="signal-bar">
        <div className="signal-marker" style={{ left: `${pos}%` }} />
      </div>
      <div className="signal-scale"><span>强利空 -3</span><span>0</span><span>强利好 +3</span></div>
      <div className="judge-notes" style={{ marginTop: 8 }}>{signal.trend_hint}</div>
    </div>
  )
}

const CJK_RE = /[一-鿿]/

export function timeAgo(ts) {
  if (!ts) return null
  const h = (Date.now() / 1000 - ts) / 3600
  if (h < 1) return `${Math.max(1, Math.round(h * 60))}分钟前`
  if (h < 24) return `${Math.round(h)}小时前`
  return `${Math.round(h / 24)}天前`
}

function News({ news }) {
  const [lang, setLang] = useState('all')
  if (!news?.items?.length) return null
  const sig = news.signal
  const counts = sig
    ? `${sig.positive} 利好 / ${sig.negative} 利空 / ${sig.neutral} 中性`
    : `${news.positive} 利好 / ${news.negative} 利空 / ${news.neutral} 中性`
  const items = news.items.filter((n) => {
    if (lang === 'zh') return CJK_RE.test(n.title)
    if (lang === 'en') return !CJK_RE.test(n.title)
    return true
  })
  return (
    <div className="panel">
      <h3>实时消息面（{counts}）</h3>
      <div className="quick-chips" style={{ marginBottom: 8 }}>
        {[['all', '全部'], ['zh', '中文'], ['en', 'English']].map(([k, label]) => (
          <span key={k} className="chip" onClick={() => setLang(k)}
            style={lang === k ? { borderColor: 'var(--accent)', color: 'var(--accent)' } : {}}>
            {label}
          </span>
        ))}
      </div>
      {items.map((n, i) => (
        <div className="news-item" key={i}>
          <div style={{ flex: 1 }}>
            <a href={n.link} target="_blank" rel="noreferrer">{n.title}</a>
            {timeAgo(n.published_ts) && <span className="news-time">{timeAgo(n.published_ts)}</span>}
            {n.events?.length > 0 && (
              <div className="event-tags">
                {n.events.map((e) => <span className="event-tag" key={e}>{e}</span>)}
              </div>
            )}
          </div>
          <span className={`sent ${n.impact_label || n.sentiment_label}`}>
            {n.impact_label || n.sentiment_label}
            {n.impact != null && Math.abs(n.impact) >= 1.5 ? '‼' : ''}
          </span>
        </div>
      ))}
    </div>
  )
}

// Claude 深度研报：点按生成（费用与真实兴趣成正比），服务端当日缓存
function DeepPanel({ ticker }) {
  const [state, setState] = useState('idle') // idle | loading | done
  const [result, setResult] = useState(null)

  useEffect(() => { setState('idle'); setResult(null) }, [ticker])

  const generate = () => {
    setState('loading')
    fetch(`/api/deep/${ticker}`, { signal: AbortSignal.timeout(90000) })
      .then((r) => r.json())
      .then((d) => { setResult(d); setState('done') })
      .catch(() => { setResult({ error: '生成超时，稍后再试。' }); setState('done') })
  }

  return (
    <div className="panel">
      <h3>AI 深度解读</h3>
      {state === 'idle' && (
        <>
          <p className="judge-notes" style={{ marginTop: 4 }}>
            让 Claude 通读本页全部结构化分析（多空对抗、模型回测、消息面、基本面），
            写一篇说人话的深度解读。约 20 秒，当日缓存。
          </p>
          <button className="grad-btn" style={{ marginTop: 8, padding: '6px 18px', fontSize: 12.5 }}
            onClick={generate}>生成今日深度解读</button>
        </>
      )}
      {state === 'loading' && (
        <div className="loading" style={{ padding: '12px 0' }}>
          <span className="spin" /> Claude 正在通读 {ticker} 的全部分析…
        </div>
      )}
      {state === 'done' && result?.text && (
        <div className="explain" style={{ marginTop: 6 }}>
          {result.text.split(/\n+/).filter((l) => l.trim() && !/^-{3,}$/.test(l.trim())).map((p, i) => {
            const h = p.match(/^#+\s*(.+)/)
            if (h) return <p key={i} style={{ fontWeight: 800, fontSize: 13.5, margin: '10px 0 4px' }}>{h[1]}</p>
            return <p key={i} style={{ marginBottom: 7 }}>{p.replace(/\*\*(.+?)\*\*/g, '$1')}</p>
          })}
          <div className="judge-notes" style={{ marginTop: 4 }}>
            由 {result.model || 'Claude'} 生成 · 当日缓存 · 不构成投资建议
          </div>
        </div>
      )}
      {state === 'done' && !result?.text && (
        <p className="judge-notes" style={{ marginTop: 6 }}>
          {result?.error || result?.note || '暂时生成不了，规则版解读不受影响。'}
        </p>
      )}
    </div>
  )
}

// 定价权/护城河评分：描述性财务画像，诚实标注"不是涨跌预测"
function MoatPanel({ ticker }) {
  const [m, setM] = useState(null)
  const [state, setState] = useState('loading')
  useEffect(() => {
    let alive = true
    setState('loading')
    fetch(`/api/moat/${ticker}`, { signal: AbortSignal.timeout(30000) })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (alive) { setM(d); setState('done') } })
      .catch(() => { if (alive) setState('done') })
    return () => { alive = false }
  }, [ticker])

  if (state === 'loading') return <div className="panel"><h3>定价权评分</h3><div className="loading"><span className="spin" /> 读财报…</div></div>
  if (!m) return null
  const pct = (v) => (v == null ? '—' : `${(v * 100).toFixed(0)}%`)
  const color = m.score >= 70 ? 'var(--up)' : m.score >= 55 ? 'var(--neutral)' : 'var(--text-dim)'
  return (
    <div className="panel">
      <h3>定价权评分 <span style={{ fontWeight: 400, fontSize: 11.5, color: 'var(--text-dim)' }}>护城河财务画像</span></h3>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, margin: '4px 0 8px' }}>
        <span style={{ fontSize: 30, fontWeight: 800, color }}>{m.score}</span>
        <span style={{ fontSize: 13, color }}>{m.tier}</span>
        <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>满分 100</span>
      </div>
      <div className="judge-notes" style={{ lineHeight: 1.9 }}>
        毛利率 <b>{pct(m.gross_margin)}</b> · 稳定度 <b>{(m.gross_margin_stability * 100).toFixed(0)}</b>
        {m.roe != null && <> · ROE <b>{pct(m.roe)}</b></>}
        {m.revenue_growth != null && <> · 营收增速 <b>{pct(m.revenue_growth)}</b></>}
        {m.n_years > 0 && <> · 取 {m.n_years} 年财报</>}
      </div>
      <div className="judge-notes" style={{ marginTop: 6, color: 'var(--neutral)' }}>
        ⚠这是描述公司「定价权」的财务画像，<b>不是涨跌预测</b>。我们诚实回测过：
        定价权高低单独并不能预测未来超额收益（高分组反而略跑输）——它帮你理解生意质量，不构成买卖信号。
      </div>
    </div>
  )
}

// 基本面动量：分析师盈利预期修正信号。诚实标注"无法回测、非买卖指令"。
function FundMomPanel({ ticker }) {
  const [m, setM] = useState(null)
  const [state, setState] = useState('loading')
  useEffect(() => {
    let alive = true
    setState('loading')
    fetch(`/api/fundmom/${ticker}`, { signal: AbortSignal.timeout(30000) })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (alive) { setM(d); setState('done') } })
      .catch(() => { if (alive) setState('done') })
    return () => { alive = false }
  }, [ticker])

  if (state === 'loading') return <div className="panel"><h3>盈利预期修正</h3><div className="loading"><span className="spin" /> 读分析师预期…</div></div>
  if (!m) return null
  const up = (m.revision_momentum_90d ?? 0) >= 0
  const color = m.score >= 68 ? 'var(--up)' : m.score >= 42 ? 'var(--neutral)' : 'var(--down)'
  return (
    <div className="panel">
      <h3>盈利预期修正 <span style={{ fontWeight: 400, fontSize: 11.5, color: 'var(--text-dim)' }}>分析师在上修还是下修</span></h3>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, margin: '4px 0 8px' }}>
        <span style={{ fontSize: 30, fontWeight: 800, color }}>{m.score}</span>
        <span style={{ fontSize: 13, color }}>{m.tier}</span>
        <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>满分 100</span>
      </div>
      <div className="judge-notes" style={{ lineHeight: 1.9 }}>
        {m.revision_momentum_90d != null && (
          <>一致预期 90 天{up ? '上修' : '下修'} <b style={{ color: up ? 'var(--up)' : 'var(--down)' }}>{(m.revision_momentum_90d * 100).toFixed(1)}%</b></>
        )}
        {m.revision_breadth_30d != null && <> · 近 30 天净{m.revision_breadth_30d >= 0 ? '上修' : '下修'}广度 <b>{(m.revision_breadth_30d * 100).toFixed(0)}%</b></>}
      </div>
      <div className="judge-notes" style={{ marginTop: 6, color: 'var(--neutral)' }}>
        ⚠盈利预期修正是学术上较稳的异象，但<b>免费数据没有历史预期序列，我们无法独立回测</b>它——
        作前瞻信号看，<b>不并入模型、不构成买卖指令</b>。
      </div>
    </div>
  )
}

function RiskStats({ risk }) {
  if (!risk) return null
  const rows = [
    ['年化波动率', `${(risk.annual_volatility * 100).toFixed(0)}%`],
    ['近一年收益', `${(risk.annual_return_1y * 100).toFixed(1)}%`],
    ['最大回撤', `${(risk.max_drawdown * 100).toFixed(0)}%`],
    ['夏普比率', risk.sharpe_ratio],
    ['单日VaR(95%)', `${(risk.var_95_daily * 100).toFixed(1)}%`],
    ['Beta(对标普)', risk.beta_vs_spy ?? '-'],
  ]
  return (
    <div className="panel">
      <h3>风险指标</h3>
      <div className="stats">
        {rows.map(([k, v]) => (
          <div className="stat" key={k}><div className="k">{k}</div><div className="v">{v}</div></div>
        ))}
      </div>
    </div>
  )
}

function BankPanel({ bank }) {
  if (!bank?.quarters?.length) return null
  const fmtB = (k) => (k == null ? '-' : `$${(k / 1e6).toFixed(0)}B`)
  return (
    <div className="panel">
      <h3>银行监管数据（{bank.source}）</h3>
      <div style={{ color: 'var(--text-dim)', fontSize: 12, marginBottom: 6 }}>
        实体：{bank.entity}（FDIC CERT {bank.cert}）
      </div>
      <table className="bank-table">
        <thead>
          <tr><th>季度</th><th>总资产</th><th>存款</th><th>净利润</th><th>ROE%</th><th>净息差%</th></tr>
        </thead>
        <tbody>
          {bank.quarters.slice(0, 6).map((q) => (
            <tr key={q.report_date}>
              <td>{q.report_date}</td>
              <td>{fmtB(q.total_assets_k)}</td>
              <td>{fmtB(q.total_deposits_k)}</td>
              <td>{q.net_income_k == null ? '-' : `$${(q.net_income_k / 1e3).toFixed(0)}M`}</td>
              <td>{q.roe ?? '-'}</td>
              <td>{q.net_interest_margin ?? '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function InsiderPanel({ insider }) {
  if (!insider?.summary) return null
  const s = insider.summary
  const fmtM = (v) => `$${(v / 1e6).toFixed(1)}M`
  return (
    <div className="panel">
      <h3>内部人交易（近 {insider.window_days} 天 · {insider.source}）</h3>
      <div className="judge-notes" style={{ marginBottom: 8 }}>
        买入 {s.n_buys} 笔（{fmtM(s.buy_value)}） vs 卖出 {s.n_sells} 笔（{fmtM(s.sell_value)}）
      </div>
      <div className="explain"><p>{s.judge}</p></div>
      {insider.items.length > 0 && (
        <table className="bank-table">
          <thead>
            <tr><th>日期</th><th>人物</th><th>类型</th><th>金额</th></tr>
          </thead>
          <tbody>
            {insider.items.slice(0, 8).map((it, i) => (
              <tr key={i}>
                <td>{it.date}</td>
                <td style={{ maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                  title={`${it.insider} (${it.position})`}>{it.insider}</td>
                <td style={{ color: it.type === 'buy' ? 'var(--up)' : it.type === 'sell' ? 'var(--down)' : 'var(--text-dim)' }}>
                  {it.type_cn}
                </td>
                <td>{it.value ? `$${(it.value / 1e6).toFixed(2)}M` : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function HoldersPanel({ holders }) {
  if (!holders?.items?.length) return null
  return (
    <div className="panel">
      <h3>机构持仓（{holders.source} · 前十合计 {(holders.top10_pct * 100).toFixed(0)}%）</h3>
      <table className="bank-table">
        <thead><tr><th>机构</th><th>持股比例</th><th>市值</th></tr></thead>
        <tbody>
          {holders.items.slice(0, 6).map((h, i) => (
            <tr key={i}>
              <td style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{h.holder}</td>
              <td>{h.pct_held != null ? `${(h.pct_held * 100).toFixed(2)}%` : '-'}</td>
              <td>{h.value != null ? `$${(h.value / 1e9).toFixed(1)}B` : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function EventsPanel({ events }) {
  if (!events) return null
  return (
    <div className="panel">
      <h3>财报日历与期权预期</h3>
      <div className="stats">
        {events.earnings_date && (
          <div className="stat">
            <div className="k">下次财报</div>
            <div className="v">{events.earnings_date}</div>
            <div className="k">还有 {events.days_to_earnings} 天</div>
          </div>
        )}
        {events.atm_iv != null && (
          <div className="stat">
            <div className="k">隐含波动率(ATM)</div>
            <div className="v">{(events.atm_iv * 100).toFixed(0)}%</div>
          </div>
        )}
        {events.implied_move_pct != null && (
          <div className="stat">
            <div className="k">隐含波动幅度</div>
            <div className="v">±{(events.implied_move_pct * 100).toFixed(1)}%</div>
          </div>
        )}
      </div>
      {events.implied_move_note && (
        <div className="judge-notes" style={{ marginTop: 8 }}>{events.implied_move_note}</div>
      )}
    </div>
  )
}

export default function StockDetail({ ticker, onOpenEarnings, watched, inFixedList, onToggleWatch }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    setData(null)
    setError(null)
    fetchStock(ticker)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e.message))
    return () => { alive = false }
  }, [ticker])

  if (error) return <div className="detail error">加载失败：{error}</div>
  if (!data) {
    return (
      <div className="detail loading">
        <span className="spin" /> 正在分析 {ticker}：拉取行情、新闻、基本面，训练模型并做对抗验证…
      </div>
    )
  }

  const up = data.quote.change_pct >= 0
  const ex = data.explanation

  return (
    <div className="detail">
      <div className="detail-header">
        <h2>
          {data.ticker} · {data.name_cn}
          {onOpenEarnings && (
            <button className="link-btn" onClick={() => onOpenEarnings(data.ticker)}>拆解财报</button>
          )}
          {onToggleWatch && !inFixedList && (
            <button className="link-btn" onClick={onToggleWatch}>
              {watched ? '★ 移出自选' : '☆ 加入自选'}
            </button>
          )}
        </h2>
        <div>
          <span className="price">{data.currency || '$'}{data.quote.price}</span>{' '}
          <span className={`chg ${up ? 'up' : 'down'}`}>
            {up ? '+' : ''}{data.quote.change} ({up ? '+' : ''}{data.quote.change_pct}%)
          </span>
          <span style={{ color: 'var(--text-dim)', fontSize: 12, marginLeft: 8 }}>
            截至 {data.quote.as_of}
          </span>
        </div>
      </div>

      {data.pitfalls?.length > 0 && (
        <div style={{ margin: '12px 0 0' }}>
          {data.pitfalls.map((p) => (
            <div className="pitfall-signpost" key={p.id}>
              <div className="pitfall-head">
                {p.emoji} 跌倒路标 · {p.title}
                {(JSON.parse(localStorage.getItem('sp_pitfall_profile') || '[]')).includes(p.id)
                  && <span className="danger-tag">你的高危区</span>}
              </div>
              <div className="judge-notes" style={{ marginTop: 3 }}>{p.context}</div>
              <div className="judge-notes" style={{ marginTop: 3, color: 'var(--up)' }}>
                {p.inversion}
              </div>
            </div>
          ))}
        </div>
      )}

      {ex.summary?.length > 0 && (
        <div className="judge-box" style={{ margin: '14px 0 4px', display: 'block' }}>
          <div style={{ fontWeight: 800, marginBottom: 6 }}>
            一页看懂
            <button className="link-btn" onClick={() => {
              const text = `【${data.name_cn} ${data.ticker} · 一页看懂】\n` + ex.summary.join('\n')
                + `\n—— 来自 明白股 https://mingbaigu.com`
              navigator.clipboard.writeText(text).then(() => alert('已复制，可以直接粘贴分享'))
            }}>复制分享</button>
          </div>
          <div className="explain">
            {ex.summary.map((l, i) => <p key={i} style={{ marginBottom: 6 }}>{l}</p>)}
          </div>
        </div>
      )}

      <PriceChart series={data.series} />

      <div className="detail-grid">
        <div>
          <Adversarial adv={data.adversarial} />
          <DeepPanel ticker={data.ticker} />
          <Explain title="消息面研判" lines={ex.news} />
          <Explain title="模型预判与对抗结论" lines={ex.prediction} />
          <Explain title="⚠风险解读" lines={ex.risk} />
          <Explain title="基本面解读" lines={ex.fundamentals} />
          <ValuePanel ticker={data.ticker} />
          <MoatPanel ticker={data.ticker} />
          <FundMomPanel ticker={data.ticker} />
          {ex.bank?.length > 0 && <Explain title="银行体检" lines={ex.bank} />}
        </div>
        <div>
          <NewsSignal signal={data.news?.signal} />
          <RiskStats risk={data.risk} />
          <EventsPanel events={data.events} />
          <InsiderPanel insider={data.insider} />
          <HoldersPanel holders={data.holders} />
          <News news={data.news} />
          <BankPanel bank={data.bank} />
        </div>
      </div>

      <div className="disclaimer">{data.disclaimer}</div>
    </div>
  )
}
