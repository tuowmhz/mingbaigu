import './apiBase.js' // 必须最先执行：App 壳环境把 /api 改写到线上后端
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './styles.css'

// 字号偏好：渲染前应用，避免闪动
document.body.dataset.scale = localStorage.getItem('sp_scale') || '1'

// 全局：给所有 /api 请求自动带上登录令牌（个人功能用；分析内容无需登录）
const _fetch = window.fetch.bind(window)
window.fetch = (url, opts = {}) => {
  const token = localStorage.getItem('sp_token')
  if (token && typeof url === 'string' && url.startsWith('/api')) {
    opts.headers = { ...(opts.headers || {}), Authorization: `Bearer ${token}` }
  }
  return _fetch(url, opts)
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
