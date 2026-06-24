import { useEffect, useState } from 'react'
import { track } from './apiBase.js'
import { FEATURES } from './features.js'
import { fetchWatchlist } from './api/client'
import ChainView from './components/ChainView.jsx'
import AcademyView from './components/AcademyView.jsx'
import EarningsView from './components/EarningsView.jsx'
import NewsletterView from './components/NewsletterView.jsx'
import PitfallQuiz from './components/PitfallQuiz.jsx'
import Landing from './components/Landing.jsx'
import TrackRecordView from './components/TrackRecordView.jsx'
import PortfolioView from './components/PortfolioView.jsx'
import QuantView from './components/QuantView.jsx'
import AShareStrategyView from './components/AShareStrategyView.jsx'
import TrafficDashboard from './components/TrafficDashboard.jsx'
import { shareCard } from './shareCard.js'
import ThesisView from './components/ThesisView.jsx'
import NarrativeCheckView from './components/NarrativeCheckView.jsx'
import HomeFeed from './components/HomeFeed.jsx'
import SectorsView from './components/SectorsView.jsx'

// renhuagu.com 是日报优先的入口：默认落在"人话日报"，品牌名随域名
const IS_RENHUAGU = typeof location !== 'undefined' && location.hostname.includes('renhuagu')

// 0.1 分发精简开关（见 features.js / README）：持仓、量化、低波蓝筹、成绩单暂时隐藏
const SHOW_PORTFOLIO = FEATURES.portfolio

// 体质测验钩子：没测过 → 醒目邀请；测过 → 人格徽章（身份感 + 高危区提醒入口）
function QuizHook({ onStart }) {
  const profile = localStorage.getItem('sp_pitfall_profile')
  const arch = JSON.parse(localStorage.getItem('sp_archetype') || 'null')
  if (profile && arch) {
    return (
      <div className="quiz-badge">
        你的股市体质：<b>{arch.emoji} {arch.name}</b>
        <span className="judge-notes" style={{ margin: 0 }}>个股页会自动标出你的高危区</span>
        <button className="link-btn" style={{ marginLeft: 'auto' }} onClick={onStart}>重测</button>
      </div>
    )
  }
  if (profile) return null
  return (
    <div className="quiz-cta" onClick={onStart}>
      <b>你是哪种股市体质？</b>12 个真实场景，3 分钟测出你的投资人格和最容易栽的坑
      <span className="grad-btn" style={{ padding: '5px 16px', fontSize: 12.5, marginLeft: 'auto' }}>立即开测</span>
    </div>
  )
}

// 新访客首屏：30 秒讲清楚这个产品是干嘛的（三张王牌 + 直达按钮）
function IntroHero({ onClose, onGo }) {
  const cards = [
    { emoji: '', title: '你是哪种股市体质？', desc: '12 个真实场景，3 分钟测出你的投资人格、和你最容易栽进去的坑。可以晒。', cta: '立即开测', go: ['quiz'], hot: true },
    { emoji: '', title: '三分钟看懂一只股票', desc: '多空证据摆上桌面，AI 把数字背后的因果用人话讲明白。美股、A股都行。', cta: '看一只股票', go: ['stocks'] },
    { emoji: '', title: '拆懂一条产业链', desc: '太阳能、核能、机器人、量子计算…十几条产业链，从下游到上游找出卡脖子环节。', cta: '看产业链图谱', go: ['sectors'] },
    FEATURES.record && { emoji: '', title: '我们敢被检验', desc: '每天的预测全部公证存档在 GitHub，错的不删、亏的置顶。别信我们，查我们。', cta: '查公开成绩单', go: ['record'] },
  ].filter(Boolean)
  return (
    <div className="intro-hero">
      <div className="intro-head">
        <div>
          <div className="intro-title">这里帮你想清楚，不帮你着急。</div>
          <div className="intro-sub">给每个人的股票决策工具——不荐股、不收割、不制造焦虑。</div>
        </div>
        <button className="link-btn" onClick={onClose}>知道了 </button>
      </div>
      <div className="intro-cards">
        {cards.map((c) => (
          <div className={`intro-card ${c.hot ? 'hot' : ''}`} key={c.title} onClick={() => { onGo(...c.go); onClose() }}>
            <div className="intro-emoji">{c.emoji}{c.hot && <span className="hot-tag">最多人玩</span>}</div>
            <b>{c.title}</b>
            <p>{c.desc}</p>
            <span className="intro-cta">{c.cta} →</span>
          </div>
        ))}
      </div>
    </div>
  )
}
import StockCard from './components/StockCard.jsx'
import StockDetail from './components/StockDetail.jsx'

const SCALE_LABELS = { 1: '标准', 2: '舒适', 3: '超大' }

function FontScale() {
  const [scale, setScale] = useState(() => localStorage.getItem('sp_scale') || '1')
  const cycle = () => {
    const next = String(+scale % 3 + 1)
    setScale(next)
    localStorage.setItem('sp_scale', next)
    document.body.dataset.scale = next
  }
  return (
    <button className="font-scale-btn" onClick={cycle}
      title={`字号：${SCALE_LABELS[scale]}（点击切换，怎么舒服怎么来）`}>
      <span style={{ fontSize: 12 }}>A</span>
      <span style={{ fontSize: 16 }}>a</span>
      {scale !== '1' && <span className="font-scale-dot">{SCALE_LABELS[scale]}</span>}
    </button>
  )
}

function DailyBrief() {
  const [brief, setBrief] = useState(null)
  const [open, setOpen] = useState(false)
  useEffect(() => {
    fetch('/api/brief').then((r) => r.json()).then(setBrief).catch(() => {})
  }, [])
  if (!brief) return null
  return (
    <div className="brief-panel">
      <div className="brief-head" onClick={() => setOpen(!open)}>
        三分钟看懂今天 · {brief.date}
        <span style={{ color: 'var(--text-dim)', fontSize: 11, marginLeft: 8 }}>
          {open ? '收起 ▲' : '展开 ▼'}
        </span>
      </div>
      {open && (
        <div className="brief-body">
          {brief.sections.map((s) => (
            <div key={s.title} style={{ marginBottom: 10 }}>
              <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4 }}>{s.title}</div>
              {s.lines.map((l, i) => (
                <div key={i} className="judge-notes" style={{ marginTop: 2 }}>· {l}</div>
              ))}
            </div>
          ))}
          <div className="judge-notes">{brief.disclaimer}</div>
        </div>
      )}
    </div>
  )
}

function heatShareSpec(heat) {
  const items = (heat.items || []).slice(0, 8)
  return {
    column: '今日热度',
    headline: '今天，散户都在围观这些',
    subhead: heat.note || 'A股散户围观热度榜',
    viz: {
      type: 'bars', note: '按围观热度排序（↑=排名快速上升）',
      items: items.map((h, i) => ({
        label: `${h.rank}. ${h.name}`,
        value: Math.max(20, 100 - i * 10),
        tone: (h.rank_change || 0) > 20 ? 'hot' : 'cool',
      })),
    },
    takeaway: '热度高 ≠ 该买——围观最多的，往往也是回撤时最拥挤的。先看懂，再决定。',
    chips: ['散户围观榜', '不构成投资建议'],
    cta: '看懂你关心的那只 →',
    tags: ['散户热度', 'A股', '投资'],
  }
}

function HeatStrip({ onAnalyze }) {
  const [heat, setHeat] = useState(null)
  useEffect(() => {
    fetch('/api/heat').then((r) => r.json()).then(setHeat).catch(() => {})
  }, [])
  if (!heat?.items?.length) return null
  return (
    <div className="heat-strip" title={heat.note}>
      <span className="fg-title">散户在围观</span>
      {heat.items.slice(0, 10).map((h) => (
        <span key={h.ticker} className="chip" onClick={() => onAnalyze(h.ticker)}>
          {h.rank}. {h.name}
          {(h.rank_change || 0) > 20 && <span style={{ color: 'var(--up)' }}> ↑</span>}
        </span>
      ))}
      <button className="link-btn" style={{ marginLeft: 8, verticalAlign: 0 }}
        onClick={() => shareCard(heatShareSpec(heat))}>分享今日热度</button>
    </div>
  )
}

// 恐惧贪婪 5 个成分的人话解释（前端兜底，避免后端缓存未刷新时丢失富文本）
const FG_DESC = {
  momentum: '标普500 离它 125 日均线越远、涨得越凶，市场越亢奋。高分=贪婪，跌破均线偏恐惧。',
  volatility: 'VIX 是『恐慌指数』，越高说明大家越害怕。这里取反：VIX 低=平静=高分（贪婪），VIX 飙升=低分（恐惧）。',
  safe_haven: '比近 20 天股票和长期国债谁涨得多。钱涌向债券避险=低分（恐惧），敢追股票=高分（贪婪）。',
  junk: '比『垃圾债（高收益债）』和安全的投资级债。愿意买垃圾债博收益=风险胃口大=高分（贪婪），躲回安全债=恐惧。',
  breadth: '多少只股票站上了 50 日均线。多数都涨=健康的贪婪（高分）；只剩少数权重股撑指数=外强中干、偏恐惧。',
}

function FearGreedGauge() {
  const [fg, setFg] = useState(null)
  useEffect(() => {
    let alive = true
    const load = () => fetch('/api/market/sentiment').then((r) => r.json())
      .then((d) => alive && setFg(d)).catch(() => {})
    load()
    const id = setInterval(load, 3600000)
    return () => { alive = false; clearInterval(id) }
  }, [])
  if (!fg) return null
  const cls = fg.index <= 25 ? 'bearish' : fg.index <= 45 ? 'neutral' : fg.index <= 75 ? '' : 'bullish'
  const color = fg.index <= 25 ? 'var(--down)' : fg.index <= 45 ? 'var(--neutral)' : fg.index <= 75 ? 'var(--text)' : 'var(--up)'
  return (
    <div className="fg-bar" title={fg.hint}>
      <span className="fg-title">恐惧贪婪指数</span>
      <span className="fg-value" style={{ color }}>{fg.index}</span>
      <span className={`badge ${cls}`}>{fg.label_cn}</span>
      <div className="signal-bar" style={{ flex: 1, maxWidth: 220 }}>
        <div className="signal-marker" style={{ left: `${Math.max(2, Math.min(98, fg.index))}%` }} />
      </div>
      <span className="fg-components">
        {fg.components.flatMap((c, i) => {
          const node = (
            <span key={c.key} className="fg-comp" data-tip={c.desc || FG_DESC[c.key] || c.note}
              title={c.desc || FG_DESC[c.key] || c.note}>
              {c.name} {c.value}
            </span>
          )
          return i === 0 ? [node] : [<span key={c.key + '_s'} className="fg-sep"> · </span>, node]
        })}
      </span>
    </div>
  )
}

// AI 泡沫指数：龙头 vs 故事股的资金结构体温计（信息性，不构成投资建议）
const BUBBLE_COLOR = { green: 'var(--up)', yellow: 'var(--neutral)', orange: '#ff9f43', red: 'var(--down)' }
function AiBubbleGauge() {
  const [b, setB] = useState(null)
  useEffect(() => {
    let alive = true
    const load = () => fetch('/api/ai-bubble').then((r) => r.json())
      .then((d) => alive && d && d.index != null && setB(d)).catch(() => {})
    load()
    const id = setInterval(load, 3600000)
    return () => { alive = false; clearInterval(id) }
  }, [])
  if (!b) return null
  const color = BUBBLE_COLOR[b.level] || 'var(--text)'
  return (
    <div className="fg-bar" title={b.hint}>
      <span className="fg-title">AI 泡沫指数</span>
      <span className="fg-value" style={{ color }}>{b.index}</span>
      <span className="badge" style={{ borderColor: color, color }}>{b.stage_cn}</span>
      <div className="signal-bar" style={{ flex: 1, maxWidth: 220 }}>
        <div className="signal-marker" style={{ left: `${Math.max(2, Math.min(98, b.index))}%` }} />
      </div>
      <span className="fg-components">
        {b.components.flatMap((c, i) => {
          const node = (
            <span key={c.key} className="fg-comp" data-tip={c.desc || c.note} title={c.desc || c.note}>
              {c.name} {c.value}
            </span>
          )
          return i === 0 ? [node] : [<span key={c.key + '_s'} className="fg-sep"> · </span>, node]
        })}
        {b.pending?.length > 0 && <span className="fg-sep"> · </span>}
        {b.pending?.length > 0 && (
          <span className="fg-comp" style={{ opacity: .55 }}
            data-tip={'这些信号需付费数据、尚未接入，未计入评分：\n· ' + b.pending.join('\n· ')}
            title={'待接入（未计入评分）：' + b.pending.join('；')}>+{b.pending.length} 项待接入</span>
        )}
      </span>
      <button className="link-btn" style={{ verticalAlign: 0, fontSize: 12, marginLeft: 6, whiteSpace: 'nowrap' }}
        title="生成可分享的市场体温卡（小红书 / 微信）"
        onClick={() => shareCard({
          column: 'AI 泡沫指数 · 市场体温',
          headline: `AI 泡沫体温 ${b.index} · ${b.stage_cn}`,
          subhead: '龙头 vs 故事股的资金结构 · 数字越高越像泡沫后期',
          viz: {
            type: 'bars', note: '子信号 0–100，越高越泡沫',
            items: b.components.map((c) => ({
              label: c.name, value: c.value,
              tone: c.status === 'red' ? 'hot' : (c.status === 'orange' || c.status === 'yellow') ? 'warn' : 'ok',
            })),
          },
          takeaway: b.hint,
          chips: ['免费价格数据', '不预测顶部', '不构成投资建议'],
          cta: '拆你关心的板块泡沫度 →', tags: ['AI', '美股', '泡沫'],
        })}>体温卡</button>
    </div>
  )
}

function TickerTape({ stocks }) {
  if (!stocks.length) return null
  const items = [...stocks, ...stocks]
  return (
    <div className="tape">
      <div className="tape-track">
        {items.map((s, i) => (
          <span className="tape-item" key={i}>
            <b>{s.ticker}</b>{s.currency || '$'}{s.price}
            <span className={s.change_pct >= 0 ? 'up' : 'down'}>
              {s.change_pct >= 0 ? '▲' : '▼'}{Math.abs(s.change_pct)}%
            </span>
          </span>
        ))}
      </div>
    </div>
  )
}

const WATCHLIST_KEY = 'sp_custom_watchlist'

// 深链路由：分享/UTM 链接可直达指定板块或个股
// 例 ?view=record（成绩单）、?t=NVDA（直接分析 NVDA）、?view=academy&mode=pitfalls（跌倒地图）
function initialRoute() {
  try {
    const p = new URLSearchParams(window.location.search)
    const VIEWS = ['stocks', 'thesis', 'narrative', 'sectors', 'chain', 'earnings', 'academy', 'daily', 'traffic',
      ...(FEATURES.portfolio ? ['portfolio'] : []),
      ...(FEATURES.quant ? ['quant'] : []),
      ...(FEATURES.ashare ? ['ashare'] : []),
      ...(FEATURES.record ? ['record'] : [])]
    let view = p.get('view')
    const ticker = (p.get('t') || p.get('stock') || '').toUpperCase().trim()
    if (ticker) view = 'stocks'
    if (!VIEWS.includes(view)) view = null
    return { view, ticker: ticker || null, mode: p.get('mode') === 'pitfalls' ? 'pitfalls' : 'dict' }
  } catch { return { view: null, ticker: null, mode: 'dict' } }
}
const ROUTE = initialRoute()

// A股代码宽松比较：用户输入 600519 与池中 600519.SS 视为同一只
const tickerEq = (a, b) => a === b || a.split('.')[0] === b || b.split('.')[0] === a

export default function App() {
  const [stocks, setStocks] = useState([])
  const [disclaimer, setDisclaimer] = useState('')
  const [selected, setSelected] = useState(ROUTE.ticker)
  const [error, setError] = useState(null)
  const [view, setView] = useState(ROUTE.view || (IS_RENHUAGU ? 'daily' : 'stocks'))
  const [earningsQuery, setEarningsQuery] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [customTickers, setCustomTickers] = useState(
    () => JSON.parse(localStorage.getItem(WATCHLIST_KEY) || '[]'),
  )
  const [customStocks, setCustomStocks] = useState([])
  const [alertBanner, setAlertBanner] = useState(null)
  // 全屏落地页：mingbaigu 冷流量首次进来先看到它；深链/老用户/renhuagu 跳过
  const [showLanding, setShowLanding] = useState(
    () => !IS_RENHUAGU && !localStorage.getItem('sp_seen_landing') && !ROUTE.view && !ROUTE.ticker)
  // 深链到具体内容时跳过首屏引导，直接展示分享目标
  const [showIntro, setShowIntro] = useState(
    () => !localStorage.getItem('sp_seen_intro') && !ROUTE.view && !ROUTE.ticker
      && (IS_RENHUAGU || localStorage.getItem('sp_seen_landing')))
  const [market, setMarket] = useState(() => localStorage.getItem('sp_market_pref') || 'all')
  const [academyMode, setAcademyMode] = useState(ROUTE.mode)
  // 聚焦幻灯片模式：分析一只股时，报告独占主屏，藏掉自选/热度/列表（深链 ?t= 直接进入）
  const [focus, setFocus] = useState(() => !!ROUTE.ticker)

  const openStock = (ticker) => {
    setSelected(ticker); setFocus(true)
    if (typeof window !== 'undefined') window.scrollTo({ top: 0 })
  }

  const closeIntro = () => { localStorage.setItem('sp_seen_intro', '1'); setShowIntro(false) }
  const goFeature = (v, mode) => { if (v === 'academy') setAcademyMode(mode || 'dict'); setView(v) }

  // 从落地页进入工具：标记已看过，按 CTA 落到对应板块
  const enterApp = (target) => {
    localStorage.setItem('sp_seen_landing', '1')
    localStorage.setItem('sp_seen_intro', '1')
    setShowLanding(false); setShowIntro(false)
    if (target === 'quiz') setView('quiz')
    else if (target === 'record') setView('record')
    else if (target === 'stocks') setView('stocks')
    else if (target === 'sectors') setView('sectors')
    else if (target === 'academy_pitfalls') { setAcademyMode('pitfalls'); setView('academy') }
  }
  const pickMarket = (m) => { setMarket(m); localStorage.setItem('sp_market_pref', m) }

  const openEarnings = (ticker) => {
    setEarningsQuery(ticker)
    setView('earnings')
  }

  const toggleCustom = (ticker) => {
    setCustomTickers((prev) => {
      const next = prev.includes(ticker)
        ? prev.filter((t) => t !== ticker)
        : [...prev, ticker]
      localStorage.setItem(WATCHLIST_KEY, JSON.stringify(next))
      return next
    })
  }

  const analyzeTicker = () => {
    const t = searchInput.trim().toUpperCase()
    if (t) openStock(t)
  }

  const loadCustom = (tickers) => {
    const fixed = new Set(stocks.map((s) => s.ticker))
    Promise.all(
      tickers.filter((t) => !fixed.has(t)).map((t) =>
        fetch(`/api/quote/${t}`).then((r) => (r.ok ? r.json() : null)).catch(() => null)),
    ).then((cards) => setCustomStocks(cards.filter(Boolean)))
  }

  useEffect(() => {
    if (IS_RENHUAGU) document.title = '人话股 · 每天一封人话日报'
  }, [])

  useEffect(() => {
    fetchWatchlist()
      .then((d) => {
        setStocks(d.stocks)
        setDisclaimer(d.disclaimer)
        if (d.stocks.length && !selected) setSelected(d.stocks[0].ticker)
      })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => { loadCustom(customTickers) }, [customTickers, stocks.length])

  // 埋点（隐私友好：当日盐哈希，不追踪个人）+ UTM 首触来源
  useEffect(() => { track(view) }, [view])

  // 每 5 分钟静默刷新行情（与后端缓存同频）
  useEffect(() => {
    const id = setInterval(() => {
      fetchWatchlist().then((d) => setStocks(d.stocks)).catch(() => {})
      loadCustom(customTickers)
    }, 300000)
    return () => clearInterval(id)
  }, [customTickers])

  // 每分钟轮询触发的提醒，弹横幅 + 浏览器通知（属持仓/提醒功能，0.1 精简版关闭）
  useEffect(() => {
    if (!SHOW_PORTFOLIO) return
    const poll = () => fetch('/api/alerts').then((r) => r.json()).then((d) => {
      const unseen = (d.triggered || []).filter((t) => !t.seen)
      if (unseen.length) {
        setAlertBanner(unseen.map((t) => t.message).join('；'))
        if (window.Notification?.permission === 'granted') {
          unseen.forEach((t) => new Notification('StockPrediction 提醒', { body: t.message }))
        } else if (window.Notification?.permission === 'default') {
          Notification.requestPermission()
        }
        fetch('/api/alerts/seen', { method: 'POST' })
      }
    }).catch(() => {})
    poll()
    const id = setInterval(poll, 60000)
    return () => clearInterval(id)
  }, [])

  const usHot = stocks.filter((s) => s.category !== 'cn')   // 美股近期热门（按成交额/放量）
  const cnHot = stocks.filter((s) => s.category === 'cn')   // A股人气榜热门

  if (showLanding) return <Landing onEnter={enterApp} />

  return (
    <div className="app">
      <div className="header">
        <h1>{IS_RENHUAGU ? '人话股' : (
          <img src="/logo.svg" alt="明白股" style={{ height: 34, width: 34, display: 'block' }} />
        )}</h1>
        <span className="sub"><span className="live-dot" />
          {IS_RENHUAGU
            ? '每天一封人话日报 · 看完就可以关掉'
            : '三分钟看懂一只股票 · 美股 + A股 · 不懂行话也能用'}
        </span>
        <button className="link-btn" style={{ fontSize: 11.5 }} onClick={() => setShowLanding(true)}>这是什么？</button>
        <FontScale />
        <nav className="nav">
          {IS_RENHUAGU && (
            <button className={view === 'daily' ? 'active' : ''} onClick={() => setView('daily')}>人话日报</button>
          )}
          <button className={view === 'stocks' && !focus ? 'active' : ''} onClick={() => { setFocus(false); setView('stocks') }}>个股分析</button>
          {SHOW_PORTFOLIO && <button className={view === 'portfolio' ? 'active' : ''} onClick={() => setView('portfolio')}>持仓</button>}
          <button className={view === 'sectors' || view === 'chain' ? 'active' : ''} onClick={() => setView('sectors')}>产业链图谱</button>
          {FEATURES.quant && <button className={view === 'quant' ? 'active' : ''} onClick={() => setView('quant')}>量化组合</button>}
          {FEATURES.ashare && <button className={view === 'ashare' ? 'active' : ''} onClick={() => setView('ashare')}>低波蓝筹</button>}
          <button className={view === 'academy' ? 'active' : ''} onClick={() => setView('academy')}>学堂</button>
          {!IS_RENHUAGU && (
            <button className={view === 'daily' ? 'active' : ''} onClick={() => setView('daily')}>日报</button>
          )}
          {FEATURES.record && <button className={view === 'record' ? 'active' : ''} onClick={() => setView('record')}>成绩单</button>}
        </nav>
      </div>
      {alertBanner && (
        <div className="alert-banner" onClick={() => setAlertBanner(null)}>
          {alertBanner} <span style={{ opacity: .6, marginLeft: 8 }}>（点击关闭）</span>
        </div>
      )}
      {view === 'stocks' && !focus && <HomeFeed onGo={(v) => setView(v)} />}
      {view === 'stocks' && !focus && <DailyBrief />}
      {view === 'stocks' && !focus && <HeatStrip onAnalyze={(t) => { setView('stocks'); openStock(t) }} />}
      {view === 'daily' && <NewsletterView />}
      {view === 'traffic' && <TrafficDashboard />}
      {view === 'thesis' && <ThesisView onOpenStock={(t) => { setView('stocks'); openStock(t) }} />}
      {view === 'narrative' && <NarrativeCheckView onOpenStock={(t) => { setView('stocks'); openStock(t) }} />}
      {FEATURES.record && view === 'record' && <TrackRecordView />}
      {view === 'sectors' && <SectorsView onOpenStock={(t) => { setView('stocks'); openStock(t) }} onOpenLiveAI={() => setView('chain')} />}
      {view === 'quiz' && (
        <div className="detail">
          <div className="detail-header"><h2>股市体质测试</h2></div>
          <PitfallQuiz onClose={() => setView('stocks')} />
        </div>
      )}
      {SHOW_PORTFOLIO && view === 'portfolio' && <PortfolioView />}
      {view === 'academy' && <AcademyView initialMode={academyMode} />}
      {view === 'chain' && <ChainView onOpenEarnings={openEarnings} />}
      {FEATURES.quant && view === 'quant' && <QuantView />}
      {FEATURES.ashare && view === 'ashare' && <AShareStrategyView />}
      {view === 'earnings' && <EarningsView initialQuery={earningsQuery} />}
      {view === 'stocks' && (focus && selected ? (
        <>
          <div className="focus-bar">
            <button className="link-btn" onClick={() => setFocus(false)}>← 返回列表</button>
          </div>
          <div className="slide-stage" key={selected}>
            <StockDetail ticker={selected} onOpenEarnings={openEarnings}
              watched={customTickers.includes(selected) || stocks.some((s) => tickerEq(s.ticker, selected))}
              inFixedList={stocks.some((s) => tickerEq(s.ticker, selected))}
              onToggleWatch={() => toggleCustom(selected)} />
          </div>
        </>
      ) : (<>
      {showIntro && <IntroHero onClose={closeIntro} onGo={goFeature} />}
      {error && <div className="error">加载失败：{error}（请确认后端已启动）</div>}

      <div className="search-row" style={{ margin: '4px 0 6px' }}>
        <input
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && analyzeTicker()}
          placeholder="A股美股都能查：600519 / 贵州茅台 / NKE …"
        />
        <button onClick={analyzeTicker}>分析</button>
      </div>

      <div className="quick-chips" style={{ margin: '2px 0 8px' }}>
        {[['all', '全部'], ['cn', 'A股'], ['us', '美股']].map(([m, label]) => (
          <span key={m} className="chip" onClick={() => pickMarket(m)}
            style={market === m ? { borderColor: 'var(--accent)', color: 'var(--accent)' } : {}}>
            {label}
          </span>
        ))}
      </div>

      {customStocks.length > 0 && (
        <>
          <div className="section-title">我的自选</div>
          <div className="grid">
            {customStocks.map((s, i) => (
              <StockCard key={s.ticker} stock={s} idx={i} active={selected === s.ticker}
                onClick={() => openStock(s.ticker)}
                onRemove={() => toggleCustom(s.ticker)} />
            ))}
          </div>
        </>
      )}
      {!stocks.length && !error && (
        <div className="grid">
          {Array.from({ length: 6 }, (_, i) => (
            <div className="card skeleton" key={i}>
              <div className="sk-line" style={{ width: '55%' }} />
              <div className="sk-line" style={{ width: '40%', height: 22 }} />
              <div className="sk-line" style={{ width: '100%', height: 38 }} />
              <div className="sk-line" style={{ width: '70%' }} />
            </div>
          ))}
        </div>
      )}

      {market !== 'us' && cnHot.length > 0 && (
        <>
          <div className="section-title">A股 · 近期热门（人气榜）</div>
          <div className="grid">
            {cnHot.map((s, i) => (
              <StockCard key={s.ticker} stock={s} idx={i} active={selected === s.ticker}
                onClick={() => openStock(s.ticker)} />
            ))}
          </div>
        </>
      )}

      {market !== 'cn' && usHot.length > 0 && (
        <>
          <div className="section-title" style={{ marginTop: 18 }}>美股 · 近期热门（成交活跃）</div>
          <div className="grid">
            {usHot.map((s, i) => (
              <StockCard key={s.ticker} stock={s} idx={i} active={selected === s.ticker}
                onClick={() => openStock(s.ticker)} />
            ))}
          </div>
        </>
      )}

      {disclaimer && <div className="timeliness-note" style={{ opacity: .7 }}>{disclaimer}</div>}
      </>))}

      <div className="timeliness-note">
        信息时效 · 行情每 5 分钟更新（免费源约 15 分钟延迟）· 新闻分钟级 · 财报与持仓数据每日 ——
        我们刻意不做秒级刷新：这里帮你想清楚，不帮你着急。
      </div>
    </div>
  )
}
