// 把「叙事验证器」核验卡映射成 shareCard.js 认的 spec —— 复用统一竖图引擎，不重造。
// 源自 ThesisChecker/web/thesisShareSpec.js（share.py 的 JS 镜像）。
const STATUS_TONE = {
  '证实': 'ok', '部分证实': 'warn', '证伪': 'hot',
  '无法验证': 'dim', '预测(不可证伪)': 'cool', '观点': 'cool',
}
const STATUS_SCORE = {
  '证实': 100, '部分证实': 60, '证伪': 5, '无法验证': 30,
  '预测(不可证伪)': 45, '观点': 45,
}

export function narrativeShareSpec(card) {
  const verdicts = (card.verdicts || []).slice(0, 4) // ≤4 条，避免顶到卡底
  const items = verdicts.map((v) => ({
    label: `${v.type || ''}·${v.status || ''}`.replace(/^·|·$/g, '').slice(0, 10),
    value: STATUS_SCORE[v.status] ?? 40,
    tone: STATUS_TONE[v.status] || 'dim',
  }))

  const facts = (card.verdicts || []).filter((v) => v.type === '事实')
  const nCheck = facts.filter((v) => ['证实', '部分证实', '证伪'].includes(v.status)).length
  const note = `${facts.length} 条事实主张，${nCheck} 条可被公开数据核验`

  const val = card.valuation_priced_in || {}
  const takeaway = (card.falsification || val.read || card.core_thesis || '').slice(0, 90)

  const title = card.name || card.ticker || ''
  const chips = ['真实财报核验']
  if (card.as_of) chips.push(`数据截止 ${card.as_of}`)
  chips.push(card.supply_chain_grounded ? '产业链接地' : '不喊单·只核叙事')

  return {
    column: '叙事验证器',
    headline: card.headline || card.summary || '',
    subhead: `${title}｜原叙事：${card.summary || ''}`.slice(0, 26),
    viz: items.length ? { type: 'bars', items, note } : null,
    takeaway,
    chips: chips.slice(0, 3),
    cta: '一条荐股观点，先过一遍公开数据',
    tags: ['A股', '投资', '叙事验证', '不喊单'],
  }
}
