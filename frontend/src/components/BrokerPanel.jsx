import { useEffect, useState } from 'react'

const post = (url, body) => fetch(url, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body || {}),
}).then((r) => r.json())

export default function BrokerPanel() {
  const [st, setSt] = useState(null)
  const [busy, setBusy] = useState('')
  const [props, setProps] = useState(null)
  const [checked, setChecked] = useState({})
  const [ackLive, setAckLive] = useState(false)
  const [execResult, setExecResult] = useState(null)
  const [form, setForm] = useState(null)

  const refresh = () => fetch('/api/broker/status').then((r) => r.json()).then((d) => {
    setSt(d)
    if (!form && d.settings) {
      setForm({ ...d.settings, universe_text: d.settings.universe.join(', ') })
    }
  }).catch(() => {})
  useEffect(() => { refresh() }, [])

  const connect = async () => {
    setBusy('连接中…')
    const d = await post('/api/broker/connect')
    setSt(d)
    setBusy('')
  }

  const saveSettings = async () => {
    const universe = form.universe_text.split(/[,，\s]+/).filter(Boolean)
    await post('/api/broker/settings', { ...form, universe, port: +form.port })
    refresh()
  }

  const generate = async () => {
    setBusy('正在分析标的并生成提案（每只股票要跑全套信号，约 1-2 分钟）…')
    setExecResult(null)
    const d = await post('/api/broker/proposals')
    setProps(d)
    setChecked({})
    setBusy('')
  }

  const execute = async () => {
    const ids = Object.keys(checked).filter((k) => checked[k])
    if (!ids.length) return
    if (!window.confirm(`确认提交 ${ids.length} 笔订单到 ${st?.mode}？`)) return
    setBusy('提交订单中…')
    const d = await post('/api/broker/execute', { ids, acknowledge_live: ackLive })
    setExecResult(d)
    setProps(null)
    setBusy('')
    refresh()
  }

  if (!st || !form) return null
  const isLive = +form.port !== 7497

  return (
    <div className="panel" style={{ marginTop: 18 }}>
      <h3>IBKR 策略交易（提案-审批模式）</h3>
      <div className="disclaimer" style={{ marginTop: 8 }}>
        ⚠软件只生成提案，每一笔都需要你勾选确认后才下单。我们的回测显示策略没有稳定优势——
        这是辅助工具不是印钞机。<b>强烈建议先用模拟账户（端口 7497）跑几周。</b>
      </div>

      <div className="judge-line" style={{ margin: '10px 0' }}>
        <span className={`badge ${st.connected ? 'bullish' : 'bearish'}`}>
          {st.connected ? `已连接 · ${st.mode}` : '未连接'}
        </span>
        {st.connected && st.account && (
          <span style={{ fontSize: 12.5, color: 'var(--text-dim)' }}>
            净值 ${(+st.account.NetLiquidation || 0).toLocaleString()} ·
            可用资金 ${(+st.account.AvailableFunds || 0).toLocaleString()} ·
            持仓 {st.positions?.length ?? 0} 只
          </span>
        )}
        {!st.connected && <button className="grad-btn" onClick={connect}>连接</button>}
      </div>

      {!st.connected && st.setup_guide && (
        <div className="judge-notes">
          {st.error && <div style={{ color: 'var(--down)' }}>· {st.error}</div>}
          {st.setup_guide.map((g, i) => <div key={i}>· {g}</div>)}
        </div>
      )}

      <div className="tx-form" style={{ marginTop: 10 }}>
        <select value={form.risk_level} onChange={(e) => setForm({ ...form, risk_level: e.target.value })}>
          <option value="conservative">保守（单票5%·高门槛）</option>
          <option value="balanced">平衡（单票10%）</option>
          <option value="aggressive">进取（单票15%·低门槛）</option>
        </select>
        <select value={form.horizon} onChange={(e) => setForm({ ...form, horizon: e.target.value })}>
          <option value="short">短线信号（约5个交易日）</option>
          <option value="long">一年期（动量优先）</option>
        </select>
        <input style={{ width: 90 }} type="number" value={form.port} title="7497=模拟 7496=实盘"
          onChange={(e) => setForm({ ...form, port: e.target.value })} />
        <button className="grad-btn" onClick={saveSettings}>保存设置</button>
      </div>
      <div className="tx-form">
        <input style={{ flex: 1, minWidth: 260 }} value={form.universe_text}
          placeholder="感兴趣的标的（逗号分隔）：NVDA, MSFT, …"
          onChange={(e) => setForm({ ...form, universe_text: e.target.value })} />
        <button className="grad-btn" onClick={generate} disabled={!st.connected || !!busy}>
          生成交易提案
        </button>
      </div>

      {isLive && (
        <label className="judge-notes" style={{ display: 'block', color: 'var(--down)' }}>
          <input type="checkbox" checked={ackLive} onChange={(e) => setAckLive(e.target.checked)} />
          {' '}当前是实盘端口：我已知晓风险，确认要用真金白银执行
        </label>
      )}

      {busy && <div className="loading" style={{ padding: 14 }}><span className="spin" /> {busy}</div>}

      {props && (
        props.error ? <div className="error">{props.error}</div> : (
          <>
            <div className="judge-notes" style={{ margin: '8px 0' }}>
              可用资金 ${(props.funds || 0).toLocaleString()} · 风险档位：{props.profile} · {props.note}
            </div>
            {props.proposals.length ? (
              <>
                <table className="bank-table">
                  <thead>
                    <tr><th></th><th>方向</th><th>代码</th><th>数量</th><th>参考价</th><th>金额</th><th style={{ textAlign: 'left' }}>理由</th></tr>
                  </thead>
                  <tbody>
                    {props.proposals.map((p) => (
                      <tr key={p.id}>
                        <td><input type="checkbox" checked={!!checked[p.id]}
                          onChange={(e) => setChecked({ ...checked, [p.id]: e.target.checked })} /></td>
                        <td style={{ color: p.action === 'BUY' ? 'var(--up)' : 'var(--down)', fontWeight: 700 }}>
                          {p.action === 'BUY' ? '买入' : '卖出'}
                        </td>
                        <td><b>{p.ticker}</b></td>
                        <td>{p.qty}</td>
                        <td>${p.est_price}</td>
                        <td>${p.notional.toLocaleString()}</td>
                        <td style={{ textAlign: 'left', fontSize: 11.5, color: 'var(--text-dim)' }}>{p.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="tx-form">
                  <button className="grad-btn" onClick={execute}>执行勾选的提案</button>
                </div>
              </>
            ) : <div className="judge-notes">当前信号下没有可提案的交易——没有信号时不动手也是一种纪律。</div>}
          </>
        )
      )}

      {execResult?.results && (
        <div className="judge-notes" style={{ marginTop: 8 }}>
          {execResult.results.map((r, i) => (
            <div key={i}>
              · {r.ticker || r.id}: {r.status}{r.limit ? `（限价 $${r.limit}）` : ''}{r.msg ? ` — ${r.msg}` : ''}
            </div>
          ))}
        </div>
      )}
      {execResult?.error && <div className="error">{execResult.error}</div>}
    </div>
  )
}
