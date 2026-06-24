import { useEffect, useState } from 'react'
import { track } from '../apiBase.js'
import BrokerPanel from './BrokerPanel.jsx'

const ACTION_CLS = {
  reduce: 'bearish', trim: 'neutral', add_watch: 'bullish', hold: '',
}

function fmtMoney(v, sym = '$') {
  if (v == null) return '-'
  return `${v < 0 ? '-' : ''}${sym}${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

function TxForm({ onSubmit }) {
  const [form, setForm] = useState({ ticker: '', side: 'buy', shares: '', price: '', date: new Date().toISOString().slice(0, 10) })
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const submit = () => {
    if (!form.ticker || !form.shares || !form.price) return
    onSubmit({ ...form, ticker: form.ticker.toUpperCase(), shares: +form.shares, price: +form.price })
    setForm({ ...form, ticker: '', shares: '', price: '' })
  }
  return (
    <div className="tx-form">
      <input placeholder="代码 NVDA / 600519.SS" value={form.ticker} onChange={set('ticker')} style={{ width: 150 }} />
      <select value={form.side} onChange={set('side')}>
        <option value="buy">买入</option>
        <option value="sell">卖出</option>
      </select>
      <input placeholder="股数" type="number" value={form.shares} onChange={set('shares')} style={{ width: 80 }} />
      <input placeholder="成交价" type="number" value={form.price} onChange={set('price')} style={{ width: 90 }} />
      <input type="date" value={form.date} onChange={set('date')} />
      <button className="grad-btn" onClick={submit}>记一笔</button>
    </div>
  )
}

function AlertsPanel() {
  const [data, setData] = useState({ rules: [], triggered: [] })
  const [form, setForm] = useState({ ticker: '', kind: 'price_below', value: '' })

  const refresh = () => fetch('/api/alerts').then((r) => r.json()).then(setData).catch(() => {})
  useEffect(() => { refresh() }, [])

  const add = () => {
    if (!form.ticker || !form.value) return
    fetch('/api/alerts', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker: form.ticker.toUpperCase(), kind: form.kind, value: +form.value }),
    }).then(() => { setForm({ ...form, ticker: '', value: '' }); refresh() })
  }
  const del = (id) => fetch(`/api/alerts/${id}`, { method: 'DELETE' }).then(refresh)

  return (
    <div className="panel">
      <h3>价格提醒（后台每 5 分钟检查，命中即触发并失效）</h3>
      <div className="tx-form">
        <input placeholder="代码" value={form.ticker} style={{ width: 120 }}
          onChange={(e) => setForm({ ...form, ticker: e.target.value })} />
        <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
          <option value="price_below">价格低于</option>
          <option value="price_above">价格高于</option>
          <option value="change_below">单日跌幅超过%</option>
        </select>
        <input placeholder="阈值" type="number" value={form.value} style={{ width: 90 }}
          onChange={(e) => setForm({ ...form, value: e.target.value })} />
        <button className="grad-btn" onClick={add}>添加</button>
      </div>
      {data.rules.map((r) => (
        <div className="news-item" key={r.id}>
          <span style={{ flex: 1 }}>
            <b>{r.ticker}</b> {r.kind === 'price_below' ? '价格低于' : r.kind === 'price_above' ? '价格高于' : '单日跌幅超过'} {r.value}
          </span>
          <button className="link-btn" onClick={() => del(r.id)}>删除</button>
        </div>
      ))}
      {data.triggered.slice(-5).reverse().map((t) => (
        <div className="news-item" key={t.id} style={{ color: 'var(--neutral)' }}>
          {t.message} <span style={{ color: 'var(--text-dim)', fontSize: 11, marginLeft: 8 }}>{t.time}</span>
        </div>
      ))}
      {!data.rules.length && !data.triggered.length && (
        <div className="judge-notes">还没有提醒规则——添加一条，比如 NVDA 价格低于 180。</div>
      )}
    </div>
  )
}

function AuthGate({ onAuthed }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [pw, setPw] = useState('')
  const [err, setErr] = useState(null)

  const submit = async () => {
    setErr(null)
    const r = await fetch(`/api/auth/${mode}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password: pw }),
    })
    const d = await r.json()
    if (!r.ok) { setErr(d.detail || '失败'); return }
    if (mode === 'register') track('portfolio', 'signup') // 转化漏斗：注册
    localStorage.setItem('sp_token', d.token)
    localStorage.setItem('sp_email', d.email)
    onAuthed()
  }

  return (
    <div className="detail" style={{ maxWidth: 460 }}>
      <h2>{mode === 'login' ? '登录' : '注册'}</h2>
      <div className="judge-notes" style={{ margin: '8px 0' }}>
        分析内容无需登录；持仓、提醒等个人功能需要账号（你的数据只属于你）。
      </div>
      <div className="tx-form" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
        <input placeholder="邮箱" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input placeholder="密码（至少 8 位）" type="password" value={pw}
          onChange={(e) => setPw(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()} />
        <button className="grad-btn" onClick={submit}>{mode === 'login' ? '登录' : '注册'}</button>
      </div>
      {err && <div className="error">{err}</div>}
      <div className="judge-notes" style={{ cursor: 'pointer' }}
        onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
        {mode === 'login' ? '没有账号？点这里注册' : '已有账号？点这里登录'}
      </div>
    </div>
  )
}

export default function PortfolioView() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [cashInput, setCashInput] = useState('')
  const [loadingAdvice, setLoadingAdvice] = useState(false)
  const [needLogin, setNeedLogin] = useState(false)

  const refresh = (withAdvice = true) => {
    setLoadingAdvice(withAdvice)
    fetch(`/api/portfolio?advice=${withAdvice}`)
      .then((r) => {
        if (r.status === 401) { setNeedLogin(true); setLoadingAdvice(false); return null }
        return r.json()
      })
      .then((d) => { if (d) { setData(d); setNeedLogin(false) } setLoadingAdvice(false) })
      .catch((e) => { setError(e.message); setLoadingAdvice(false) })
  }
  useEffect(() => { refresh(true) }, [])

  if (needLogin) return <AuthGate onAuthed={() => refresh(true)} />

  const saveCash = () => {
    fetch('/api/portfolio/settings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ initial_cash: +cashInput }),
    }).then(() => refresh(true))
  }
  const addTx = (tx) => {
    fetch('/api/portfolio/transaction', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(tx),
    }).then(() => refresh(true))
  }
  const delTx = (id) => fetch(`/api/portfolio/transaction/${id}`, { method: 'DELETE' }).then(() => refresh(true))

  if (error) return <div className="detail error">加载失败：{error}</div>
  if (!data) return <div className="detail loading"><span className="spin" /> 加载持仓…</div>

  const stats = [
    ['总资产', fmtMoney(data.total_assets)],
    ['现金', `${fmtMoney(data.cash)} (${(data.cash_ratio * 100).toFixed(0)}%)`],
    ['持仓市值', fmtMoney(data.market_value)],
    ['总盈亏', fmtMoney(data.total_pnl)],
  ]

  const email = localStorage.getItem('sp_email')
  const logout = () => {
    localStorage.removeItem('sp_token'); localStorage.removeItem('sp_email')
    setData(null); setNeedLogin(true)
  }
  const deleteAccount = async () => {
    if (!confirm('注销将删除你的账号和全部个人数据（持仓、提醒），不可恢复。确定吗？')) return
    const pw = prompt('请输入密码确认注销：')
    if (!pw) return
    const r = await fetch('/api/auth/delete', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password: pw }),
    })
    if (!r.ok) { alert((await r.json()).detail || '注销失败'); return }
    alert('账号已注销，数据已删除。')
    logout()
  }

  return (
    <div className="detail">
      <div className="detail-header">
        <h2>我的持仓</h2>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>{data.currency_note}</span>
        {email && (
          <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'var(--text-dim)' }}>
            {email}
            <button className="link-btn" onClick={logout}>退出登录</button>
            <button className="link-btn" style={{ color: 'var(--down)' }} onClick={deleteAccount}>注销账号</button>
          </span>
        )}
      </div>

      <div className="stats" style={{ margin: '14px 0' }}>
        {stats.map(([k, v]) => (
          <div className="stat" key={k}>
            <div className="k">{k}</div>
            <div className="v" style={k === '总盈亏' ? { color: data.total_pnl >= 0 ? 'var(--up)' : 'var(--down)' } : {}}>{v}</div>
          </div>
        ))}
      </div>

      <div className="tx-form" style={{ marginBottom: 6 }}>
        <input placeholder={`总投入资金（当前 $${data.initial_cash.toLocaleString()}）`} type="number"
          value={cashInput} onChange={(e) => setCashInput(e.target.value)} style={{ width: 240 }} />
        <button className="grad-btn" onClick={saveCash}>设置总资金</button>
        <button className="link-btn" style={{ verticalAlign: 0 }} onClick={() => refresh(true)}>
          {loadingAdvice ? '分析中…' : '重新分析'}
        </button>
      </div>
      <TxForm onSubmit={addTx} />

      {data.notes.length > 0 && (
        <div className="judge-box" style={{ margin: '12px 0' }}>
          <div className="judge-main">
            {data.notes.map((n, i) => <div className="judge-notes" key={i}>· {n}</div>)}
          </div>
        </div>
      )}

      {data.pitfalls?.length > 0 && data.pitfalls.map((p) => (
        <div className="pitfall-signpost" key={p.id}>
          <div className="pitfall-head">{p.emoji} 跌倒路标 · {p.title}</div>
          <div className="judge-notes" style={{ marginTop: 3 }}>{p.context}</div>
          <div className="judge-notes" style={{ marginTop: 3, color: 'var(--up)' }}>{p.inversion}</div>
        </div>
      ))}

      {data.positions.length > 0 ? (
        <div className="panel" style={{ marginTop: 14 }}>
          <h3>持仓与每日建议</h3>
          {data.positions.map((p) => (
            <div className="position-row" key={p.ticker}>
              <div className="position-head">
                <span><b>{p.ticker}</b> <span className="name-cn">{p.name_cn}</span>
                  <span className="badge" style={{ marginLeft: 8 }}>{p.market === 'CN' ? 'A股' : '美股'}</span>
                </span>
                <span className={`badge ${ACTION_CLS[p.advice?.action] || ''}`}>
                  {p.advice?.action_cn || (loadingAdvice ? '分析中…' : '—')}
                </span>
              </div>
              <div className="position-nums">
                <span>{p.shares} 股 @ {p.currency}{p.avg_cost.toFixed(2)}</span>
                <span>现价 {p.currency}{p.price}</span>
                <span>市值 {p.currency}{p.market_value.toLocaleString()}</span>
                <span style={{ color: (p.pnl_pct ?? 0) >= 0 ? 'var(--up)' : 'var(--down)', fontWeight: 700 }}>
                  {p.pnl_pct != null ? `${(p.pnl_pct * 100).toFixed(1)}%` : '-'}（{p.currency}{p.pnl.toLocaleString()}）
                </span>
                <span style={{ color: 'var(--text-dim)' }}>占比 {(p.weight * 100).toFixed(0)}%</span>
              </div>
              {p.advice?.reasons?.map((r, i) => (
                <div className="judge-notes" key={i}>· {r}</div>
              ))}
            </div>
          ))}
        </div>
      ) : (
        <div className="loading" style={{ padding: 24 }}>
          还没有持仓——先设置总资金，然后在上面"记一笔"你的买入。
        </div>
      )}

      <BrokerPanel />

      <AlertsPanel />

      {data.transactions.length > 0 && (
        <div className="panel">
          <h3>交易记录</h3>
          <table className="bank-table">
            <thead><tr><th>日期</th><th>代码</th><th>方向</th><th>股数</th><th>价格</th><th></th></tr></thead>
            <tbody>
              {data.transactions.map((t) => (
                <tr key={t.id}>
                  <td>{t.date}</td><td>{t.ticker}</td>
                  <td style={{ color: t.side === 'buy' ? 'var(--up)' : 'var(--down)' }}>{t.side === 'buy' ? '买入' : '卖出'}</td>
                  <td>{t.shares}</td><td>{t.price}</td>
                  <td><button className="link-btn" style={{ verticalAlign: 0 }} onClick={() => delTx(t.id)}>删</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="disclaimer">⚠{data.disclaimer}</div>
    </div>
  )
}
