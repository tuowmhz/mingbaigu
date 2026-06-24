// 首页「洞见流」：几张专业入口卡——把卡片工厂做成首页门面。
const CARDS = [
  { title: '论点拆解', desc: '说一句你对当下的判断，AI 帮你拆成 多空 + 标的 + 怎么验证，用真实数据做地基、逼你看反面。', go: 'thesis' },
  { title: '产业链卡脖子', desc: '一条链下游→上游，找出真正有定价权的卡点环节。', go: 'sectors' },
  { title: '你是哪种炒股体质', desc: '12 个真实场景，3 分钟测出你最容易栽的坑。可晒。', go: 'quiz' },
  { title: '财报拆解', desc: '把一份财报讲成人话，含股价位置。', go: 'earnings' },
  { title: '今日人话日报', desc: '三分钟看懂今天的市场，不堆术语。', go: 'daily' },
]

export default function HomeFeed({ onGo }) {
  return (
    <div style={{ margin: '8px 0 16px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
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
