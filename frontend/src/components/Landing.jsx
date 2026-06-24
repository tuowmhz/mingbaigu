import { FEATURES } from '../features.js'

// 全屏落地页：冷流量首次进来先看到它，点 CTA 才进工具。
// 老用户 / 深链（?view= ?t=）直接跳过（由 App 控制）。
const CARDS = [
  { emoji: '', title: '一页看懂', desc: '多空证据摆上桌，机器学习预判 + AI 用人话讲清数字背后的因果。美股 A股都行。', cta: '看一只股票', go: 'stocks' },
  { emoji: '', title: '先学会不亏钱', desc: '把散户 14 种亏钱方式画成地图，配查理·芒格式的反向思考——避开坑比追涨更值钱。', cta: '看跌倒地图', go: 'academy_pitfalls' },
  { emoji: '', title: '拆懂一条产业链', desc: '太阳能、核能、机器人、量子计算…十几条产业链，从下游到上游找出卡脖子环节。', cta: '看产业链图谱', go: 'sectors' },
  FEATURES.record && { emoji: '', title: '我们敢被检验', desc: '每天的预测全部公证存档在 GitHub，错的不删、亏的置顶。别信我们，查我们。', cta: '查公开成绩单', go: 'record' },
].filter(Boolean)

export default function Landing({ onEnter }) {
  return (
    <div className="lp">
      <div className="lp-nav">
        <span className="lp-logo">明白股</span>
        <span className="lp-chip">不荐股 · 不收割 · 不制造焦虑</span>
        <button className="lp-skip" onClick={() => onEnter()}>直接进入 →</button>
      </div>

      <section className="lp-hero">
        <div className="lp-badge">美股 + A股 · 写给每个人的股票决策工具</div>
        <h1 className="lp-h1">三分钟<br /><span className="grad">看懂一只股票</span></h1>
        <p className="lp-lead">
          不懂行话也能用。多空证据摆上桌面，AI 把数字背后的因果讲成人话。<br />
          <b>这里帮你想清楚，不帮你着急。</b>
        </p>
        <div className="lp-cta-row">
          <button className="lp-btn primary" onClick={() => onEnter('quiz')}>测测我的炒股体质</button>
          <button className="lp-btn ghost" onClick={() => onEnter('stocks')}>随便看一只股票 →</button>
        </div>
        <div className="lp-note">3 分钟 · 免费 · 不用注册</div>
      </section>

      <section className="lp-honesty">
        <div className="lp-big">别人告诉你「买什么」。<br /><span className="grad">我们先教你「怎么不亏」。</span></div>
        <div className="lp-proofs">
          <div><b>敢被检验</b><span>每天的预测公证存档在 GitHub，错的不删、亏的置顶。</span></div>
          <div><b>不夸大</b><span>模型没跑赢「无脑看多」基准时，我们会直接说出来。</span></div>
          <div><b>不制造焦虑</b><span>没有秒级刷新、没有「再不买就晚了」。看完就能关掉。</span></div>
        </div>
      </section>

      <section className="lp-cards">
        {CARDS.map((c) => (
          <div className="lp-card" key={c.title} onClick={() => onEnter(c.go)}>
            <div className="lp-card-emoji">{c.emoji}</div>
            <b>{c.title}</b>
            <p>{c.desc}</p>
            <span className="lp-link">{c.cta} →</span>
          </div>
        ))}
      </section>

      <section className="lp-personas" onClick={() => onEnter('quiz')}>
        <div className="lp-emojis"></div>
        <h3>你是哪种炒股体质？</h3>
        <p>8 种投资人格，对号入座，3 分钟找出你最容易栽进去的坑。最后一种最稀有。</p>
        <span className="lp-link">开始测试 →</span>
      </section>

      <section className="lp-features">
        <h3>进去你会用到</h3>
        <div className="lp-feat-grid">
          {['个股「一页看懂」', '财报拆解（含股价位置）', '人话日报 Newsletter', '恐惧贪婪指数', '跌倒地图 + 体质测试', '公开成绩单'].map((f) => (
            <span className="lp-feat" key={f}>{f}</span>
          ))}
        </div>
      </section>

      <section className="lp-final">
        <button className="lp-btn primary lg" onClick={() => onEnter('quiz')}>3 分钟，先测测你的炒股体质 →</button>
        <button className="lp-btn ghost" onClick={() => onEnter()}>先随便逛逛</button>
      </section>

      <footer className="lp-footer">
        <span>明白股 · 信息分析工具，不是券商，不构成投资建议。投资有风险，决策需独立判断。</span>
        <a href="/privacy.html" target="_blank" rel="noreferrer">隐私政策</a>
      </footer>
    </div>
  )
}
