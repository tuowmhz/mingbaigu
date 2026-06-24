import { useEffect, useState } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

async function fetchQuant() {
  const res = await fetch('/api/quant', { signal: AbortSignal.timeout(30000) })
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}

function pct(v, digits = 1) {
  return v == null ? '-' : `${(v * 100).toFixed(digits)}%`
}

function BacktestPanel({ bt }) {
  const s = bt.stats.strategy
  const b = bt.stats.spy
  const rows = [
    ['年化收益', pct(s.cagr), pct(b.cagr)],
    ['年化波动', pct(s.annual_vol), pct(b.annual_vol)],
    ['夏普比率', s.sharpe, b.sharpe],
    ['最大回撤', pct(s.max_drawdown), pct(b.max_drawdown)],
    ['区间总收益', pct(s.total_return), pct(b.total_return)],
  ]
  return (
    <div className="panel">
      <h3>回测：多因子 Top{bt.top_n} vs SPY（月调仓，扣 {bt.cost_roundtrip_bps}bps 成本）</h3>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={bt.curve} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="rgba(255,255,255,.06)" strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fill: '#8b96a8', fontSize: 11 }} minTickGap={60}
            axisLine={{ stroke: 'rgba(255,255,255,.1)' }} tickLine={false} />
          <YAxis tick={{ fill: '#8b96a8', fontSize: 11 }} width={44}
            domain={['auto', 'auto']} tickFormatter={(v) => `${v}x`}
            axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{
            background: 'rgba(13,17,28,.92)', backdropFilter: 'blur(12px)',
            border: '1px solid rgba(255,255,255,.12)', borderRadius: 12,
          }} labelStyle={{ color: '#8b96a8' }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey="strategy" name="多因子策略" stroke="#00d68f" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="spy" name="SPY" stroke="#5ea0ff" dot={false} strokeWidth={1.5} />
        </LineChart>
      </ResponsiveContainer>
      <table className="bank-table" style={{ marginTop: 10 }}>
        <thead><tr><th>指标</th><th>策略</th><th>SPY</th></tr></thead>
        <tbody>
          {rows.map(([k, a, c]) => (
            <tr key={k}><td>{k}</td><td>{a}</td><td>{c}</td></tr>
          ))}
        </tbody>
      </table>
      <div className="judge-notes" style={{ marginTop: 8 }}>
        · 共 {bt.n_months} 个月样本，月度跑赢 SPY 的比例 {pct(bt.monthly_win_rate_vs_spy, 0)}，平均月换手 {pct(bt.avg_turnover, 0)}
      </div>
    </div>
  )
}

function FactorPanel({ factors, glossary }) {
  return (
    <div className="panel">
      <h3>因子体检（IC = 因子值与下月收益的秩相关）</h3>
      <table className="bank-table">
        <thead>
          <tr><th>因子</th><th>月均IC</th><th>IC IR</th><th>IC&gt;0月份</th></tr>
        </thead>
        <tbody>
          {factors.map((f) => (
            <tr key={f.key}>
              <td title={f.desc_cn}>{f.name_cn}</td>
              <td style={{ color: f.ic_mean > 0 ? 'var(--up)' : 'var(--down)' }}>{f.ic_mean}</td>
              <td>{f.ic_ir ?? '-'}</td>
              <td>{pct(f.ic_positive_pct, 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="judge-notes" style={{ marginTop: 8 }}>
        {Object.entries(glossary).filter(([, g]) => !g.backtestable).map(([k, g]) => (
          <div key={k}>· {g.name_cn}（财报因子，只参与当前打分不进回测）：{g.desc_cn}</div>
        ))}
      </div>
    </div>
  )
}

function RankingPanel({ ranking }) {
  return (
    <div className="panel">
      <h3>当前综合得分 Top 20（价格因子 50% + 财报因子 50%）</h3>
      <table className="bank-table">
        <thead>
          <tr><th>#</th><th>代码</th><th>公司</th><th>综合</th><th>动量类</th><th>价值</th><th>质量</th><th>成长</th></tr>
        </thead>
        <tbody>
          {ranking.map((r, i) => (
            <tr key={r.ticker}>
              <td>{i + 1}</td>
              <td><b>{r.ticker}</b></td>
              <td style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.name}</td>
              <td><b>{r.score}</b></td>
              <td>{r.price_score}</td>
              <td>{r.value}</td>
              <td>{r.quality}</td>
              <td>{r.growth}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PortfolioPanel({ portfolio }) {
  if (!portfolio) return null
  const s = portfolio.stats
  const e = portfolio.equal_weight_stats
  const maxW = Math.max(...portfolio.weights.map((w) => w.weight))
  return (
    <div className="panel">
      <h3>组合优化（{portfolio.method}）</h3>
      {portfolio.weights.map((w) => (
        <div className="weight-row" key={w.ticker}>
          <span className="weight-ticker">{w.ticker}</span>
          <div className="weight-bar-track">
            <div className="weight-bar" style={{ width: `${(w.weight / maxW) * 100}%` }} />
          </div>
          <span className="weight-val">{pct(w.weight)}</span>
        </div>
      ))}
      <table className="bank-table" style={{ marginTop: 10 }}>
        <thead><tr><th>口径</th><th>预期年化收益</th><th>预期波动</th><th>预期夏普</th></tr></thead>
        <tbody>
          <tr><td>优化组合</td><td>{pct(s.exp_return)}</td><td>{pct(s.exp_vol)}</td><td>{s.exp_sharpe}</td></tr>
          <tr><td>等权对照</td><td>{pct(e.exp_return)}</td><td>{pct(e.exp_vol)}</td><td>{e.exp_sharpe}</td></tr>
        </tbody>
      </table>
      <div className="judge-notes" style={{ marginTop: 8 }}>· {portfolio.note}</div>
    </div>
  )
}

function ZooPanel() {
  const [zoo, setZoo] = useState(null)
  useEffect(() => {
    let alive = true
    let timer
    const poll = () => fetch('/api/zoo').then((r) => r.json()).then((d) => {
      if (!alive) return
      setZoo(d)
      if (d.status === 'building') timer = setTimeout(poll, 10000)
    }).catch(() => {})
    poll()
    return () => { alive = false; clearTimeout(timer) }
  }, [])

  if (!zoo) return null
  if (zoo.status === 'building') {
    return (
      <div className="loading" style={{ padding: 20 }}>
        <span className="spin" /> 策略动物园构建中（102 个策略 × 10 年回测，约 1 分钟）…
      </div>
    )
  }

  const a = zoo.analysis
  const c = zoo.composite
  return (
    <div style={{ marginTop: 26 }}>
      <div className="detail-header">
        <h2>策略动物园 · {zoo.meta.n_strategies} 个开源族系策略统一回测</h2>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>
          {zoo.meta.is_period}（样本内）→ {zoo.meta.oos_period}（样本外） · {zoo.meta.sources}
        </span>
      </div>

      <div className="judge-box" style={{ margin: '12px 0' }}>
        <div className="judge-main">
          <div className="judge-line">
            <span className="verdict bullish">拟合组合策略</span>
            <span style={{ fontSize: 13 }}>{c.recipe}</span>
          </div>
          <div className="judge-notes">
            样本外夏普 <b>{c.oos_sharpe}</b>（样本内 {c.is_sharpe}）·
            {c.oos_months} 个月总回报 <b>{(c.oos_total_return * 100).toFixed(0)}%</b> vs QQQ {(c.qqq_total_return * 100).toFixed(0)}% ·
            跑赢动物园 {(c.oos_percentile * 100).toFixed(0)}% 的策略
          </div>
        </div>
      </div>

      <div className="detail-grid">
        <div className="panel">
          <h3>策略族系战绩（中位夏普，按样本外排序）</h3>
          <table className="bank-table">
            <thead><tr><th>族系</th><th>数量</th><th>样本内</th><th>样本外</th></tr></thead>
            <tbody>
              {a.families.map((f) => (
                <tr key={f.family}>
                  <td>{f.family}</td><td>{f.n}</td><td>{f.is_sharpe_med}</td>
                  <td style={{ fontWeight: 700, color: f.oos_sharpe_med > 1.4 ? 'var(--up)' : f.oos_sharpe_med < 1 ? 'var(--down)' : 'inherit' }}>
                    {f.oos_sharpe_med}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <div className="panel">
            <h3>统计共性：哪些'成分'真的有用（对样本外夏普的提升）</h3>
            <table className="bank-table">
              <thead><tr><th style={{ textAlign: 'left' }}>成分</th><th>含此成分</th><th>不含/全体</th><th>提升</th></tr></thead>
              <tbody>
                {a.effects.map((e) => (
                  <tr key={e.ingredient}>
                    <td style={{ textAlign: 'left' }}>{e.ingredient}</td>
                    <td>{e.with_avg}</td><td>{e.without_avg}</td>
                    <td style={{ fontWeight: 700, color: e.lift > 0 ? 'var(--up)' : 'var(--down)' }}>
                      {e.lift > 0 ? '+' : ''}{e.lift}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="judge-notes" style={{ marginTop: 6 }}>
              · IS→OOS 夏普秩相关：<b>{a.is_oos_corr}</b> · 样本内前十策略：IS {a.decay.top10_is_avg_is_sharpe} → OOS {a.decay.top10_is_avg_oos_sharpe}（全体 {a.decay.all_avg_oos_sharpe}）
            </div>
          </div>
        </div>
      </div>

      {zoo.honest_notes.map((n, i) => <div className="disclaimer" key={i}>⚠{n}</div>)}
    </div>
  )
}

function Famous13F() {
  const [data, setData] = useState(null)
  useEffect(() => {
    let alive = true
    fetch('/api/13f').then((r) => r.json()).then((d) => alive && setData(d)).catch(() => {})
    return () => { alive = false }
  }, [])
  if (!data) return null
  return (
    <div style={{ marginTop: 22 }}>
      <div className="detail-header"><h2>大佬持仓 · 13F</h2>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>{data.source}</span>
      </div>
      {data.unavailable_reason ? (
        <div className="disclaimer" style={{ marginTop: 10 }}>⚠{data.unavailable_reason}</div>
      ) : (
        <div className="stats" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', marginTop: 12 }}>
          {data.filers.map((f) => (
            <div className="stat" key={f.cik}>
              <div className="k" style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>{f.name}</div>
              <table className="bank-table" style={{ marginTop: 6 }}>
                <tbody>
                  {f.holdings.slice(0, 8).map((h) => (
                    <tr key={h.issuer}>
                      <td style={{ maxWidth: 170, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{h.issuer}</td>
                      <td>{(h.weight * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
      {!data.unavailable_reason && <div className="judge-notes" style={{ marginTop: 8 }}>· {data.note}</div>}
    </div>
  )
}

function LongTermPanel() {
  const [lt, setLt] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let alive = true
    fetch('/api/longterm').then((r) => r.json())
      .then((d) => alive && setLt(d)).catch((e) => alive && setErr(e.message))
    return () => { alive = false }
  }, [])

  if (err) return <div className="error">一年期模型加载失败：{err}</div>
  if (!lt) {
    return (
      <div className="loading" style={{ padding: 24 }}>
        <span className="spin" /> 一年期展望模型构建中（10 年数据 × 100 只股票，首次约 2-3 分钟）…
      </div>
    )
  }

  return (
    <>
      <div className="detail-header" style={{ marginTop: 26 }}>
        <h2>一年期展望 · 对标 {lt.benchmark}</h2>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>
          {lt.n_samples.toLocaleString()} 个训练样本 · purged walk-forward（12 个月禁运）· 截至 {lt.as_of}
        </span>
      </div>

      <div className="judge-box" style={{ margin: '12px 0 18px' }}>
        <div className="judge-main">
          <div className="judge-line">
            <span className={`verdict ${lt.avg_excess > 0.02 ? 'bullish' : lt.avg_excess < 0 ? 'bearish' : 'neutral'}`}>
              {lt.n_test_years} 年样本外：{lt.wins_vs_qqq} 胜 {lt.n_test_years - lt.wins_vs_qqq} 负
            </span>
            <span>平均年超额 {pct(lt.avg_excess)} · 平均 IC {lt.avg_ic ?? '-'}</span>
          </div>
          <div className="judge-notes">{lt.verdict}</div>
        </div>
      </div>

      <div className="detail-grid">
        <div className="panel">
          <h3>逐年样本外战绩（年初建仓 Top10 持有一年）</h3>
          <table className="bank-table">
            <thead>
              <tr><th>年份</th><th>组合收益</th><th>QQQ</th><th>超额</th><th>IC</th></tr>
            </thead>
            <tbody>
              {lt.yearly.map((r) => (
                <tr key={r.year}>
                  <td>{r.year}</td>
                  <td>{pct(r.portfolio_return)}</td>
                  <td>{pct(r.qqq_return)}</td>
                  <td style={{ color: r.excess > 0 ? 'var(--up)' : 'var(--down)', fontWeight: 700 }}>
                    {r.excess > 0 ? '+' : ''}{(r.excess * 100).toFixed(1)}%
                  </td>
                  <td>{r.ic ?? '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="panel">
          <h3>当前一年期相对看好（预测超额排序，非收益承诺）</h3>
          <table className="bank-table">
            <thead>
              <tr><th>代码</th><th>预测1年超额</th><th>12月动量</th><th>相对强度</th><th>波动率</th></tr>
            </thead>
            <tbody>
              {lt.current_picks.map((p) => (
                <tr key={p.ticker}>
                  <td><b>{p.ticker}</b></td>
                  <td style={{ color: p.predicted_excess_1y > 0 ? 'var(--up)' : 'var(--down)' }}>
                    {pct(p.predicted_excess_1y)}
                  </td>
                  <td>{pct(p.mom_12)}</td>
                  <td>{pct(p.rel_strength_12)}</td>
                  <td>{pct(p.vol_12)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {lt.disclaimers.map((d, i) => <div className="disclaimer" key={i}>⚠{d}</div>)}
    </>
  )
}

export default function QuantView() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    let timer
    const poll = () => {
      fetchQuant()
        .then((d) => {
          if (!alive) return
          setData(d)
          if (d.status === 'building') timer = setTimeout(poll, 8000)
        })
        .catch((e) => alive && setError(e.message))
    }
    poll()
    return () => { alive = false; clearTimeout(timer) }
  }, [])

  if (error) return <div className="detail error">加载失败：{error}</div>
  if (!data) return <div className="detail loading"><span className="spin" /> 加载量化结果…</div>
  if (data.status === 'building') {
    return (
      <div className="detail loading">
        <span className="spin" /> 量化管线构建中（拉取 100 只股票数据、清洗、因子、回测、优化，约 2-4 分钟）…
        {data.error && <div className="error">上次构建失败：{data.error}</div>}
      </div>
    )
  }

  const m = data.meta
  return (
    <div className="detail">
      <div className="detail-header">
        <h2>量化组合 · {m.universe}</h2>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>
          数据 {m.price_start} ~ {m.price_end} · 实际使用 {m.n_used} 只 · 生成于 {m.generated_at}
        </span>
      </div>

      <div className="detail-grid">
        <div>
          <BacktestPanel bt={data.backtest} />
          <FactorPanel factors={data.backtest.factors} glossary={data.factor_glossary} />
        </div>
        <div>
          <PortfolioPanel portfolio={data.portfolio} />
          <RankingPanel ranking={data.ranking} />
        </div>
      </div>

      {m.disclaimers.map((d, i) => (
        <div className="disclaimer" key={i}>⚠{d}</div>
      ))}

      <LongTermPanel />
      <ZooPanel />
      <Famous13F />
    </div>
  )
}
