import { useState } from 'react'
import { track } from '../apiBase.js'
import { shareCard } from '../shareCard.js'

const EXAMPLES = [
  '锂价见底了，我看好锂电产业链反弹',
  'AI 数据中心要缺电，电力是瓶颈',
  '铜会长期短缺，看好铜',
  '金价还会创新高',
]
const REL = {
  '同向': { cls: 'up', v: 85, tone: 'ok' },
  '反向': { cls: 'down', v: 70, tone: 'hot' },
  '≈无关': { cls: 'dim', v: 16, tone: 'dim' },
  '对照': { cls: 'dim', v: 20, tone: 'dim' },
}

export default function ThesisView({ onOpenStock }) {
  const [q, setQ] = useState('')
  const [d, setD] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)

  const run = (text) => {
    const j = (text ?? q).trim()
    if (!j) return
    setQ(j); setLoading(true); setErr(null); setD(null)
    track('thesis', 'run')
    fetch(`/api/thesis?q=${encodeURIComponent(j)}`, { signal: AbortSignal.timeout(120000) })
      .then(async (r) => {
        if (!r.ok) { setErr(r.status === 503 ? '拆解引擎正在休息（今日 AI 预算已用尽或暂不可用），稍后再试' : '出错了，稍后再试'); return }
        setD(await r.json())
      })
      .catch(() => setErr('请求超时，稍后再试'))
      .finally(() => setLoading(false))
  }

  const share = () => shareCard({
    column: '论点拆解',
    headline: `"${d.judgment}"`,
    subhead: `拆解：${d.chain || ''} · ${d.direction || ''}`,
    viz: {
      type: 'bars', note: '标的与该判断的历史关系',
      items: (d.targets || []).slice(0, 4).map((t) => ({
        label: (t.name || '').slice(0, 6),
        value: (REL[t.relation] || REL['对照']).v,
        tone: (REL[t.relation] || REL['对照']).tone,
      })),
    },
    takeaway: d.assumption || d.falsification || '',
    chips: ['数据为地基', '含证伪条件', '不构成投资建议'],
    cta: '说一句你的判断，AI 帮你拆 →', tags: [d.chain || '产业链', '多空', '投资'],
  })

  return (
    <div className="detail">
      <div className="detail-header">
        <h2>论点拆解</h2>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>一句判断 → 多空证据 + 标的 + 怎么验证</span>
      </div>

      <div className="tx-form" style={{ display: 'flex', gap: 8, margin: '12px 0 6px' }}>
        <input placeholder="说一句你对当下的判断，比如：锂价见底了，看好锂电链…"
          value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && run()} style={{ flex: 1 }} />
        <button className="grad-btn" onClick={() => run()} disabled={loading}>拆解</button>
      </div>
      {!d && !loading && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
          {EXAMPLES.map((e) => (
            <span key={e} className="company-chip" style={{ cursor: 'pointer' }} onClick={() => run(e)}>{e}</span>
          ))}
        </div>
      )}
      <div className="judge-notes" style={{ fontSize: 11 }}>用真实产业链与实证传导数据做地基、逼你看反面，不替你做决定，不构成投资建议。</div>

      {loading && <div className="loading" style={{ marginTop: 16 }}><span className="spin" /> 正在拆你的论点：找产业链、翻多空、挂数据、列验证…（约 20–60 秒，网络慢会更久，请勿离开本页）</div>}
      {err && <div className="judge-notes" style={{ color: 'var(--down)', marginTop: 14 }}>⚠{err}</div>}

      {d && (
        <div style={{ marginTop: 16 }}>
          <div className="judge-box" style={{ display: 'block' }}>
            <div style={{ fontFamily: 'serif', fontSize: 20, lineHeight: 1.4 }}>"{d.judgment}"</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
              {[d.chain, d.direction, d.horizon].filter(Boolean).map((t) => (
                <span key={t} className="company-chip">{t}</span>
              ))}
            </div>
          </div>

          {d.assumption && (
            <div className="panel" style={{ marginTop: 12 }}>
              <h3>你真正押的假设</h3>
              <div className="judge-notes">{d.assumption}</div>
            </div>
          )}

          <div className="detail-grid" style={{ marginTop: 12, gap: 10 }}>
            <div className="panel"><h3 style={{ color: 'var(--up)' }}>看多证据</h3>
              {(d.bull || []).map((x, i) => <div className="judge-notes" key={i} style={{ marginTop: 4 }}>· {x}</div>)}</div>
            <div className="panel"><h3 style={{ color: 'var(--down)' }}>看空证据</h3>
              {(d.bear || []).map((x, i) => <div className="judge-notes" key={i} style={{ marginTop: 4 }}>· {x}</div>)}</div>
          </div>

          {d.targets?.length > 0 && (
            <div className="panel" style={{ marginTop: 12 }}>
              <h3>标的 × 与你判断的关系 <span style={{ fontSize: 11, color: 'var(--text-dim)', fontWeight: 400 }}>（举例，非推荐）</span></h3>
              {d.targets.map((t, i) => {
                const r = REL[t.relation] || REL['对照']
                return (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, margin: '7px 0' }}>
                    <span style={{ width: 96, fontSize: 12, color: 'var(--text-dim)', flexShrink: 0 }}>{t.layer}</span>
                    {t.ticker
                      ? <span className="company-chip" onClick={() => onOpenStock && onOpenStock(t.ticker)} style={{ cursor: 'pointer' }}>{t.name} <b>{t.ticker}</b></span>
                      : <span className="company-chip muted">{t.name}</span>}
                    <span className={`badge ${r.cls === 'up' ? 'bullish' : r.cls === 'down' ? 'bearish' : 'neutral'}`} style={{ flexShrink: 0 }}>{t.relation}</span>
                    {t.note && <span className="judge-notes" style={{ fontSize: 12 }}>{t.note}</span>}
                  </div>
                )
              })}
            </div>
          )}

          {d.scenario && (
            <div className="panel" style={{ marginTop: 12 }}>
              <h3>情景敏感度 <span style={{ fontSize: 11, color: 'var(--text-dim)', fontWeight: 400 }}>（基于历史，非收益预测）</span></h3>
              {d.scenario.if_holds && <div className="judge-notes" style={{ marginTop: 4 }}><b style={{ color: 'var(--up)' }}>若假设成立：</b>{d.scenario.if_holds}</div>}
              {d.scenario.if_wrong && <div className="judge-notes" style={{ marginTop: 4 }}><b style={{ color: 'var(--down)' }}>若证伪：</b>{d.scenario.if_wrong}</div>}
            </div>
          )}

          <div className="panel" style={{ marginTop: 12 }}>
            <h3>怎么验证你对没对</h3>
            {(d.validation || []).map((x, i) => <div className="judge-notes" key={i} style={{ marginTop: 3 }}>☐ {x}</div>)}
            {d.falsification && (
              <div className="judge-notes" style={{ marginTop: 8, padding: '8px 10px', borderRadius: 8, background: 'rgba(255,176,46,.1)', color: 'var(--neutral)' }}>
                证伪触发：{d.falsification}
              </div>
            )}
          </div>

          <div className="judge-notes" style={{ marginTop: 10, fontSize: 11 }}>{d.caveat || '多空与历史敏感度，非涨跌预测，不构成投资建议。'}</div>
          <div className="tx-form" style={{ marginTop: 12 }}>
            <button className="grad-btn" onClick={share}>生成分享卡（小红书 / 微信）</button>
            <button className="link-btn" style={{ verticalAlign: 0 }} onClick={() => { setD(null); setQ('') }}>再拆一个</button>
          </div>
        </div>
      )}
    </div>
  )
}
