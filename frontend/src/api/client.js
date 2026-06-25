const BASE = import.meta.env.VITE_API_BASE || ''

async function get(path, timeoutMs = 30000) {
  // 超时保护：后端重启瞬间的挂起请求会被砍掉，而不是永远转圈
  const res = await fetch(`${BASE}${path}`, { signal: AbortSignal.timeout(timeoutMs) })
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
  return res.json()
}

export const fetchWatchlist = () => get('/api/watchlist')
// summary/stock 首次分析会训练模型 + FinGPT 逐条打分，给足时间
export const fetchSummary = (ticker) => get(`/api/summary/${ticker}`, 120000)
export const fetchStock = (ticker) => get(`/api/stock/${ticker}`, 180000)
// 次要面板（内部人/机构持仓/事件）懒加载——主分析先出，这些后补
export const fetchStockExtras = (ticker) => get(`/api/stock/${ticker}/extras`, 90000)
