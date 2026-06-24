import { useState } from 'react'
import { track } from '../apiBase.js'
import { shareCard } from '../shareCard.js'
import { narrativeShareSpec } from '../narrativeShareSpec.js'

// 真伪状态 → 配色（证实绿 / 证伪红 / 部分证实暖 / 其余中性灰）
const STATUS = {
  '证实': { cls: 'bullish', c: 'var(--up)' },
  '部分证实': { cls: 'neutral', c: 'var(--neutral)' },
  '证伪': { cls: 'bearish', c: 'var(--down)' },
  '无法验证': { cls: 'neutral', c: 'var(--text-dim)' },
  '预测(不可证伪)': { cls: 'neutral', c: 'var(--cyan)' },
  '观点': { cls: 'neutral', c: 'var(--cyan)' },
}

const EXAMPLES = [
  { t: '600519', x: '茅台需求见底、估值历史低位，机构都在跑，现在是黄金坑该抄底' },
  { t: '300750', x: '宁德时代海外订单爆发、毛利率拐点向上，还能再翻一倍' },
  { t: '002594', x: '比亚迪价格战打完就是剩者为王，利润马上修复' },
]

export default function NarrativeCheckView({ onOpenStock }) {
  const [ticker, setTicker] = useState('')
  const [text, setText] = useState('')
  const [d, setD] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)

  const run = (tk, tx) => {
    const t = (tk ?? ticker).trim()
    const x = (tx ?? text).trim()
    if (!t || !x) { setErr('填一个 A股代码 + 一段荐股叙事原文'); return }
    setTicker(t); setText(x); setLoading(true); setErr(null); setD(null)
    track('narrative', 'run')
    fetch('/api/narrative', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker: t, text: x }), signal: AbortSignal.timeout(150000),
    })
      .then(async (r) => {
        if (!r.ok) {
          const msg = r.status === 503 ? '核验引擎在休息（今日 AI 预算已用尽或暂不可用），稍后再试'
            : r.status === 422 ? '请填 A股代码 + 一段完整叙事' : '核验出错了，稍后再试'
          setErr(msg); return
        }
        setD(await r.json())
      })
      .catch(() => setErr('请求超时，稍后再试（深度核验较慢）'))
      .finally(() => setLoading(false))
  }

  const share = () => shareCard(narrativeShareSpec(d))

  return (
    <div className="detail">
      <div className="detail-header">
        <h2>叙事验证器</h2>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>一条荐股叙事 → 过一遍公开数据 → 真伪核验卡</span>
      </div>

      <div className="tx-form" style={{ display: 'flex', gap: 8, margin: '12px 0 6px', flexWrap: 'wrap' }}>
        <input placeholder="A股代码 / 名称，如 600519" value={ticker}
          onChange={(e) => setTicker(e.target.value)} style={{ width: 180 }} />
        <button className="grad-btn" onClick={() => run()} disabled={loading}>核验</button>
      </div>
      <textarea placeholder="把一条 KOL/博主的荐股叙事原文粘进来，比如：“XX 要涨，因为 YY……”"
        value={text} onChange={(e) => setText(e.target.value)} rows={4}
        style={{ width: '100%', resize: 'vertical', boxSizing: 'border-box', marginBottom: 6 }} />

      {!d && !loading && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
          {EXAMPLES.map((e) => (
            <span key={e.t} className="company-chip" style={{ cursor: 'pointer' }}
              onClick={() => run(e.t, e.x)}>{e.t}｜{e.x.slice(0, 14)}…</span>
          ))}
        </div>
      )}
      <div className="judge-notes" style={{ fontSize: 11 }}>
        只核「叙事 vs 公开财报/估值是否一致」，不判「你该不该买」。拿不到公开数据的主张诚实标『无法验证』，不喊单。仅 A股。
      </div>

      {loading && <div className="loading" style={{ marginTop: 16 }}><span className="spin" /> 深度核验中：拆主张 → 拉真实财报/估值 → 逐条裁决 → 多视角对抗质检…（约 1–2 分钟，请勿离开本页）</div>}
      {err && <div className="judge-notes" style={{ color: 'var(--down)', marginTop: 14 }}>⚠{err}</div>}

      {d && d.ok && (
        <div style={{ marginTop: 16 }}>
          <div className="judge-box" style={{ display: 'block' }}>
            <div style={{ fontFamily: 'serif', fontSize: 20, lineHeight: 1.4 }}>{d.headline}</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
              {[d.name || d.ticker, d.direction, d.horizon].filter(Boolean).map((t) => (
                <span key={t} className="company-chip">{t}</span>
              ))}
              {d.as_of && <span className="company-chip muted">数据截止 {d.as_of}</span>}
            </div>
            {d.summary && <div className="judge-notes" style={{ marginTop: 8 }}>原叙事：{d.summary}</div>}
          </div>

          <div className="panel" style={{ marginTop: 12 }}>
            <h3>逐条真伪裁决 <span style={{ fontSize: 11, color: 'var(--text-dim)', fontWeight: 400 }}>
              （事实才判真伪，预测/观点不判）{d.self_check?.ran ? ` · 已过 ${d.self_check.votes} 视角对抗质检` : ''}</span></h3>
            {(d.verdicts || []).map((v, i) => {
              const s = STATUS[v.status] || STATUS['无法验证']
              return (
                <div key={v.id || i} style={{ margin: '9px 0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span className={`badge ${s.cls}`} style={{ flexShrink: 0 }}>{v.status}</span>
                    <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>{v.type}</span>
                    {v.votes && <span className="badge bearish" style={{ fontSize: 10 }}>{v.votes}↓</span>}
                  </div>
                  {v.basis && <div className="judge-notes" style={{ marginTop: 3 }}>{v.basis}</div>}
                  {v.evidence && <div className="judge-notes" style={{ marginTop: 2, color: s.c, fontSize: 12 }}>证据：{v.evidence}</div>}
                  {v.challenge && <div className="judge-notes" style={{ marginTop: 2, fontSize: 11, color: 'var(--neutral)' }}>质疑：{v.challenge}</div>}
                </div>
              )
            })}
          </div>

          {d.financial_check?.verdict && (
            <div className="panel" style={{ marginTop: 12 }}>
              <h3>财报验证</h3>
              <div className="judge-notes">{d.financial_check.verdict}</div>
              {(d.financial_check.points || []).map((p, i) => (
                <div className="judge-notes" key={i} style={{ marginTop: 3 }}>· {p}</div>
              ))}
            </div>
          )}

          {d.valuation_priced_in?.read && (
            <div className="panel" style={{ marginTop: 12 }}>
              <h3>估值 price in 了什么</h3>
              <div className="judge-notes">{d.valuation_priced_in.read}</div>
              {d.valuation_priced_in.needed && <div className="judge-notes" style={{ marginTop: 4 }}><b>要让叙事成立：</b>{d.valuation_priced_in.needed}</div>}
            </div>
          )}

          {(d.supply_chain?.links?.length > 0 || d.supply_chain?.note) && (
            <div className="panel" style={{ marginTop: 12 }}>
              <h3>产业链位置 {d.supply_chain_grounded && <span className="badge bullish" style={{ fontSize: 10 }}>图谱接地</span>}</h3>
              {d.supply_chain.note && <div className="judge-notes">{d.supply_chain.note}</div>}
              {(d.supply_chain.links || []).map((l, i) => (
                <div className="judge-notes" key={i} style={{ marginTop: 3 }}>· {l}</div>
              ))}
            </div>
          )}

          <div className="detail-grid" style={{ marginTop: 12, gap: 10 }}>
            <div className="panel"><h3 style={{ color: 'var(--up)' }}>多头视角</h3>
              {(d.bull || []).map((x, i) => <div className="judge-notes" key={i} style={{ marginTop: 4 }}>· {x}</div>)}</div>
            <div className="panel"><h3 style={{ color: 'var(--down)' }}>空头/反方</h3>
              {(d.bear || []).map((x, i) => <div className="judge-notes" key={i} style={{ marginTop: 4 }}>· {x}</div>)}</div>
          </div>

          {(d.disconfirmers?.length > 0 || d.falsification) && (
            <div className="panel" style={{ marginTop: 12 }}>
              <h3>怎么验证它对没对</h3>
              {(d.disconfirmers || []).map((x, i) => <div className="judge-notes" key={i} style={{ marginTop: 3 }}>· {x}</div>)}
              {d.falsification && (
                <div className="judge-notes" style={{ marginTop: 8, padding: '8px 10px', borderRadius: 8, background: 'rgba(255,176,46,.1)', color: 'var(--neutral)' }}>
                  证伪触发：{d.falsification}
                </div>
              )}
            </div>
          )}

          {d.sources?.length > 0 && (
            <div className="judge-notes" style={{ marginTop: 10, fontSize: 11 }}>数据来源：{d.sources.join(' · ')}</div>
          )}
          <div className="judge-notes" style={{ marginTop: 6, fontSize: 11 }}>{d.caveat || '基于公开数据的叙事核验，非涨跌预测，不构成投资建议。'}</div>

          <div className="tx-form" style={{ marginTop: 12 }}>
            <button className="grad-btn" onClick={share}>生成分享卡（小红书 / 微信）</button>
            {d.ticker && onOpenStock && (
              <button className="link-btn" style={{ verticalAlign: 0 }} onClick={() => onOpenStock(d.ticker)}>看这只股的完整分析</button>
            )}
            <button className="link-btn" style={{ verticalAlign: 0 }} onClick={() => { setD(null) }}>再核一条</button>
          </div>
        </div>
      )}
    </div>
  )
}
