import { useEffect, useState } from 'react'

// 人话日报：每天一封的精选，看完就可以关掉——反焦虑的 Newsletter 形态
async function fetchRetry(url, tries = 3) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(30000) })
      if (r.ok) return r.json()
    } catch {}
    await new Promise((res) => setTimeout(res, 2000))
  }
  return null
}

function DigestItem({ item, rank }) {
  const main = item.links?.[0]
  return (
    <div className="digest-item">
      <span className="digest-rank">{rank}</span>
      <div style={{ flex: 1 }}>
        <div className="digest-intro">
          {item.intro_cn || item.title}
          {item.cross_source && <span className="resonance-tag">{item.sources.length} 家共振</span>}
        </div>
        {item.intro_cn && <div className="judge-notes" style={{ marginTop: 2 }}>{item.title}</div>}
        <div className="digest-meta">
          {item.sources.map((s) => <span key={s} className="src-badge">{s}</span>)}
          {item.events?.map((e) => <span key={e} className="src-badge" style={{ color: 'var(--accent)' }}>{e}</span>)}
          {main?.link && (
            <a href={main.link} target="_blank" rel="noreferrer" className="digest-link">原文 ↗</a>
          )}
        </div>
      </div>
    </div>
  )
}

export default function NewsletterView() {
  const [brief, setBrief] = useState(null)
  const [digest, setDigest] = useState(null)
  const [copied, setCopied] = useState(false)
  const [attempt, setAttempt] = useState(0)

  // 拿不到就隔几秒再来一轮，不让一次坏窗口把页面卡死在加载态
  useEffect(() => {
    let cancelled = false
    Promise.all([
      brief ? Promise.resolve(brief) : fetchRetry('/api/brief').then((d) => { if (d && !cancelled) setBrief(d); return d }),
      digest ? Promise.resolve(digest) : fetchRetry('/api/digest').then((d) => { if (d && !cancelled) setDigest(d); return d }),
    ]).then(([b, dg]) => {
      if (!cancelled && !b && !dg) setTimeout(() => !cancelled && setAttempt((a) => a + 1), 4000)
    })
    return () => { cancelled = true }
  }, [attempt])

  if (!brief && !digest) {
    return <div className="detail loading"><span className="spin" /> 正在备好今天这一封…</div>
  }

  return (
    <div className="detail">
      <div className="detail-header">
        <h2>人话日报</h2>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>
          每天一封精选，看完就可以关掉——不轰炸、不催你刷新
        </span>
      </div>

      {brief && (
        <div className="panel" style={{ marginTop: 14 }}>
          <h3>三分钟看懂今天 · {brief.date}</h3>
          {brief.sections.map((s) => (
            <div key={s.title} style={{ marginBottom: 10 }}>
              <b style={{ fontSize: 13 }}>{s.title}</b>
              {s.lines.map((l, i) => (
                <div key={i} className="judge-notes" style={{ marginTop: 3 }}>{l}</div>
              ))}
            </div>
          ))}
          <button className="link-btn" onClick={() => {
            navigator.clipboard.writeText(brief.markdown).then(() => {
              setCopied(true); setTimeout(() => setCopied(false), 2500)
            })
          }}>{copied ? '✅ 已复制 Markdown' : '复制全文（贴进 Substack 直接发）'}</button>
          <div className="judge-notes" style={{ marginTop: 4 }}>{brief.disclaimer}</div>
        </div>
      )}

      {digest && (
        <div className="panel" style={{ marginTop: 14 }}>
          <h3>全球爆款精选 <span style={{ fontWeight: 400, fontSize: 11.5, color: 'var(--text-dim)' }}>
            今日 {digest.n_raw} 条原始新闻 → {digest.n_clusters} 个故事 → 精选 {digest.items.length} 条
          </span></h3>
          {digest.items.map((it, i) => <DigestItem key={i} item={it} rank={i + 1} />)}
          <div className="judge-notes" style={{ marginTop: 8 }}>{digest.methodology}</div>
          {!digest.intro_engine && (
            <div className="judge-notes" style={{ marginTop: 4 }}>
              中文导读暂未点亮（服务端配置 AI 后自动出现）。
            </div>
          )}
        </div>
      )}
    </div>
  )
}
