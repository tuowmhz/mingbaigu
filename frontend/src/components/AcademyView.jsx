import { useEffect, useState } from 'react'
import PitfallQuiz from './PitfallQuiz.jsx'

// 带重试的请求：后端重启窗口的瞬时失败自动恢复
async function fetchRetry(url, tries = 3) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(20000) })
      if (r.ok) return r.json()
    } catch {}
    await new Promise((res) => setTimeout(res, 2000))
  }
  return null
}

function FailureMap() {
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(null)
  const [cat, setCat] = useState('全部')
  const [quizOpen, setQuizOpen] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    fetchRetry('/api/failures').then((d) => {
      if (cancelled) return
      if (d) setData(d)
      else setTimeout(() => !cancelled && setAttempt((a) => a + 1), 4000)
    })
    return () => { cancelled = true }
  }, [attempt])

  if (!data) return <div className="loading"><span className="spin" /> 加载跌倒地图…</div>

  if (quizOpen) return <PitfallQuiz onClose={() => setQuizOpen(false)} />

  const cats = ['全部', '消息面', '行为']
  const entries = data.entries.filter((e) => cat === '全部' || e.category === cat)

  return (
    <>
      <div className="munger-quote">
        "{data.quote.split('——')[0].trim()}"
        <span className="munger-author">—— 查理·芒格</span>
      </div>
      <div className="judge-notes" style={{ margin: '6px 0 10px' }}>{data.intro}</div>
      <div className="quiz-cta" onClick={() => setQuizOpen(true)}>
        <b>测测你的跌倒体质</b> —— 12 个真实场景，3 分钟，找出你最可能栽进去的那几个坑
        <span className="grad-btn" style={{ padding: '5px 16px', fontSize: 12.5, marginLeft: 'auto' }}>开始测试</span>
      </div>
      <div className="quick-chips" style={{ marginBottom: 14 }}>
        {cats.map((c) => (
          <span key={c} className="chip" onClick={() => setCat(c)}
            style={cat === c ? { borderColor: 'var(--down)', color: 'var(--down)' } : {}}>
            {c === '全部' ? `全部 ${data.n} 种死法` : `${c}的死法`}
          </span>
        ))}
      </div>
      <div className="academy-grid">
        {entries.map((e) => {
          const expanded = open === e.id
          return (
            <div key={e.id} className={`academy-card pitfall-card ${expanded ? 'open' : ''}`}
              onClick={() => setOpen(expanded ? null : e.id)}>
              <div className="academy-head">
                <span className="academy-emoji">{e.emoji}</span>
                <div>
                  <div className="academy-title">{e.title}</div>
                  <div className="academy-cat" style={{ color: 'var(--down)' }}>{e.category}的死法</div>
                </div>
              </div>
              <p className="academy-liner">{e.hook}</p>
              {expanded && (
                <div className="academy-body">
                  <p><b>为什么聪明人也会踩：</b>{e.mechanism}</p>
                  <p style={{ color: 'var(--down)' }}><b>代价：</b>{e.cost}</p>
                  <div style={{ margin: '8px 0' }}>
                    <b style={{ fontSize: 12.8 }}>你正在走向那里的路标：</b>
                    {e.signs.map((s, i) => (
                      <div key={i} className="judge-notes" style={{ marginTop: 3 }}>□ {s}</div>
                    ))}
                  </div>
                  <p style={{ color: 'var(--up)' }}><b>芒格式逆向：</b>{e.inversion}</p>
                </div>
              )}
              <div className="academy-more">{expanded ? '收起 ▲' : '看完整死法 ▼'}</div>
            </div>
          )
        })}
      </div>
    </>
  )
}

export default function AcademyView({ initialMode = 'dict' }) {
  const [data, setData] = useState(null)
  const [cat, setCat] = useState('全部')
  const [open, setOpen] = useState(null)
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState(initialMode)

  useEffect(() => { setMode(initialMode) }, [initialMode])

  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let cancelled = false
    fetchRetry('/api/academy').then((d) => {
      if (cancelled) return
      if (d) setData(d)
      else setTimeout(() => !cancelled && setAttempt((a) => a + 1), 4000)
    })
    return () => { cancelled = true }
  }, [attempt])

  if (!data) return <div className="detail loading"><span className="spin" /> 加载学堂…</div>

  if (mode === 'pitfalls') {
    return (
      <div className="detail">
        <div className="detail-header">
          <h2>跌倒地图</h2>
          <span className="nav" style={{ marginLeft: 0 }}>
            <button onClick={() => setMode('dict')}>概念词典</button>
            <button className="active" onClick={() => setMode('pitfalls')}>跌倒地图</button>
          </span>
        </div>
        <FailureMap />
      </div>
    )
  }

  const cats = ['全部', ...data.categories]
  const entries = data.entries.filter((e) =>
    (cat === '全部' || e.category === cat)
    && (!query || e.title.includes(query) || e.one_liner.includes(query)))

  return (
    <div className="detail">
      <div className="detail-header">
        <h2>说人话学堂</h2>
        <span className="nav" style={{ marginLeft: 0 }}>
          <button className="active" onClick={() => setMode('dict')}>概念词典</button>
          <button onClick={() => setMode('pitfalls')}>跌倒地图</button>
        </span>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>{data.motto}</span>
      </div>

      <div className="search-row" style={{ margin: '14px 0 8px' }}>
        <input placeholder="搜：期权 / 做空 / 夏普…" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className="quick-chips" style={{ marginBottom: 14 }}>
        {cats.map((c) => (
          <span key={c} className="chip" onClick={() => setCat(c)}
            style={cat === c ? { borderColor: 'var(--accent)', color: 'var(--accent)' } : {}}>
            {c}
          </span>
        ))}
      </div>

      <div className="academy-grid">
        {entries.map((e) => {
          const expanded = open === e.id
          return (
            <div key={e.id} className={`academy-card ${expanded ? 'open' : ''}`}
              onClick={() => setOpen(expanded ? null : e.id)}>
              <div className="academy-head">
                <span className="academy-emoji">{e.emoji}</span>
                <div>
                  <div className="academy-title">{e.title}</div>
                  <div className="academy-cat">{e.category}</div>
                </div>
              </div>
              <p className="academy-liner">{e.one_liner}</p>
              {expanded && (
                <div className="academy-body">
                  <p><b>怎么运作：</b>{e.how}</p>
                  <p><b>适合谁：</b>{e.fit}</p>
                  <p style={{ color: 'var(--down)' }}><b>⚠最大风险：</b>{e.risk}</p>
                  <p style={{ color: 'var(--neutral)' }}><b>常见误区：</b>{e.mistake}</p>
                </div>
              )}
              <div className="academy-more">{expanded ? '收起 ▲' : '展开细讲 ▼'}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
