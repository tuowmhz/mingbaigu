import { useEffect, useState } from 'react'

// owner 专用流量看板。令牌存浏览器 localStorage（不进 URL、不进我们的库），
// 用 X-Admin-Token 头调 /api/traffic。访问：mingbaigu.com/?view=traffic
export default function TrafficDashboard() {
  const [token, setToken] = useState(() => localStorage.getItem('sp_admin_token') || '')
  const [input, setInput] = useState('')
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = (tk) => {
    if (!tk) return
    setLoading(true); setErr(null)
    fetch('/api/traffic?days=30', { headers: { 'X-Admin-Token': tk } })
      .then(async (r) => {
        if (r.status === 403) { setErr('服务端还没设置 ADMIN_TOKEN（fly secrets set ADMIN_TOKEN=…）'); setData(null); return }
        if (r.status === 401) { setErr('令牌无效，请重新输入'); setData(null); return }
        setData(await r.json())
      })
      .catch(() => setErr('网络错误，稍后重试'))
      .finally(() => setLoading(false))
  }
  useEffect(() => { if (token) load(token) }, [token])

  const saveToken = () => {
    const t = input.trim()
    if (!t) return
    localStorage.setItem('sp_admin_token', t); setToken(t); setInput('')
  }
  const clearToken = () => {
    localStorage.removeItem('sp_admin_token'); setToken(''); setData(null); setErr(null)
  }

  if (!token || (err && !data)) {
    return (
      <div className="detail">
        <div className="detail-header"><h2>流量看板（owner）</h2></div>
        {err && <div className="judge-notes" style={{ color: 'var(--down)', margin: '8px 0' }}>⚠{err}</div>}
        <div className="judge-notes" style={{ margin: '8px 0' }}>输入管理令牌（ADMIN_TOKEN）。只存在你这台设备的浏览器里，不会上传。</div>
        <div className="tx-form" style={{ display: 'flex', gap: 8 }}>
          <input type="password" placeholder="ADMIN_TOKEN" value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && saveToken()}
            style={{ flex: 1 }} />
          <button className="grad-btn" onClick={saveToken}>进入</button>
        </div>
      </div>
    )
  }
  if (loading && !data) return <div className="detail loading"><span className="spin" /> 加载流量…</div>
  if (!data) return <div className="detail loading"><span className="spin" /> …</div>

  const s = data.summary || {}
  const days = data.days || []
  const maxUV = Math.max(1, ...days.map((d) => d.unique_visitors || 0))
  const hot = s.hottest_views || []
  const maxHot = Math.max(1, ...hot.map((h) => h[1] || 0))
  const VIEW_CN = { stocks: '个股', sectors: '产业链', chain: 'AI链', earnings: '财报', academy: '学堂',
    daily: '日报', record: '成绩单', quant: '量化', portfolio: '持仓', landing: '落地页', other: '其它', quiz: '体质测试' }

  return (
    <div className="detail">
      <div className="detail-header">
        <h2>流量看板（owner）</h2>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>近 {s.period_days} 天</span>
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', margin: '10px 0 4px' }}>
        {[['访客人日', s.total_unique_visitors], ['总浏览', s.total_views], ['统计天数', s.period_days]].map(([k, v]) => (
          <div key={k} className="panel" style={{ flex: 1, minWidth: 92, textAlign: 'center', padding: '12px 8px' }}>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{v ?? '—'}</div>
            <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>{k}</div>
          </div>
        ))}
      </div>
      <div className="judge-notes" style={{ fontSize: 11 }}>「访客人日」= 每日独立访客之和；标识为当日盐哈希、不能跨天去重，同一人多日来访会被多次计入，真实人数 ≤ 此值。</div>

      <div className="panel" style={{ marginTop: 12 }}>
        <h3>每日独立访客</h3>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 130, marginTop: 8 }}>
          {days.map((d) => (
            <div key={d.date} title={`${d.date}：访客 ${d.unique_visitors} · 浏览 ${d.total_views}`}
              style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: '100%' }}>
              <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>{d.unique_visitors}</span>
              <div style={{ width: '70%', height: `${(d.unique_visitors / maxUV) * 100}%`, minHeight: 2,
                background: 'linear-gradient(180deg,var(--accent),#5ea0ff)', borderRadius: '3px 3px 0 0' }} />
              <span style={{ fontSize: 9, color: 'var(--text-dim)', marginTop: 3, whiteSpace: 'nowrap' }}>{d.date.slice(5)}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="panel" style={{ marginTop: 12 }}>
        <h3>热门页面</h3>
        {hot.map(([name, cnt]) => (
          <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '5px 0' }}>
            <span style={{ width: 64, fontSize: 12 }}>{VIEW_CN[name] || name}</span>
            <div className="weight-bar-track" style={{ flex: 1 }}>
              <div className="weight-bar" style={{ width: `${(cnt / maxHot) * 100}%`, background: 'linear-gradient(90deg,#5ea0ff,var(--accent))' }} />
            </div>
            <span style={{ width: 38, textAlign: 'right', fontSize: 12 }}>{cnt}</span>
          </div>
        ))}
      </div>

      {data.by_source?.length > 0 && (
        <div className="panel" style={{ marginTop: 12 }}>
          <h3>来源 · 转化漏斗</h3>
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead><tr style={{ color: 'var(--text-dim)', textAlign: 'left' }}>
              <th style={{ padding: '4px 6px' }}>来源</th><th>人日</th><th>测试</th><th>注册</th><th>测试率</th>
            </tr></thead>
            <tbody>
              {data.by_source.map((r) => (
                <tr key={r.source} style={{ borderTop: '1px solid var(--line, rgba(255,255,255,.08))' }}>
                  <td style={{ padding: '5px 6px' }}>{r.source}</td>
                  <td>{r.visitor_days}</td><td>{r.quiz_done}</td><td>{r.signup}</td>
                  <td>{r.quiz_rate != null ? `${Math.round(r.quiz_rate * 100)}%` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="judge-notes" style={{ marginTop: 12, fontSize: 11 }}>{data.privacy_note}</div>
      <div className="tx-form" style={{ marginTop: 10 }}>
        <button className="link-btn" onClick={() => load(token)} style={{ verticalAlign: 0 }}>刷新</button>
        <button className="link-btn" onClick={clearToken} style={{ verticalAlign: 0 }}>改令牌</button>
      </div>
    </div>
  )
}
