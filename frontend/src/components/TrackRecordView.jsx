import { useEffect, useState } from 'react'

// 公开成绩单："别信我们，查我们。"
async function fetchRetry(url, tries = 3) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(60000) })
      if (r.ok) return r.json()
    } catch {}
    await new Promise((res) => setTimeout(res, 2000))
  }
  return null
}

function Row({ r, showOutcome }) {
  const hit = r.hit
  return (
    <tr>
      <td>{r.date}</td>
      <td>{r.name}<span style={{ color: 'var(--text-dim)', fontSize: 10.5, marginLeft: 5 }}>{r.ticker}</span></td>
      <td>
        <span style={{ color: r.verdict === 'bullish' ? 'var(--up)' : r.verdict === 'bearish' ? 'var(--down)' : 'var(--text-dim)' }}>
          {r.verdict_cn}
        </span>
        <span style={{ color: 'var(--text-dim)', fontSize: 10.5, marginLeft: 5 }}>
          {r.prob_up != null ? `跑赢概率${Math.round(r.prob_up * 100)}%` : ''}
        </span>
      </td>
      {showOutcome ? (
        <>
          <td style={{ color: (r.excess_pct ?? 0) >= 0 ? 'var(--up)' : 'var(--down)' }}>
            {(r.excess_pct ?? 0) > 0 ? '+' : ''}{r.excess_pct ?? '—'}%
            <span style={{ color: 'var(--text-dim)', fontSize: 10, marginLeft: 4 }}>
              （自身{r.return_pct > 0 ? '+' : ''}{r.return_pct}%）
            </span>
          </td>
          <td>{hit ? '✅ 跑赢' : '❌ 没跑赢'}</td>
        </>
      ) : (
        <td style={{ color: 'var(--text-dim)' }}>已公证，待对账</td>
      )}
    </tr>
  )
}

export default function TrackRecordView() {
  const [data, setData] = useState(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    fetchRetry('/api/track-record').then((d) => {
      if (cancelled) return
      if (d) setData(d)
      else setTimeout(() => !cancelled && setAttempt((a) => a + 1), 4000)
    })
    return () => { cancelled = true }
  }, [attempt])

  if (!data) return <div className="detail loading"><span className="spin" /> 正在核对历史档案…</div>

  const s = data.stats
  const pct = (v) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`)

  return (
    <div className="detail">
      <div className="detail-header">
        <h2>公开成绩单</h2>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>错的不删 · 亏的置顶 · 全量存档无挑选</span>
      </div>

      <div className="judge-box" style={{ margin: '14px 0', display: 'block' }}>
        <div style={{ fontWeight: 800, marginBottom: 6 }}>别信我们，查我们。</div>
        <div className="judge-notes">
          每个交易日，观察列表的全部模型预测都会被存档，并由公开 GitHub 仓库的
          commit 时间戳公证——我们无法事后修改任何一天"说过什么"。
          满约半年（126 个交易日）后自动对账，以"是否跑赢大盘"为准，结果如下，好坏都在。
        </div>
        <a className="grad-btn" style={{ display: 'inline-block', marginTop: 10, padding: '6px 16px', fontSize: 12.5, textDecoration: 'none' }}
          href={data.repo_url} target="_blank" rel="noreferrer">去 GitHub 验证公证档案 ↗</a>
      </div>

      <div className="quick-chips" style={{ marginBottom: 6 }}>
        <span className="chip">已公证 {data.n_snapshots} 天</span>
        <span className="chip">已对账 {s.n_judged} 条</span>
        <span className="chip">跑赢命中率 {pct(s.hit_rate)}</span>
        <span className="chip">随机基准 {pct(s.baseline_hit_rate)}</span>
        <span className="chip">待对账 {s.n_pending} 条</span>
      </div>
      {s.hit_rate != null && s.baseline_hit_rate != null && s.hit_rate <= s.baseline_hit_rate && (
        <div className="judge-notes" style={{ color: 'var(--down)', marginBottom: 8 }}>
          ⚠截至目前，我们的裁决没有跑赢"随机猜"基准。这正是要公开的原因——你该知道。
        </div>
      )}

      {data.worst_misses?.length > 0 && (
        <div className="panel" style={{ borderColor: 'rgba(255,84,112,.35)' }}>
          <h3>我们错得最狠的</h3>
          <table className="bank-table">
            <thead><tr><th>日期</th><th>股票</th><th>我们说</th><th>半年后 vs 大盘</th><th>结果</th></tr></thead>
            <tbody>{data.worst_misses.map((r, i) => <Row key={i} r={r} showOutcome />)}</tbody>
          </table>
        </div>
      )}

      {data.entries?.length > 0 ? (
        <div className="panel">
          <h3>全部已对账预测（近 {data.entries.length} 条）</h3>
          <table className="bank-table">
            <thead><tr><th>日期</th><th>股票</th><th>我们说</th><th>半年后 vs 大盘</th><th>结果</th></tr></thead>
            <tbody>{data.entries.map((r, i) => <Row key={i} r={r} showOutcome />)}</tbody>
          </table>
        </div>
      ) : (
        <div className="panel">
          <h3>对账进行中</h3>
          <p className="judge-notes">
            成绩单刚启动：第一批预测已存档并公证，满约半年（126 交易日）后这里会出现第一批对账结果——无论好坏。
          </p>
        </div>
      )}

      {data.pending?.length > 0 && (
        <div className="panel">
          <h3>已公证、待对账（{data.pending.length} 条）</h3>
          <table className="bank-table">
            <thead><tr><th>日期</th><th>股票</th><th>我们说</th><th>状态</th></tr></thead>
            <tbody>{data.pending.slice(0, 30).map((r, i) => <Row key={i} r={r} showOutcome={false} />)}</tbody>
          </table>
        </div>
      )}

      <div className="judge-notes" style={{ marginTop: 10 }}>{data.methodology}</div>
      <div className="disclaimer">{data.disclaimer}</div>
    </div>
  )
}
