// 首页「洞见流」：把卡片工厂做成首页门面——旗舰论点拆解 + 几张专业入口卡。
const CARDS = [
  { title: '产业链卡脖子', desc: '一条链下游→上游，找出真正有定价权的卡点环节。', go: 'sectors' },
  { title: '你是哪种炒股体质', desc: '12 个真实场景，3 分钟测出你最容易栽的坑。可晒。', go: 'quiz' },
  { title: '财报拆解', desc: '把一份财报讲成人话，含股价位置。', go: 'earnings' },
  { title: '今日人话日报', desc: '三分钟看懂今天的市场，不堆术语。', go: 'daily' },
]

export default function HomeFeed({ onGo }) {
  return (
    <div style={{ margin: '8px 0 16px' }}>
      <div onClick={() => onGo('thesis')} role="button" tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && onGo('thesis')}
        style={{
          cursor: 'pointer', borderRadius: 14, padding: '16px 18px',
          border: '1px solid var(--accent)', background: 'rgba(255,176,46,.06)',
        }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', letterSpacing: '.04em' }}>论点拆解 · 旗舰</div>
        <div style={{ fontSize: 19, fontWeight: 600, margin: '8px 0 6px', lineHeight: 1.42 }}>
          说一句你对当下的判断，AI 帮你拆成 多空 + 标的 + 怎么验证
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.55 }}>
          用真实产业链与实证传导数据做地基，逼你看反面、给出证伪条件——不替你做决定、不构成投资建议。
        </div>
        <div style={{ fontSize: 14, color: 'var(--accent)', marginTop: 10, fontWeight: 500 }}>立即拆解 →</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 10 }}>
        {CARDS.map((c) => (
          <div key={c.go} onClick={() => onGo(c.go)} role="button" tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && onGo(c.go)}
            style={{
              cursor: 'pointer', borderRadius: 12, padding: '14px 16px',
              border: '1px solid rgba(255,255,255,.08)', background: 'rgba(255,255,255,.02)',
            }}>
            <div style={{ fontSize: 15, fontWeight: 500 }}>{c.title}</div>
            <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 5, lineHeight: 1.5 }}>{c.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
