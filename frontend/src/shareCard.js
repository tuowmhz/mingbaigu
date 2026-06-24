// 统一分享卡引擎：把结构化 spec 画成 1080×1440 专业竖图 PNG，并配好小红书/微信文案。
// 所有"卡片工厂"（市场体温/论点卡/产业链/个股）都复用它，保证视觉与品牌一致。
import { track } from './apiBase.js'

const W = 1080, H = 1440
const ACCENT = '#5ea0ff'
const TONE = { hot: '#ff5470', warn: '#ffb02e', ok: '#67c2a6', dim: '#8b96a8', cool: '#5ea0ff' }

// 预加载指向 mingbaigu.com 的真二维码（同源，不污染 canvas）；出图时画进卡底
const QR = typeof Image !== 'undefined' ? new Image() : null
if (QR) QR.src = '/qr-mingbaigu.png'

function wrapLines(ctx, text, maxW) {
  const lines = []
  for (const para of String(text).split('\n')) {
    let line = ''
    for (const ch of [...para]) {
      if (ctx.measureText(line + ch).width > maxW) { lines.push(line); line = ch }
      else line += ch
    }
    lines.push(line)
  }
  return lines
}

export function drawCard(spec) {
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H
  const ctx = cv.getContext('2d')
  const P = 92

  ctx.fillStyle = '#0d0e12'; ctx.fillRect(0, 0, W, H)
  ctx.strokeStyle = 'rgba(255,255,255,.08)'; ctx.lineWidth = 3
  ctx.beginPath(); ctx.roundRect(40, 40, W - 80, H - 80, 28); ctx.stroke()

  // 品牌条
  ctx.textAlign = 'left'
  ctx.fillStyle = ACCENT; ctx.beginPath(); ctx.arc(P + 9, 152, 10, 0, 7); ctx.fill()
  ctx.fillStyle = '#ECEDEF'; ctx.font = '500 40px sans-serif'; ctx.fillText('明白股', P + 34, 165)
  ctx.textAlign = 'right'; ctx.fillStyle = '#8b96a8'; ctx.font = '28px sans-serif'
  ctx.fillText(spec.column || '', W - P, 162); ctx.textAlign = 'left'
  ctx.strokeStyle = 'rgba(255,255,255,.08)'; ctx.lineWidth = 2
  ctx.beginPath(); ctx.moveTo(P, 208); ctx.lineTo(W - P, 208); ctx.stroke()

  let y = 320
  // 大标题（洞见）
  ctx.fillStyle = '#ffffff'; ctx.font = '600 78px sans-serif'
  for (const ln of wrapLines(ctx, spec.headline, W - 2 * P)) { ctx.fillText(ln, P, y); y += 94 }
  // 副标
  if (spec.subhead) {
    y += 8; ctx.fillStyle = '#aeb6c2'; ctx.font = '37px sans-serif'
    for (const ln of wrapLines(ctx, spec.subhead, W - 2 * P)) { ctx.fillText(ln, P, y); y += 50 }
  }

  // 数据可视：条形
  if (spec.viz?.type === 'bars') {
    y += 60
    const barX = P + 280, barW = W - P - barX - 130
    for (const it of spec.viz.items) {
      ctx.fillStyle = '#cdd5e0'; ctx.font = '33px sans-serif'; ctx.textAlign = 'left'
      ctx.fillText(it.label, P, y + 9)
      ctx.fillStyle = 'rgba(255,255,255,.09)'; ctx.beginPath(); ctx.roundRect(barX, y - 22, barW, 32, 16); ctx.fill()
      const w = Math.max(12, barW * Math.min(100, Math.max(0, it.value)) / 100)
      ctx.fillStyle = TONE[it.tone] || ACCENT; ctx.beginPath(); ctx.roundRect(barX, y - 22, w, 32, 16); ctx.fill()
      ctx.fillStyle = '#ECEDEF'; ctx.font = '500 32px sans-serif'; ctx.textAlign = 'right'
      ctx.fillText(String(it.value), W - P, y + 8); ctx.textAlign = 'left'
      y += 70
    }
    if (spec.viz.note) { ctx.fillStyle = '#6b7178'; ctx.font = '25px sans-serif'; ctx.fillText(spec.viz.note, P, y + 4); y += 30 }
  }

  // 人话解读面板
  if (spec.takeaway) {
    y += 50
    ctx.font = '38px sans-serif'
    const lines = wrapLines(ctx, spec.takeaway, W - 2 * P - 56)
    const ph = lines.length * 54 + 56
    ctx.fillStyle = 'rgba(94,160,255,.10)'; ctx.beginPath(); ctx.roundRect(P, y, W - 2 * P, ph, 18); ctx.fill()
    ctx.fillStyle = '#dbe3ef'; let ty = y + 56
    for (const ln of lines) { ctx.fillText(ln, P + 28, ty); ty += 54 }
    y += ph
  }

  // 可信度 chips
  if (spec.chips?.length) {
    y += 40; let cx = P
    ctx.font = '26px sans-serif'
    for (const c of spec.chips) {
      const tw = ctx.measureText(c).width + 38
      ctx.strokeStyle = 'rgba(255,255,255,.16)'; ctx.lineWidth = 2
      ctx.beginPath(); ctx.roundRect(cx, y, tw, 48, 24); ctx.stroke()
      ctx.fillStyle = '#9aa0a8'; ctx.fillText(c, cx + 19, y + 33)
      cx += tw + 14
    }
  }

  // 底部：品牌 + 钩子 + 二维码占位
  const fy = H - 150
  ctx.strokeStyle = 'rgba(255,255,255,.08)'; ctx.lineWidth = 2
  ctx.beginPath(); ctx.moveTo(P, fy - 30); ctx.lineTo(W - P, fy - 30); ctx.stroke()
  ctx.textAlign = 'left'
  ctx.fillStyle = '#ECEDEF'; ctx.font = '500 38px sans-serif'; ctx.fillText('mingbaigu.com', P, fy + 18)
  ctx.fillStyle = ACCENT; ctx.font = '30px sans-serif'; ctx.fillText(spec.cta || '三分钟看懂一只股票 / 一条产业链', P, fy + 64)
  const qx = W - P - 92, qy = fy - 8
  ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.roundRect(qx, qy, 92, 92, 12); ctx.fill()
  if (QR && QR.complete && QR.naturalWidth) {
    ctx.drawImage(QR, qx + 8, qy + 8, 76, 76)
  } else {
    ctx.fillStyle = '#6b7178'; ctx.font = '22px sans-serif'; ctx.textAlign = 'center'
    ctx.fillText('扫码', qx + 46, qy + 52); ctx.textAlign = 'left'
  }
  return cv
}

// 自动配文案：小红书标题/正文 + 微信一句话
export function cardCopy(spec) {
  const tags = (spec.tags || ['A股', '投资', '产业链']).map((t) => '#' + t).join(' ')
  return {
    xiaohongshu: `${spec.headline}\n\n${spec.subhead ? spec.subhead + '\n\n' : ''}${spec.takeaway || ''}\n\n用真实数据看懂，不喊单 · mingbaigu.com\n${tags}`,
    wechat: `${spec.headline}——${spec.takeaway || ''} mingbaigu.com`,
  }
}

function isMobile() {
  if (typeof navigator === 'undefined') return false
  return /iPhone|iPad|iPod|Android|HarmonyOS/i.test(navigator.userAgent) ||
    (typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(pointer: coarse)').matches)
}

// 手机端：把卡片图直接弹出来，提示「长按存到相册，再去小红书发布」。
// 小红书的分享扩展不收浏览器递过去的文件（会报“暂不支持该分享类型”），长按存图才是稳的链路。
function showSaveOverlay(imgUrl, copyText) {
  const ov = document.createElement('div')
  Object.assign(ov.style, {
    position: 'fixed', top: '0', left: '0', right: '0', bottom: '0', zIndex: '99999',
    background: 'rgba(8,9,12,.94)', backdropFilter: 'blur(4px)', WebkitBackdropFilter: 'blur(4px)',
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    overflowY: 'auto', padding: '16px 16px 28px', boxSizing: 'border-box',
  })

  const tip = document.createElement('div')
  tip.textContent = '长按图片 → 存储到照片，再去小红书发布'
  Object.assign(tip.style, { color: '#ECEDEF', font: '600 16px sans-serif', margin: '6px 0 12px', textAlign: 'center' })

  const img = document.createElement('img')
  img.src = imgUrl; img.alt = '明白股分享卡'
  Object.assign(img.style, {
    maxWidth: '86vw', maxHeight: '60vh', width: 'auto', borderRadius: '14px',
    boxShadow: '0 10px 40px rgba(0,0,0,.5)', display: 'block',
  })
  img.style.setProperty('-webkit-touch-callout', 'default')  // 确保 iOS 长按能弹「存储到照片」
  img.style.setProperty('-webkit-user-select', 'auto')

  const note = document.createElement('div')
  note.textContent = '文案已自动复制，发布时直接粘贴即可'
  Object.assign(note.style, { color: '#8b96a8', font: '13px sans-serif', margin: '14px 0 6px', textAlign: 'center', maxWidth: '86vw' })

  const box = document.createElement('div')
  box.textContent = copyText
  Object.assign(box.style, {
    whiteSpace: 'pre-wrap', color: '#cdd5e0', font: '13px sans-serif',
    background: 'rgba(255,255,255,.05)', border: '1px solid rgba(255,255,255,.1)',
    borderRadius: '10px', padding: '10px 12px', margin: '4px 0 12px',
    maxWidth: '86vw', maxHeight: '20vh', overflow: 'auto',
  })

  const row = document.createElement('div')
  Object.assign(row.style, { display: 'flex', gap: '10px' })
  const close = () => { ov.remove(); try { URL.revokeObjectURL(imgUrl) } catch {} }

  const copyBtn = document.createElement('button')
  copyBtn.textContent = '复制文案'
  Object.assign(copyBtn.style, {
    padding: '10px 22px', borderRadius: '999px', border: 'none',
    background: 'linear-gradient(90deg,#ffb02e,#ff8a3d)', color: '#1a1300',
    font: '600 14px sans-serif', cursor: 'pointer',
  })
  copyBtn.onclick = () => { try { navigator.clipboard.writeText(copyText) } catch {} ; copyBtn.textContent = '已复制 ✓' }

  const closeBtn = document.createElement('button')
  closeBtn.textContent = '完成'
  Object.assign(closeBtn.style, {
    padding: '10px 22px', borderRadius: '999px', border: '1px solid rgba(255,255,255,.2)',
    background: 'transparent', color: '#cdd5e0', font: '600 14px sans-serif', cursor: 'pointer',
  })
  closeBtn.onclick = close
  ov.addEventListener('click', (e) => { if (e.target === ov) close() })

  row.append(copyBtn, closeBtn)
  ov.append(tip, img, note, box, row)
  document.body.appendChild(ov)
}

// 出图 + 复制文案 + 分发：手机端弹「长按存图」浮层；桌面端走系统分享/下载。
export async function shareCard(spec) {
  track('share', 'card', { campaign: spec.column })
  const cv = drawCard(spec)
  const copy = cardCopy(spec)
  try { await navigator.clipboard.writeText(copy.xiaohongshu) } catch {}
  const blob = await new Promise((r) => cv.toBlob(r, 'image/png'))

  if (isMobile()) {
    showSaveOverlay(URL.createObjectURL(blob), copy.xiaohongshu)
    return
  }

  // 桌面端：保持原行为（系统分享优先，否则下载）
  const file = new File([blob], 'mingbaigu.png', { type: 'image/png' })
  if (navigator.canShare && navigator.canShare({ files: [file] })) {
    try { await navigator.share({ files: [file], title: spec.headline }); return } catch {}
  }
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob); a.download = 'mingbaigu-分享卡.png'; a.click()
  alert('竖图已保存，文案已复制——发小红书/微信都合适')
}
