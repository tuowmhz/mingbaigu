// App 壳（Capacitor）里页面跑在 capacitor://localhost，相对路径 /api 会打到壳自己。
// 这里在最早时机给 fetch 打补丁：App 环境下把 /api 请求改写到线上后端。
// 网页环境（mingbaigu.com / 本地 vite 代理）不受影响。
const API_ORIGIN = 'https://mingbaigu.com'

const isNativeShell = typeof window !== 'undefined'
  && (window.Capacitor?.isNativePlatform?.() || window.location.protocol === 'capacitor:')

if (isNativeShell) {
  const rawFetch = window.fetch.bind(window)
  window.fetch = (input, init) => {
    if (typeof input === 'string' && input.startsWith('/api')) {
      return rawFetch(API_ORIGIN + input, init)
    }
    if (input instanceof Request && new URL(input.url).pathname.startsWith('/api')) {
      return rawFetch(new Request(API_ORIGIN + new URL(input.url).pathname + new URL(input.url).search, input), init)
    }
    return rawFetch(input, init)
  }
}

export const IS_APP = isNativeShell

// —— UTM 首触归因 ——
// 访客第一次进来时记下来源(优先 UTM 参数，否则从 referrer 推断)，存本地。
// 之后回访仍带同一来源，于是能回答"哪条渠道带来的人会留下来"。
const REFERRER_MAP = [
  ['xiaohongshu', 'xiaohongshu'], ['xhslink', 'xiaohongshu'], ['xhscdn', 'xiaohongshu'],
  ['zhihu', 'zhihu'], ['weixin', 'wechat'], ['qq.com', 'wechat'],
  ['1point3acres', '1p3a'], ['xueqiu', 'xueqiu'],
  ['bilibili', 'bilibili'], ['youtube', 'youtube'], ['youtu.be', 'youtube'],
  ['twitter', 'twitter'], ['t.co', 'twitter'], ['x.com', 'twitter'],
  ['google', 'google'], ['bing', 'bing'], ['baidu', 'baidu'],
]

function captureAttribution() {
  try {
    if (localStorage.getItem('sp_utm')) return // 首触为准，不覆盖
    const p = new URLSearchParams(window.location.search)
    let source = p.get('utm_source')
    const campaign = p.get('utm_campaign') || ''
    const medium = p.get('utm_medium') || ''
    if (!source && document.referrer) {
      const host = new URL(document.referrer).hostname
      if (!host.includes('mingbaigu') && !host.includes('renhuagu') && !host.includes('localhost')) {
        const hit = REFERRER_MAP.find(([k]) => host.includes(k))
        source = hit ? hit[1] : host
      }
    }
    localStorage.setItem('sp_utm', JSON.stringify({ source: source || 'direct', campaign, medium }))
  } catch {}
}

if (typeof window !== 'undefined') captureAttribution()

export function getAttribution() {
  try { return JSON.parse(localStorage.getItem('sp_utm') || '{}') } catch { return {} }
}

// 统一埋点：带上首触来源 + 可选转化事件
export function track(view, event) {
  try {
    const a = getAttribution()
    window.fetch('/api/track', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ view, event, source: a.source, campaign: a.campaign }),
    }).catch(() => {})
  } catch {}
}
