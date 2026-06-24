import { useEffect, useState } from 'react'
import { timeAgo } from './StockDetail.jsx'

const pct = (v, d = 0) => (v == null ? '-' : `${v > 0 ? '+' : ''}${(v * 100).toFixed(d)}%`)

function growthColor(v) {
  if (v == null) return 'var(--text-dim)'
  if (v > 0.15) return 'var(--up)'
  if (v < 0) return 'var(--down)'
  return 'var(--neutral)'
}

function valueColor(s) {
  if (!s || s === '-') return 'var(--text-dim)'
  return s.startsWith('+') ? 'var(--up)' : s.startsWith('-') ? 'var(--down)' : 'var(--neutral)'
}

function Transmission({ tr }) {
  return (
    <div className="panel">
      <h3>财报传导链（钱怎么沿产业链流动）</h3>
      <div className="trans-flow">
        {tr.steps.map((s, i) => (
          <div className="trans-step-wrap" key={s.label}>
            <div className="trans-step">
              <div className="trans-label">{s.label}</div>
              <div className="trans-value" style={{ color: valueColor(s.value) }}>{s.value}</div>
              <div className="trans-note">{s.note}</div>
            </div>
            {i < tr.steps.length - 1 && <div className="trans-arrow">→</div>}
          </div>
        ))}
      </div>
      <div className="judge-notes" style={{ marginTop: 10 }}>{tr.detail}</div>
    </div>
  )
}

function LayerFlow({ layers, onOpenEarnings }) {
  return (
    <div className="panel">
      <h3>产业链全景（上游 → 下游，点击公司看财报拆解）</h3>
      {layers.map((l, i) => (
        <div key={l.layer}>
          <div className={`layer-row ${l.health}`}>
            <div className="layer-head">
              <div className="layer-name">{l.layer}
                <span className={`badge ${l.health === 'strong' ? 'bullish' : l.health === 'weak' ? 'bearish' : 'neutral'}`}
                  style={{ marginLeft: 8 }}>
                  {l.health_cn} {pct(l.avg_revenue_growth)}
                </span>
                {l.logic && (
                  <span className="badge" style={{ marginLeft: 6, color: 'var(--cyan)', borderColor: 'rgba(34,211,238,.4)' }}>
                    {l.logic}
                  </span>
                )}
              </div>
              <div className="layer-desc">{l.desc}</div>
            </div>
            <div className="layer-companies">
              {l.companies.map((c) => (
                <span className="company-chip" key={c.ticker} title={c.role}
                  onClick={() => onOpenEarnings && onOpenEarnings(c.ticker)}>
                  <b>{c.ticker}</b> {c.name_cn}
                  <span style={{ color: growthColor(c.revenue_growth), marginLeft: 6 }}>
                    {pct(c.revenue_growth)}
                  </span>
                </span>
              ))}
            </div>
          </div>
          {i < layers.length - 1 && <div className="layer-arrow">▼</div>}
        </div>
      ))}
    </div>
  )
}

function MiniTable({ rows, columns }) {
  return (
    <div className="research-table-wrap">
      <table className="bank-table research-table">
        <thead>
          <tr>{columns.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.stage || r.type || r.route || i}>
              {columns.map((c) => <td key={c.key}>{r[c.key]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DriverTree({ title, rows }) {
  return (
    <div className="research-tree">
      <div className="research-tree-root">{title}</div>
      {rows.map((r) => (
        <div className="research-tree-branch" key={r.driver}>
          <b>{r.driver}</b>
          <div>{(r.reasons || r.items || []).join(' / ')}</div>
        </div>
      ))}
    </div>
  )
}

function OpportunityCard({ op, i }) {
  return (
    <div className="opp-card">
      <div className="opp-head">
        <span className="badge bullish">Opportunity #{i + 1}</span>
        <b>{op.name}</b>
      </div>
      <p>{op.why}</p>
      <div className="opp-grid">
        <div><span>市场空间</span>{op.market}</div>
        <div><span>最受益环节</span>{op.beneficiaries}</div>
        <div><span>潜在龙头</span>{op.leaders?.join(' / ')}</div>
        <div><span>超额收益来源</span>{op.alpha}</div>
      </div>
      <div className="research-tags">
        {op.signals?.map((s) => <span key={s}>信号：{s}</span>)}
      </div>
      <div className="research-tags muted">
        {op.metrics?.map((s) => <span key={s}>验证：{s}</span>)}
        {op.failure?.map((s) => <span key={s}>失效：{s}</span>)}
      </div>
      <div className="judge-notes">市场错在哪里：{op.mispricing}</div>
    </div>
  )
}

export function ResearchReport({ research }) {
  if (!research) return null
  return (
    <div className="panel research-report">
      <h3>产业机会地图（机构投研版）</h3>

      <div className="research-hero">
        <div>
          <div className="research-kicker">一句话定义</div>
          <p>{research.definition.one_liner}</p>
        </div>
        <div className="research-live">
          <span>实时验证信号</span>
          <b>{research.live_signal}</b>
        </div>
      </div>

      <div className="research-3col">
        <div><b>需求本质</b><p>{research.definition.demand}</p></div>
        <div><b>商业本质</b><p>{research.definition.business}</p></div>
        <div><b>利润本质</b><p>{research.definition.profit}</p></div>
      </div>

      <div className="research-answer-grid">
        {research.answers.map((a) => <div key={a}>{a}</div>)}
      </div>

      {research.fact_checks?.length > 0 && (
        <div className="research-box">
          <h4>关键事实校准</h4>
          <div className="research-tags facts">
            {research.fact_checks.map((f) => <span key={f}>{f}</span>)}
          </div>
        </div>
      )}

      <h4>价值流与资金流</h4>
      <MiniTable rows={research.value_chain} columns={[
        { key: 'stage', label: '环节' },
        { key: 'revenue', label: '收入来源' },
        { key: 'margin', label: '毛利率' },
        { key: 'moat', label: '护城河' },
        { key: 'pricing_power', label: '议价能力' },
      ]} />

      <h4>卡脖子环节</h4>
      <MiniTable rows={research.bottlenecks} columns={[
        { key: 'stage', label: '环节' },
        { key: 'substitution', label: '替代难度' },
        { key: 'tech', label: '技术壁垒' },
        { key: 'capital', label: '资本壁垒' },
        { key: 'time', label: '时间壁垒' },
      ]} />

      <div className="research-2col">
        <DriverTree title="需求驱动树" rows={research.demand_tree} />
        <DriverTree title="供给驱动树" rows={research.supply_tree} />
      </div>

      <div className="research-2col">
        <div className="research-box">
          <h4>产业周期定位</h4>
          <p><b>{research.cycle.stage}</b></p>
          <p>{research.cycle.path}</p>
          <div className="judge-notes">最大误判：{research.cycle.misread}</div>
        </div>
        <div className="research-box">
          <h4>未来十年权力迁移</h4>
          <p>今天的赢家：{research.ten_year.today_winners}</p>
          <p>未来的赢家：{research.ten_year.future_winners}</p>
          <p>今天的利润池：{research.ten_year.today_profit_pool}</p>
          <p>未来的利润池：{research.ten_year.future_profit_pool}</p>
        </div>
      </div>

      <h4>利润迁移路径</h4>
      <div className="research-4grid">
        {Object.entries(research.profit_migration).map(([k, v]) => (
          <div key={k}>
            <b>{{
              past_winners: '过去赢家',
              future_winners: '未来赢家',
              past_losers: '过去输家',
              future_losers: '未来输家',
            }[k]}</b>
            <p>{v.join(' / ')}</p>
          </div>
        ))}
      </div>

      <h4>技术路线竞争地图</h4>
      <MiniTable rows={research.tech_routes} columns={[
        { key: 'route', label: '路线' },
        { key: 'maturity', label: '成熟度' },
        { key: 'commercial', label: '商业化时间' },
        { key: 'cost_curve', label: '成本曲线' },
        { key: 'win_rate', label: '胜率' },
      ]} />

      <div className="research-box">
        <h4>Porter Five Forces</h4>
        <div className="research-tags">
          {research.five_forces.map((f) => <span key={f}>{f}</span>)}
        </div>
      </div>

      <h4>未来 3-5 年机会窗口</h4>
      <div className="opp-list">
        {research.opportunities.map((op, i) => <OpportunityCard op={op} i={i} key={op.name} />)}
      </div>

      <h4>投资人视角</h4>
      <MiniTable rows={research.investor_views} columns={[
        { key: 'type', label: '投资人' },
        { key: 'position', label: '会投哪里' },
        { key: 'risk', label: '核心风险' },
      ]} />

      <div className="research-2col">
        <div className="research-box">
          <h4>Agent 下一步研究任务</h4>
          {research.research_tasks.map((t) => <p key={t}>• {t}</p>)}
        </div>
        <div className="research-box conclusion">
          <h4>最终投资结论</h4>
          <p>{research.conclusion.sentence}</p>
          {research.conclusion.ratings.map((r) => (
            <div className="rating-row" key={r.rating}>
              <b>{r.rating}</b><span>{r.items.join(' / ')}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="research-disclaimer">
        ⚠评级针对产业「环节」而非个股；代表性公司仅作举例、非推荐。本机会地图是教育性结构分析，基于公开认知可能过时或有误，<b>不构成投资建议</b>，请自行核实。
      </div>
    </div>
  )
}

function NewsStream({ title, news }) {
  if (!news?.items?.length) return null
  return (
    <div className="panel">
      <h3>{title}（{news.positive} 利好 / {news.negative} 利空 · 信号 {news.score > 0 ? '+' : ''}{news.score} {news.direction_cn}）</h3>
      {news.items.slice(0, 14).map((n, i) => (
        <div className="news-item" key={i}>
          <div style={{ flex: 1 }}>
            <a href={n.link} target="_blank" rel="noreferrer">{n.title}</a>
            {timeAgo(n.published_ts) && <span className="news-time">{timeAgo(n.published_ts)}</span>}
            <div className="event-tags">
              <span className="source-badge">{n.source}</span>
              {n.events?.slice(0, 2).map((e) => <span className="event-tag" key={e}>{e}</span>)}
            </div>
          </div>
          <span className={`sent ${n.impact_label}`}>{n.impact_label}</span>
        </div>
      ))}
    </div>
  )
}

export default function ChainView({ onOpenEarnings }) {
  const [market, setMarket] = useState('US')
  const [chains, setChains] = useState({})
  const [aiNews, setAiNews] = useState(null)
  const [marketNews, setMarketNews] = useState(null)
  const [cnNews, setCnNews] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    if (!chains[market]) {
      fetch(`/api/chain/ai?market=${market}`, { signal: AbortSignal.timeout(180000) })
        .then((r) => r.json())
        .then((d) => alive && setChains((prev) => ({ ...prev, [market]: d })))
        .catch((e) => alive && setError(e.message))
    }
    if (market === 'CN' && !cnNews) {
      fetch('/api/news/cn').then((r) => r.json())
        .then((d) => alive && setCnNews(d)).catch(() => {})
    }
    return () => { alive = false }
  }, [market])

  useEffect(() => {
    let alive = true
    fetch('/api/news/ai').then((r) => r.json())
      .then((d) => alive && setAiNews(d)).catch(() => {})
    fetch('/api/news/market').then((r) => r.json())
      .then((d) => alive && setMarketNews(d)).catch(() => {})
    return () => { alive = false }
  }, [])

  const chain = chains[market]

  const toggle = (
    <span className="nav" style={{ marginLeft: 0 }}>
      <button className={market === 'US' ? 'active' : ''} onClick={() => setMarket('US')}>美股链</button>
      <button className={market === 'CN' ? 'active' : ''} onClick={() => setMarket('CN')}>A股链</button>
    </span>
  )

  if (error) return <div className="detail error">加载失败：{error}</div>
  if (!chain) {
    return (
      <div className="detail">
        <div className="detail-header"><h2>AI 产业链 · 第一性原理</h2>{toggle}</div>
        <div className="loading">
          <span className="spin" /> 正在构建{market === 'CN' ? 'A股' : '美股'} AI 产业链图谱：拉取财报与资本开支数据（首次约 1 分钟）…
        </div>
      </div>
    )
  }

  return (
    <div className="detail">
      <div className="detail-header">
        <h2>{chain.title} · 第一性原理</h2>
        {toggle}
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>
          {chain.n_companies} 家公司 · 财报数据实时验证传导链
        </span>
      </div>

      <Transmission tr={chain.transmission} />
      <ResearchReport research={chain.research} />

      <div className="detail-grid">
        <div>
          <LayerFlow layers={chain.layers} onOpenEarnings={onOpenEarnings} />
        </div>
        <div>
          <div className="panel explain">
            <h3>第一性原理解读</h3>
            {chain.narrative.map((n, i) => <p key={i}>{n}</p>)}
          </div>
          {market === 'CN' && <NewsStream title="A股实时快讯（东方财富 7×24）" news={cnNews} />}
          <NewsStream title="AI 产业链要闻" news={aiNews} />
          <NewsStream title="宏观市场要闻" news={marketNews} />
        </div>
      </div>
    </div>
  )
}
