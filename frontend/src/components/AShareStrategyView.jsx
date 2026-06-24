import { useEffect, useState } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

async function fetchStrategy() {
  const res = await fetch('/api/strategy/ashare', { signal: AbortSignal.timeout(20000) })
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}

const pct = (v, d = 1) => (v == null ? '—' : `${(v * 100).toFixed(d)}%`)
const sign = (v, d = 1) => (v == null ? '—' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(d)}%`)

function Stat({ label, value, color }) {
  return (
    <div className="stat-cell">
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={color ? { color } : {}}>{value}</div>
    </div>
  )
}

export default function AShareStrategyView() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchStrategy().then(setData).catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="error">加载失败：{error}</div>
  if (!data) return <div className="panel"><h3>低波蓝筹 · A股低频多因子</h3><p>加载中…</p></div>
  if (data.status === 'empty') {
    return <div className="panel"><h3>低波蓝筹 · A股低频多因子</h3>
      <p>实验尚未建仓。生成首期持仓后这里会显示纸面跟踪净值。</p></div>
  }

  const s = data.stats
  const live = s.n_months_live
  return (
    <div className="quant-view">
      <div className="panel">
        <h3>{data.strategy_name}
          <span className="badge" style={{ marginLeft: 8, background: 'rgba(94,160,255,.15)', color: '#5ea0ff' }}>
            纸面跟踪 · 未投真金
          </span>
        </h3>
        <p className="judge-notes" style={{ margin: '2px 0 10px' }}>
          股票池 {data.universe_cn} · 每月调仓 · 等权前 {data.current_holdings.length} 只 ·
          因子：{data.factors_used_cn.join(' + ')} · 建仓日 {data.inception_date} ·
          对标 {data.benchmark_cn}
        </p>

        <div className="stat-row" style={{ display: 'flex', flexWrap: 'wrap', gap: 12, margin: '8px 0 14px' }}>
          <Stat label={`建仓以来 (${live}个月)`} value={sign(s.total_strategy)}
            color={s.total_strategy >= 0 ? '#00d68f' : '#ff5c7c'} />
          <Stat label="同期沪深300" value={sign(s.total_bench)} />
          <Stat label="超额收益" value={sign(s.total_excess)}
            color={s.total_excess >= 0 ? '#00d68f' : '#ff5c7c'} />
          <Stat label="月度胜率" value={s.monthly_win_rate == null ? '—' : pct(s.monthly_win_rate, 0)} />
          <Stat label="最大回撤" value={s.max_drawdown == null ? '—' : pct(s.max_drawdown)} color="#ff5c7c" />
          <Stat label="年化(满半年才算)" value={s.annualized == null ? '尚不足' : pct(s.annualized)} />
        </div>

        <div className="callout" style={{ padding: '8px 12px', borderRadius: 10, marginBottom: 12, fontSize: 13, background: 'rgba(255,200,80,.10)', color: '#ffcf6b' }}>
          下次调仓日：<b>{data.next_rebalance}</b> · 每月底按因子重新选股、等权换仓一次（手动执行，换仓快照会即时 git 公证）。
        </div>

        {live === 0 ? (
          <div className="callout" style={{ padding: '10px 12px', borderRadius: 10, background: 'rgba(255,255,255,.04)' }}>
            ✅ 已于 <b>{data.inception_date}</b> 建仓，等待第一次月度对账。下方是当前持仓——
            欢迎你截图存证、对着真实行情自己核对。
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={data.curve} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="rgba(255,255,255,.06)" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fill: '#8b96a8', fontSize: 11 }} minTickGap={50}
                axisLine={{ stroke: 'rgba(255,255,255,.1)' }} tickLine={false} />
              <YAxis tick={{ fill: '#8b96a8', fontSize: 11 }} width={44}
                domain={['auto', 'auto']} tickFormatter={(v) => `${v}x`}
                axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{
                background: 'rgba(13,17,28,.92)', border: '1px solid rgba(255,255,255,.12)', borderRadius: 12,
              }} labelStyle={{ color: '#8b96a8' }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="strategy" name="策略净值" stroke="#00d68f" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="bench" name="沪深300" stroke="#5ea0ff" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="panel">
        <h3>当前持仓（{data.current_as_of} · 等权 {pct(1 / data.current_holdings.length, 1)}/只）</h3>
        <div className="table-wrap" style={{ maxHeight: 420, overflow: 'auto' }}>
          <table className="data-table" style={{ width: '100%', fontSize: 13 }}>
            <thead><tr>
              <th style={{ textAlign: 'left' }}>#</th>
              <th style={{ textAlign: 'left' }}>名称</th>
              <th style={{ textAlign: 'left' }}>代码</th>
              <th style={{ textAlign: 'right' }}>建仓价</th>
              <th style={{ textAlign: 'right' }}>综合分</th>
            </tr></thead>
            <tbody>
              {data.current_holdings.map((h, i) => (
                <tr key={h.code}>
                  <td style={{ opacity: .5 }}>{i + 1}</td>
                  <td>{h.name}</td>
                  <td style={{ opacity: .7, fontFamily: 'monospace' }}>{h.code}</td>
                  <td style={{ textAlign: 'right' }}>{h.close}</td>
                  <td style={{ textAlign: 'right', color: '#00d68f' }}>{h.score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h3>别信我们，查我们</h3>
        <p className="judge-notes" style={{ margin: '2px 0 8px' }}>{data.promise}</p>
        <a className="link-btn" href={data.repo_url} target="_blank" rel="noreferrer">查看 git 公证记录 ↗</a>
        <div className="disclaimer" style={{ marginTop: 10 }}>⚠{data.disclaimer}</div>
      </div>
    </div>
  )
}
