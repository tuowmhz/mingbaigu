import { useEffect, useState } from 'react'
import { track } from '../apiBase.js'
import { shareCard } from '../shareCard.js'

// 跌倒体质结果 → 统一分享卡 spec（与论点卡/产业链卡同一引擎、同一品牌竖图）
function quizShareSpec(result) {
  const a = result.archetype || {}
  const tops = (result.top_pitfalls || []).slice(0, 3)
  return {
    column: '跌倒体质',
    headline: `${a.emoji || ''} ${a.name || ''}`.trim(),
    subhead: a.desc,
    viz: {
      type: 'bars', note: '最可能栽的坑 · 易感度',
      items: tops.map((t) => ({
        label: t.title, value: t.pct,
        tone: t.pct >= 60 ? 'hot' : t.pct >= 35 ? 'warn' : 'cool',
      })),
    },
    takeaway: (tops[0] && tops[0].hook) || a.desc,
    chips: ['12 场景测出', '不构成投资建议'],
    cta: '测测你是哪种炒股体质 →',
    tags: ['炒股体质', '跌倒地图', '投资'],
  }
}

export default function PitfallQuiz({ onClose }) {
  const [quiz, setQuiz] = useState(null)
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)

  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let cancelled = false
    fetch('/api/quiz', { signal: AbortSignal.timeout(20000) })
      .then((r) => r.json())
      .then((d) => !cancelled && setQuiz(d))
      .catch(() => { if (!cancelled) setTimeout(() => !cancelled && setAttempt((a) => a + 1), 3000) })
    return () => { cancelled = true }
  }, [attempt])

  if (!quiz) return <div className="loading"><span className="spin" /> 准备题目…</div>

  const submit = async (finalAnswers) => {
    setBusy(true)
    const r = await fetch('/api/quiz', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers: finalAnswers }),
    })
    const d = await r.json()
    setResult(d)
    track('academy', 'quiz_done') // 转化漏斗：测试完成
    localStorage.setItem('sp_pitfall_profile',
      JSON.stringify((d.top_pitfalls || []).map((t) => t.id)))
    // 人格徽章：首页钩子横幅测完变成身份展示
    if (d.archetype) {
      localStorage.setItem('sp_archetype',
        JSON.stringify({ name: d.archetype.name, emoji: d.archetype.emoji }))
    }
    setBusy(false)
  }

  const pick = (idx) => {
    const q = quiz.questions[step]
    const next = { ...answers, [q.id]: idx }
    setAnswers(next)
    if (step + 1 < quiz.questions.length) setStep(step + 1)
    else submit(next)
  }

  if (busy) return <div className="loading"><span className="spin" /> 生成你的体质报告…</div>

  if (result) {
    const a = result.archetype
    return (
      <div className="quiz-result">
        <div className="quiz-archetype">
          <div style={{ fontSize: 44 }}>{a.emoji}</div>
          <div className="quiz-archetype-name">{a.name}</div>
          <p className="academy-liner" style={{ marginTop: 8 }}>{a.desc}</p>
        </div>
        {result.top_pitfalls?.length > 0 && (
          <div className="panel" style={{ marginTop: 14 }}>
            <h3>你的三大高危跌倒点</h3>
            {result.top_pitfalls.map((t) => (
              <div key={t.id} style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <b>{t.emoji} {t.title}</b>
                  <div className="weight-bar-track" style={{ flex: 1, maxWidth: 160 }}>
                    <div className="weight-bar" style={{ width: `${t.pct}%`, background: 'linear-gradient(90deg,#ff5470,#ffb02e)' }} />
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>易感度 {t.pct}%</span>
                </div>
                <div className="judge-notes" style={{ marginTop: 3 }}>{t.hook}</div>
                <div className="judge-notes" style={{ marginTop: 3, color: 'var(--up)' }}>专属处方：{t.inversion}</div>
              </div>
            ))}
          </div>
        )}
        <div className="judge-notes" style={{ margin: '8px 0' }}>{result.note}</div>
        <div className="tx-form">
          <button className="grad-btn" onClick={() => shareCard(quizShareSpec(result))}>生成分享卡（小红书/微信）</button>
          <button className="link-btn" style={{ verticalAlign: 0 }} onClick={() => {
            navigator.clipboard.writeText(result.share_text)
              .then(() => alert('已复制，发给朋友测测谁的体质更硬'))
          }}>复制文字</button>
          <button className="link-btn" style={{ verticalAlign: 0 }} onClick={() => { setResult(null); setStep(0); setAnswers({}) }}>重测</button>
          {onClose && <button className="link-btn" style={{ verticalAlign: 0 }} onClick={onClose}>返回</button>}
        </div>
      </div>
    )
  }

  const q = quiz.questions[step]
  return (
    <div className="quiz-card">
      <div className="quiz-progress">
        {quiz.questions.map((_, i) => (
          <span key={i} className={`quiz-dot ${i < step ? 'done' : i === step ? 'now' : ''}`} />
        ))}
        <span style={{ fontSize: 11, color: 'var(--text-dim)', marginLeft: 8 }}>{step + 1} / {quiz.questions.length}</span>
      </div>
      <div className="quiz-scene" key={`scene-${q.id}`}>{q.scene}</div>
      <div className="quiz-options" key={`opts-${q.id}`}>
        {q.options.map((o, i) => (
          <button key={`${q.id}-${i}`} className="quiz-option" onClick={() => pick(i)}>{o}</button>
        ))}
      </div>
      {step > 0 && (
        <div className="judge-notes" style={{ marginTop: 10, cursor: 'pointer' }}
          onClick={() => setStep(step - 1)}>← 上一题</div>
      )}
    </div>
  )
}
