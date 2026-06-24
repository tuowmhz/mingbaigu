import { useEffect, useState } from 'react'
import { ResearchReport } from './ChainView.jsx'

async function fetchRetry(url, tries = 3) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(20000) })
      if (r.ok) return r.json()
    } catch {}
    await new Promise((res) => setTimeout(res, 2000))
  }
  return null
}

const TIGHT = {
  tight: { label: '卡脖子', cls: 'bearish' },
  medium: { label: '有壁垒', cls: 'neutral' },
  loose: { label: '充分竞争', cls: '' },
}
const STAGE = { 下游: 'st-down', 中游: 'st-mid', 上游: 'st-up' }
const TIER = {
  龙头: { t: '龙头', c: 'var(--up)' }, 第二梯队: { t: '第二梯队', c: 'var(--accent)' },
  新进入: { t: '新进入', c: 'var(--neutral)' }, 隐藏受益: { t: '隐藏受益', c: 'var(--accent2)' },
}

function Players({ players, onOpenStock }) {
  return (
    <div className="sector-players">
      {players.map((p, i) => {
        const tier = TIER[p.tier]
        const chip = (
          <>{p.name}{p.ticker && <b> {p.ticker}</b>}
            {tier && <span className="tier-tag" style={{ color: tier.c }}>{tier.t}</span>}</>
        )
        return p.ticker
          ? <span className="company-chip" key={i} title={`${p.name} · ${p.role}`}
              onClick={() => onOpenStock && onOpenStock(p.ticker)}>{chip}</span>
          : <span className="company-chip muted" key={i} title={p.role}>{chip}</span>
      })}
    </div>
  )
}

function Layer({ l, onOpenStock }) {
  const t = TIGHT[l.tightness] || TIGHT.medium
  const tight = l.tightness === 'tight'
  const deep = !!l.profit_model
  return (
    <div className={`sector-layer ${tight ? 'tight' : ''}`}>
      <div className="sector-layer-head">
        <span className="sector-layer-name">
          {l.stage && <span className={`stage-tag ${STAGE[l.stage] || ''}`}>{l.stage}</span>}
          {l.layer}
        </span>
        <span className={`badge ${t.cls}`}>{t.label}</span>
      </div>
      <div className="judge-notes" style={{ margin: '4px 0' }}>{cleanObservationText(l.desc)}</div>
      {deep && (
        <div className="sector-meta">
          <span>{cleanObservationText(l.profit_model)}</span>
          <span>毛利 <b className={l.margin === '高' ? 'up' : l.margin === '低' ? 'down' : ''}>{l.margin}</b></span>
          <span>资本开支 <b>{l.capex}</b></span>
          <span>规模效应 <b>{l.scale}</b></span>
        </div>
      )}
      {deep && l.moat && <div className="sector-moat">护城河：{cleanObservationText(l.moat)}</div>}
      {l.chokepoint && <div className="sector-choke">卡点：{cleanObservationText(l.chokepoint)}</div>}
      <Players players={l.players} onOpenStock={onOpenStock} />
    </div>
  )
}

function Cell({ k, v }) {
  return <div className="iv-cell"><div className="iv-k">{k}</div><div className="iv-v">{cleanObservationText(v)}</div></div>
}

function cleanObservationText(x) {
  return typeof x === 'string'
    ? x
      .replaceAll('证据链', '溯源链')
      .replaceAll('反方证据', '反方观察')
      .replaceAll('硬证据', '硬观察')
      .replaceAll('证据', '观察')
    : x
}

function cleanReportCopy(x) {
  if (typeof x === 'string') return cleanObservationText(x)
  if (Array.isArray(x)) return x.map(cleanReportCopy)
  if (x && typeof x === 'object') {
    return Object.fromEntries(Object.entries(x).map(([k, v]) => [k, cleanReportCopy(v)]))
  }
  return x
}

const tightLabel = { tight: '强', medium: '中', loose: '弱' }
const marginFallback = { tight: '高', medium: '中', loose: '低' }

function names(xs) {
  return xs?.filter(Boolean).join(' / ') || '待验证'
}

function shortText(x, n = 72) {
  if (!x) return ''
  const s = String(x).replace(/\s+/g, ' ').trim()
  return s.length > n ? `${s.slice(0, n)}…` : s
}

function shortLabel(x) {
  if (!x) return ''
  let s = String(x)
  for (const sep of ['：', ':', '(', '（', '，', ',', '——', ' - ', '—']) {
    s = s.split(sep)[0]
  }
  return shortText(s, 22)
}

function layerPlayers(l) {
  return (l.players || []).map((p) => p.ticker ? `${p.name}(${p.ticker})` : p.name).filter(Boolean)
}

function topLayers(s, n = 5) {
  return [...(s.layers || [])]
    .sort((a, b) => (a.tightness === 'tight' ? -1 : 1) - (b.tightness === 'tight' ? -1 : 1))
    .slice(0, n)
}

function groupLayers(layers) {
  const out = {}
  for (const l of layers || []) {
    const k = l.stage || '关键环节'
    out[k] = [...(out[k] || []), l.layer]
  }
  return Object.entries(out).map(([driver, items]) => ({ driver, items }))
}

function matchLayer(label, layers) {
  const s = shortLabel(label)
  return (layers || []).find((l) => s && (label.includes(l.layer) || l.layer.includes(s) || s.includes(l.layer)))
    || (layers || []).find((l) => l.tightness === 'tight')
    || (layers || [])[0]
}

const SECTOR_MEMOS = {
  ai_datacenter: {
    facts: [
      'AI 数据中心需求仍由云厂资本开支驱动，但建设节奏越来越受电力、变压器、燃机和并网队列约束。',
      '芯片设计不是唯一瓶颈；HBM、CoWoS 和电力供给共同决定英伟达、云厂和 Neocloud 的真实交付上限。',
      '利润池集中在 GPU/XPU、HBM、先进封装、互联和电力设备，服务器整机更像薄利的系统集成。',
      '领先指标不是股价，而是云厂 capex 指引、HBM 预订/价格、CoWoS 月产能、变压器/燃机交期和推理 token 收入。',
    ],
    opportunities: [
      { name: '电力接入权变成新晶圆配额', why: '算力项目拿到 GPU 只是第一步，能否在 24-48 个月内拿到可调度电力和变压器交付，开始决定机房真实投产。', mispricing: '市场仍把电力当配套工程定价，但它正在变成决定算力交付节奏的主约束。', alpha: '超额收益来自 backlog 价格重估、交付周期拉长和客户愿意为确定并网支付溢价。' },
      { name: 'HBM4 代际切换的席位费', why: 'Rubin/下一代 ASIC 对 HBM4 的需求把存储从周期品推向认证品，领先厂的客户锁定比 DRAM 景气更重要。', mispricing: '市场容易用普通存储周期看 HBM，低估认证、良率和预订制对毛利的保护。', alpha: '超额收益来自份额上移、单价提升和普通 DRAM 被 HBM 挤占后的全市场价格弹性。' },
      { name: 'CoWoS-L 良率就是出货闸门', why: '更大封装、更高 HBM 层数和先进制程叠加，使先进封装比前道制程更接近短期瓶颈。', mispricing: '投资者常说台积电是代工龙头，却没有单独给先进封装瓶颈足够估值。', alpha: '超额收益来自产能预订、封装 ASP 上行和设备/材料的伴随扩产订单。' },
      { name: '1.6T 互联从配件变成集群性能变量', why: '大集群性能不只看单卡，光模块、交换芯片、铜连接和低延迟网络决定 GPU 利用率。', mispricing: '市场把光模块当电子零件周期股，忽视它对训练集群有效算力的杠杆。', alpha: '超额收益来自高速代际切换、客户认证黏性和英伟达生态锁供。' },
      { name: 'Neocloud 的信用利差交易', why: 'GPU 云的收入很像长约租赁，风险却像高杠杆重资产；订单质量和融资成本决定股权价值。', mispricing: '市场容易只看 backlog 数字，忽视客户集中、残值、再融资和电力交付风险。', alpha: '超额收益来自区分真长约与脆弱 backlog，做多资产负债表更强的供给方。' },
    ],
  },
  solar: {
    facts: [
      '全球光伏新增装机仍在高位增长，2024 年新增约 597GW，2025 年主流预测继续上行至 600GW 以上。',
      '终端需求真，但硅料、硅片、电池片、组件主链产能过剩，价格战把制造利润打到极薄甚至亏损。',
      '更有定价权的是高纯石英砂、银浆、逆变器/储能、美国本土薄膜组件等少数卡点或政策壁垒环节。',
      '领先指标应看硅料/组件周度报价、开工率、库存、银价、美国关税/FEOC 落地和并网装机，而不是只看新增 GW。',
    ],
    opportunities: [
      { name: '高纯石英砂和银浆的抽租权', why: '组件降价不会消灭坩埚砂和银浆需求，反而在产能出清期让耗材卡点更容易保价。', mispricing: '市场把光伏全链当同质制造，漏掉少数不可快速扩产的材料瓶颈。', alpha: '超额收益来自材料短缺、配方迭代和客户验证周期带来的毛利稳定性。' },
      { name: '美国本土薄膜的政策价差', why: 'First Solar 这类非硅基、本土化、可规避部分贸易摩擦的供给，享受需求和政策双重稀缺。', mispricing: '市场用中国组件价格给全球组件定价，低估美国本土供应链的隔离溢价。', alpha: '超额收益来自长约 ASP、税收抵免和进口限制带来的区域利润池。' },
      { name: '逆变器从硬件变成电站操作系统', why: '光储一体化后，逆变器承担并网、调度、储能管理和运维数据，粘性高于组件。', mispricing: '投资者常把逆变器看成 BOM 成本项，而不是电站收益率的控制节点。', alpha: '超额收益来自软件服务、渠道品牌和储能 attach rate 上升。' },
      { name: '反内卷不是普涨，而是出清交易', why: '政策与亏损会逼低效产能退出，但真正受益的是现金成本低、负债低、客户强的少数龙头。', mispricing: '市场容易把减产口号直接当利润修复，忽视产能债务和库存消化。', alpha: '超额收益来自低成本产能在行业底部抢份额，而不是全链估值修复。' },
      { name: '光储并网约束倒逼系统价值', why: '高渗透率地区的新增装机越来越受电网消纳限制，储能、功率预测和并网能力变成项目收益差异。', mispricing: '市场只看组件价格下降，低估电网接入和调度能力对项目 IRR 的影响。', alpha: '超额收益来自项目级系统方案、储能配置率和海外高毛利市场渗透。' },
    ],
  },
  nuclear: {
    facts: [
      '核能新增需求由 AI 数据中心基荷电力、脱碳和能源安全共同驱动，但新建堆兑现慢于市场叙事。',
      '燃料循环比反应堆设计更紧，铀转化、SWU 浓缩、HALEU 和核级锻件是更现实的瓶颈。',
      '存量核电运营商拥有稀缺可调度清洁电力，长协 PPA 重定价比 SMR 远期故事更快进入现金流。',
      '领先指标包括 UF6 转化费、SWU 价格、铀长协、HALEU 产量、核电 PPA 和西方扩产进度。',
    ],
    opportunities: [
      { name: 'UF6 转化费的隐形弹性', why: '转化产能比铀矿更窄，核燃料需求一旦转向西方体系，价格弹性会先在转化费体现。', mispricing: '市场盯铀矿现货，却低估燃料循环中更窄、更少玩家的转化环节。', alpha: '超额收益来自转化费上行、长协重签和西方供应链重建。' },
      { name: 'SWU/HALEU 的国家安全溢价', why: '先进堆离不开更高丰度燃料，西方 HALEU 商业供给不足使浓缩从周期品变成战略资产。', mispricing: '市场把 SMR 当设备股定价，却没有把“有堆无料”的约束反映到燃料商。', alpha: '超额收益来自政府订单、价格地板、长期 offtake 和产能许可价值。' },
      { name: '大型核级锻件的物理垄断', why: '反应堆压力容器等大锻件不能靠资本快速复制，认证、设备和经验同时稀缺。', mispricing: '投资者容易忽视没有上市代码的链底环节，因此低估设备交期对核电建设的约束。', alpha: '超额收益来自相关设备商 backlog 延长、预付款和核级认证稀缺性。' },
      { name: '存量核电 PPA 重估', why: '数据中心需要 24/7 清洁电力，存量核电资产从公用事业资产变成稀缺电力期权。', mispricing: '市场仍用传统电力估值看核电，低估长协价格和负荷因子的上行空间。', alpha: '超额收益来自 PPA 价格、容量市场和再许可延寿带来的现金流重估。' },
      { name: 'SMR 服务链优于纯堆型押注', why: 'SMR 商运慢，但许可、燃料、工程、核组件和安全系统会先获得研发和示范订单。', mispricing: '市场把涨幅给了堆型概念股，低估卖组件、燃料和工程验证的低二元风险路径。', alpha: '超额收益来自阶段性里程碑，而不是押注某一堆型最终胜出。' },
    ],
  },
  ev: {
    facts: [
      '全球电动车销量继续增长，但区域分化明显，中国份额和价格战强度远高于美国与欧洲。',
      '整车环节竞争最激烈，利润池更多在电池系统、隔膜、稀土磁材和部分车规功率半导体。',
      '锂价低位有利于电芯龙头毛利修复，但对上游资源是周期压力；不要把整条链同向交易。',
      '领先指标包括动力电池装机份额、碳酸锂价格、整车单车毛利、稀土出口许可和 SiC 产能利用率。',
    ],
    opportunities: [
      { name: '电池系统龙头的规模反击', why: '价格战后整车厂更依赖低成本、高安全、全球认证的电芯和 Pack 供应，份额会继续向头部集中。', mispricing: '市场把电池看成随锂价下行的周期品，低估系统集成和客户认证的结构性壁垒。', alpha: '超额收益来自份额提升、单位成本下降和海外储能/动力双市场复用。' },
      { name: '湿法隔膜的薄但硬护城河', why: '隔膜在 BOM 中不起眼，但良率、设备、涂覆和客户认证决定安全边界，龙头更容易维持毛利。', mispricing: '投资者喜欢讨论正极路线，却忽视隔膜是少数还能保留加工费的材料环节。', alpha: '超额收益来自高端产能、海外认证和行业出清后的加工费修复。' },
      { name: '稀土磁材的地缘期权', why: '电机效率依赖 NdFeB 和重稀土添加，出口许可或地缘摩擦会迅速改变整车供应链安全溢价。', mispricing: '市场常把它当资源小周期，低估磁材加工集中度对整车生产的横向影响。', alpha: '超额收益来自库存重建、非中国供应链溢价和价格弹性。' },
      { name: 'SiC 的问题不是技术，而是产能纪律', why: 'SiC 对高压平台有价值，但过快扩产会把技术优势变成价格压力。', mispricing: '市场把“车规 SiC 渗透率上升”直接等同于供应商利润上升。', alpha: '超额收益来自挑选良率、长约和利用率更稳的玩家，而不是无差别买扩产。' },
      { name: '垂直整合整车厂的现金成本优势', why: '价格战不会消失，能穿越周期的是电池、自研电驱、供应链金融和出口渠道更强的整车厂。', mispricing: '市场容易用交付量排名代替盈利质量，忽视单车现金毛利和库存周转。', alpha: '超额收益来自低成本平台在出清期继续抢份额。' },
    ],
  },
  humanoid: {
    facts: [
      '人形机器人仍处早期量产前夜，市场规模预测跨度大，真实锚点应是月产量、BOM 下降和工厂试用留存。',
      '整机不一定最赚钱，线性关节里的行星滚柱丝杠、减速器、力/扭矩传感器和稀土磁材更接近卡点。',
      '头部整机厂掌握架构定义权，但关键零件的良率和认证周期决定量产速度。',
      '领先指标包括特斯拉/Figure/宇树产量、丝杠良率、单机 BOM、供应商定点公告和稀土出口节奏。',
    ],
    opportunities: [
      { name: '行星滚柱丝杠良率交易', why: '量产机器人需要大量高精度线性执行件，真正难的是百万级一致性和寿命，不是样品。', mispricing: '市场把丝杠当机械件，低估良率爬坡对整机成本曲线的支配力。', alpha: '超额收益来自定点确认、良率突破和单机用量乘数。' },
      { name: 'Tier-0.5 关节模组锁定整机厂', why: '整机厂倾向把电机、传感器、减速器和控制器封装成可复制模块，模组厂会吃掉部分系统集成利润。', mispricing: '市场只追零部件单点，却低估能交付完整关节的供应商粘性。', alpha: '超额收益来自联合开发、工艺 know-how 和后续平台复用。' },
      { name: '六维力传感器从可选变必选', why: '机器人要进入柔性装配和安全协作，力反馈会从展示功能变成可靠性底座。', mispricing: '投资者容易把传感器看作小 BOM，忽视它决定任务成功率和安全认证。', alpha: '超额收益来自单机用量提升、国产替代和高端标定能力。' },
      { name: '稀土磁材卡住关节功率密度', why: '高扭矩密度电机离不开高性能磁材，出口许可和重稀土价格会直接影响整机 BOM。', mispricing: '市场把机器人只当 AI 应用，低估材料地缘约束。', alpha: '超额收益来自磁材价格弹性、库存周期和非受限供应链溢价。' },
      { name: '仿真平台和边缘算力是量产前收费点', why: '机器人还没大规模卖出前，训练、仿真、边缘推理和开发工具已经先收钱。', mispricing: '市场把英伟达在人形里的价值简单理解成卖芯片，低估平台锁定开发者的力量。', alpha: '超额收益来自工具链标准化、模型生态和边缘算力 attach。' },
    ],
  },
  ai_health: {
    facts: [
      'AI 医疗不是单一行业，临床文书、影像诊断、基因检测、AI 制药和手术机器人现金流质量差异很大。',
      '最先兑现 ROI 的是减少医生时间成本、提升诊断效率和绑定医院流程的数据产品。',
      'AI 制药期权很大，但获批、临床终点和研发资本化仍是最大不确定性。',
      '领先指标包括 CPT/医保覆盖、EHR 集成、检测量、药物临床读出、数据授权收入和 FDA 审批。',
    ],
    opportunities: [
      { name: '环境文书的短 ROI SaaS', why: '医生时间成本和医院行政负担是明确痛点，文书 AI 不需要等待新药审批就能收费。', mispricing: '市场爱讲 AI 制药星辰大海，却低估最朴素的节省工时生意。', alpha: '超额收益来自 EHR 集成、续费率、医生使用频次和科室扩张。' },
      { name: '基因数据飞轮的复利', why: '测序、病理、临床结局和治疗数据一旦闭环，模型和诊断产品会互相强化。', mispricing: '投资者只看单次检测收入，低估数据授权和伴随诊断的长期利润池。', alpha: '超额收益来自检测量增长、MRD 渗透和药企数据合作。' },
      { name: 'AI 影像从算法卖点转向报销代码', why: '影像 AI 的关键不是模型准确率展示，而是能否进入工作流并拿到支付。', mispricing: '市场常把 FDA clearance 当商业化完成，忽视医保、责任和采购预算。', alpha: '超额收益来自 CPT 覆盖、医院采购转化和真实世界效果验证。' },
      { name: '制药模型卖铲人优于单药押注', why: '平台、算力、数据和实验自动化可以服务多家药企，风险低于押某个候选药。', mispricing: '市场喜欢二元化临床事件，低估工具链供应商的组合收入。', alpha: '超额收益来自药企采用数、里程碑付款和模型-实验闭环效率。' },
      { name: '手术机器人数据闭环', why: '机器人手术量越高，器械耗材、软件和术式数据越容易形成复购与学习曲线。', mispricing: '市场把手术机器人看成设备销售，低估耗材和数据工作流的长期性。', alpha: '超额收益来自装机、单机手术量和耗材 attach rate。' },
    ],
  },
  quantum: {
    facts: [
      '量子计算距离广泛商用仍早，近期更像政府资金、路线图和工程里程碑驱动的长久期期权。',
      '真正瓶颈常在稀释制冷机、氦-3、控制读出电子学和纠错，而不是只在量子比特数量。',
      'Pure-play 公司估值弹性大但营收小、烧钱快，供应链卖铲人风险收益更清晰。',
      '领先指标包括逻辑比特、逻辑错误率、制冷机交期、氦-3价格、政府拨款和现金跑道。',
    ],
    opportunities: [
      { name: '稀释制冷机订单比量子股更诚实', why: '超导路线扩张必须先买低温系统，交期和 backlog 是硬件扩产的真实温度计。', mispricing: '市场追逐量子比特发布会，却很少给底层低温设备足够关注。', alpha: '超额收益来自寡头交付能力、服务收入和政府实验室采购。' },
      { name: '氦-3 是小市场大约束', why: '氦-3 供给不随需求快速扩张，任何超导量子扩产都需要面对工质约束。', mispricing: '市场嫌它市场小，却低估小材料对大路线的闸门作用。', alpha: '超额收益来自锁货合同、替代技术进展和价格波动。' },
      { name: '控制电子学从线缆瓶颈升级', why: '比特规模上去后，每比特布线、读出和低温控制会成为系统复杂度核心。', mispricing: '投资者用芯片思维看量子，忽视测控系统在总成本中的上升。', alpha: '超额收益来自低温电子学、模块化控制和测试仪器升级。' },
      { name: '纠错软件/IP 的非硬件杠杆', why: '可用量子计算的核心是逻辑比特和纠错栈，软件 IP 可能跨硬件路线复用。', mispricing: '市场过度争论硬件路线胜负，低估纠错和编译层的横向价值。', alpha: '超额收益来自授权、云平台集成和跨路线适配。' },
      { name: '政府采购里程碑替代营收叙事', why: '近期现金流更多来自国家项目、实验室和国防科研，而不是企业应用大规模付费。', mispricing: '市场把远期 TAM 贴现得太快，没有区分拨款兑现和商业收入。', alpha: '超额收益来自订单节点、合作路线图和现金跑道改善。' },
    ],
  },
  space: {
    facts: [
      '全球太空经济已是数千亿美元级，但商业利润高度集中在发射、卫星宽带、军用采购和少数空间级部件。',
      'SpaceX 在发射成本与频次上拥有压倒性控制权，其他玩家的机会更多在补位和非 SpaceX 可采购需求。',
      '空间级电子、抗辐照器件、TWTA、空间级太阳能电池和锗等上游卡点更容易被忽视。',
      '领先指标包括 SpaceX 发射次数、Starship 进展、军用星座合同、锗/镓管制、星座部署数和发射 slot。',
    ],
    opportunities: [
      { name: '发射成本基准的第二供给', why: 'SpaceX 近乎定义全链成本，但政府和商业客户仍需要可用的第二来源。', mispricing: '市场要么只买 SpaceX 影子，要么把所有火箭公司同等看待。', alpha: '超额收益来自可靠发射记录、政府合同和垂直整合制造能力。' },
      { name: '抗辐照电子的认证黏性', why: '空间电子不是普通芯片替换，认证、可靠性和军用合规构成高切换成本。', mispricing: '投资者容易认为卫星零部件会被大规模商用器件降维替代。', alpha: '超额收益来自认证周期、军用采购和长寿命项目锁定。' },
      { name: '空间太阳能电池和锗的双重卡点', why: '卫星电源依赖高效空间级太阳能电池，而锗等材料又存在地缘供应风险。', mispricing: '市场讲星座数量，却低估每颗星都绕不开的电源材料约束。', alpha: '超额收益来自材料价格、合规供应链和星座扩张。' },
      { name: 'SDA/Golden Dome 的快速采购链', why: '国防星座需要更短迭代和更高数量，带动总线、载荷、光通信和地面系统。', mispricing: '市场把军用空间当传统大项目，低估快速批量采购对中小供应商的拉动。', alpha: '超额收益来自合同公告、交付节奏和供应商资格扩散。' },
      { name: '星间光通信从概念到标配', why: '低轨星座要提高吞吐和降低地面站依赖，星间链路会成为高价值载荷。', mispricing: '市场只看卫星数量，忽视每星载荷价值结构升级。', alpha: '超额收益来自星座代际升级、单位卫星 ASP 和国防通信需求。' },
    ],
  },
  battery: {
    facts: [
      '储能年度新增已跨过百 GW 量级，增长从补贴项目转向电网调峰、工商业和 AI 数据中心备电。',
      '电池包价格继续下行，终端需求扩张但中游材料和部分电芯产能仍过剩。',
      '利润池在电芯龙头、海外储能系统集成、认证渠道、EMS 软件和部分资源/精炼周期拐点。',
      '领先指标包括储能招标 GWh、314/500Ah 电芯价格、碳酸锂、产能利用率、美国并网和数据中心订单。',
    ],
    opportunities: [
      { name: '储能系统从低价 EPC 转向可融资资产', why: '客户买的不只是电池，而是可并网、可质保、可融资、可调度的系统。', mispricing: '市场用电芯价格下跌推导系统利润下跌，忽视集成、质保和项目融资能力。', alpha: '超额收益来自海外渠道、认证、运维和软件 attach。' },
      { name: 'LFP 电芯出清后的头部修复', why: '价格战淘汰高成本产能后，低成本龙头在储能和动力两端能获得更高利用率。', mispricing: '市场看到过剩就回避全行业，忽视龙头成本曲线的反周期份额收益。', alpha: '超额收益来自排产回升、单位成本下降和海外高价订单。' },
      { name: '锂/精炼周期的右侧确认', why: '锂价低位压制资源商，但供给收缩叠加需求增长会先反映在库存和现货价。', mispricing: '市场常过早交易资源反转，忽视库存和高成本矿退出节奏。', alpha: '超额收益来自价格右侧、长协重定价和资源税/配额扰动。' },
      { name: 'EMS 软件吃掉调度利润', why: '高渗透新能源环境中，储能收益越来越依赖实时调度、套利和辅助服务算法。', mispricing: '市场把储能当硬件集装箱，低估软件对项目 IRR 的贡献。', alpha: '超额收益来自运维合同、调度分成和资产组合数据。' },
      { name: '非锂路线的窄场景突破', why: '钠电、液流等路线未必颠覆锂电，但可能在长时、低温、安全或低成本场景获得份额。', mispricing: '市场喜欢二选一叙事，实际更可能是按应用场景分层替代。', alpha: '超额收益来自首批商业订单、成本曲线和安全/寿命验证。' },
    ],
  },
  semicap: {
    facts: [
      '半导体设备进入 AI/HBM 与先进制程共振周期，但设备订单滞后且下行时弹性也更大。',
      'EUV/High-NA、过程控制量测、刻蚀沉积和先进封装/测试是利润最集中的环节。',
      '中国国产替代是真需求，但高端光刻、量测和关键子系统仍是最难突破位置。',
      '领先指标包括 ASML backlog、设备 book-to-bill、台积电/存储 capex、HBM 价格和出口管制变化。',
    ],
    opportunities: [
      { name: 'EUV/High-NA 插槽稀缺', why: '先进制程扩产不只看晶圆厂预算，EUV 交付和高 NA 导入节奏决定实际产能。', mispricing: '市场把 ASML 当成熟设备股，低估它在 AI 芯片扩产中的期权属性。', alpha: '超额收益来自订单能见度、ASP 上行和服务收入。' },
      { name: '过程控制是先进制程税', why: '制程越复杂、良率越难，量测检测占比越高，KLA 类公司像收良率保险费。', mispricing: '投资者更容易看见光刻机，忽视过程控制对良率 ramp 的必要性。', alpha: '超额收益来自准垄断份额、先进节点强度和存储高层数升级。' },
      { name: '先进封装/测试设备的后道升级', why: 'AI 芯片性能越来越依赖封装，测试、键合、切割和热管理设备跟随复杂度提升。', mispricing: '市场还把后道设备当低端周期，忽视 HBM/Chiplet 带来的结构升级。', alpha: '超额收益来自 A&P 设备订单、测试时间拉长和封装良率压力。' },
      { name: '国产替代只买真瓶颈', why: '政策需求会带来订单，但只有能进入关键工艺、客户验证和良率考核的设备商能沉淀利润。', mispricing: '市场把所有国产设备同等定价，忽视低端重复扩产和价格战。', alpha: '超额收益来自产品线突破、先进制程验证和进口替代边界清晰。' },
      { name: 'HBM WFE 周期的存储设备弹性', why: 'HBM 挤占 DRAM 晶圆并提升工艺复杂度，带动沉积、刻蚀、测试等设备强度。', mispricing: '市场用传统存储周期看设备，低估 HBM 对设备强度的结构拉动。', alpha: '超额收益来自存储 capex 上修、HBM 供不应求和良率设备需求。' },
    ],
  },
  grid: {
    facts: [
      '电网需求来自新能源并网、负荷增长、AI 数据中心和老旧资产更新的叠加。',
      '最紧的不是发电装机口号，而是大电力变压器、HVDC 控制保护、取向硅钢和高压测试能力。',
      '交期拉长让设备商 backlog 质量提升，但长周期订单也带来成本通胀和执行风险。',
      '领先指标包括变压器交期、GOES 价格、HVDC 招标、数据中心实际并网容量和设备商 book-to-bill。',
    ],
    opportunities: [
      { name: '大电力变压器的订单再定价', why: '高压变压器扩产慢、测试能力稀缺，客户愿意为确定交付支付溢价。', mispricing: '市场把它当传统电力设备，低估交期延长后的定价权。', alpha: '超额收益来自 backlog 毛利改善、预付款和产能利用率。' },
      { name: 'GOES 是整条链的钢铁瓶颈', why: '取向硅钢决定变压器效率和产能上限，扩产周期长且高牌号供应集中。', mispricing: '投资者关注整机订单，却忽视材料端可能限制出货。', alpha: '超额收益来自高牌号价差、供应合同和变压器产能释放。' },
      { name: 'HVDC 心脏和大脑', why: '长距离输电、海风外送和跨区调度都需要换流阀与控制保护系统，玩家集中。', mispricing: '市场把特高压看成工程量，低估核心控制系统的利润密度。', alpha: '超额收益来自项目核准、系统包份额和软件/服务收入。' },
      { name: '数据中心并网队列去伪存真', why: '申请队列不等于真实负荷，能落地的项目需要电力合同、变压器和许可同时到位。', mispricing: '市场容易把全部互联申请当确定需求。', alpha: '超额收益来自识别真实通电 GW 对设备订单的拉动。' },
      { name: '电网工程服务的瓶颈价值', why: '电力设备需要施工、设计、许可和运维，工程能力在负荷扩张期变得稀缺。', mispricing: '市场更爱硬件厂，低估工程服务公司的 backlog 和现金流。', alpha: '超额收益来自项目执行、劳动力稀缺和维护合同。' },
    ],
  },
  defense: {
    facts: [
      '军工需求由库存补充、欧洲再武装、导弹防御、无人系统和大国竞争驱动，预算确定性高但交付受供给约束。',
      '最卡的常不是主机厂，而是固体火箭发动机、含能材料、高氯酸铵、稀土磁材和特种电子。',
      'Prime 拥有项目入口，但小材料/子系统供应商在扩产期可能获得更高边际弹性。',
      '领先指标包括多年度采购、导弹月产量、SRM 交期、DPA/OSC 投资、稀土出口和关键产线投产。',
    ],
    opportunities: [
      { name: 'SRM 第三源爬坡', why: '导弹扩产被固体火箭发动机限制，第三来源是否真正上量决定产能弹性。', mispricing: '市场盯导弹主承包商订单，忽视发动机供应链才是交付瓶颈。', alpha: '超额收益来自产线认证、月产提升和长期采购锁定。' },
      { name: '含能材料的单点脆弱性', why: '高氯酸铵和炸药等化学品产能少、监管重、事故风险高，是弹药链最深约束。', mispricing: '这些资产不性感，市场通常不给军工估值，但它们决定交付。', alpha: '超额收益来自国家资金、价格地板和供应安全溢价。' },
      { name: '稀土磁材重建的政策套利', why: '制导、雷达、电机和无人系统都依赖磁材，美国中游重建需要资本和长期合同。', mispricing: '市场把稀土当资源交易，低估中游分离、金属和磁体的国家安全价值。', alpha: '超额收益来自政府入股、offtake 和非中国供应链溢价。' },
      { name: '弹药补库的多年度采购', why: '库存消耗后，客户更愿意签多年合同来换取产能扩张。', mispricing: '市场按年度预算看军工，低估多年采购对投资回收风险的降低。', alpha: '超额收益来自 book-to-bill、backlog 久期和固定成本吸收。' },
      { name: '可消耗无人系统绕开传统平台周期', why: '乌克兰战场证明低成本无人系统消耗快、迭代快，采购逻辑不同于昂贵平台。', mispricing: '市场仍把军工看成少数大型平台，忽视低成本可消耗品的量变。', alpha: '超额收益来自批量订单、软件升级和供应链快速迭代。' },
    ],
  },
  cyber: {
    facts: [
      '网络安全需求不是可选 IT 支出，勒索、身份攻击、云迁移和 AI 攻击面扩大持续抬高底线预算。',
      '平台化趋势真实，但不是所有单点都会消失；身份、PAM、威胁情报和遥测数据更接近控制权。',
      '利润池在高毛利 SaaS、数据飞轮和高切换成本模块，硬件/低差异服务更容易被压价。',
      '领先指标包括 ARR、RPO/cRPO、NRR、百万美元客户数、模块加购率、FCF margin 和重大安全事件。',
    ],
    opportunities: [
      { name: '身份/PAM 成为零信任总闸门', why: '攻击越来越多从身份和权限进入，PAM/IGA/身份治理直接控制企业风险边界。', mispricing: '市场把安全平台化理解为端点一家独大，忽视身份层的不可替代性。', alpha: '超额收益来自切换成本、并购溢价和模块扩展。' },
      { name: '威胁情报原始数据税', why: '检测能力上限取决于遥测覆盖和攻击者情报，数据越独占，模型越难复制。', mispricing: '投资者看功能列表，却低估数据源和响应闭环。', alpha: '超额收益来自数据网络效应、平台加购和事件驱动需求。' },
      { name: 'XDR/SIEM 整合的预算迁移', why: '客户想减少控制台和告警噪音，平台型厂商会吸收端点、日志、云和身份预算。', mispricing: '市场用单品份额看厂商，忽视预算从工具堆向平台迁移。', alpha: '超额收益来自 NRR、模块数和大客户 ACV 扩张。' },
      { name: 'CNAPP 与 AI 代码安全合流', why: '云原生和 AI 生成代码增加配置、依赖和身份风险，安全左移变成刚需。', mispricing: '市场把云安全当增速放缓的 SaaS，低估 AI 代码带来的新攻击面。', alpha: '超额收益来自开发者工作流嵌入和云资产覆盖扩张。' },
      { name: '事故后预算脉冲的交易纪律', why: '重大泄露会短期提升采购，但持续收入取决于能否转成平台合同。', mispricing: '市场常在事故后无差别买安全股。', alpha: '超额收益来自筛选能把事件需求转成 RPO 和 FCF 的公司。' },
    ],
  },
  autonomous: {
    facts: [
      '自动驾驶商业化从乘用车 L2+/NOA 与 Robotaxi 两条线推进，硬件降价快，软件和运营能力更稀缺。',
      'Robotaxi 的真实指标不是发布会，而是去安全员里程、周单量、城市覆盖、接管率和安全事件。',
      '激光雷达和传感器会受益出货增长但 ASP 承压，利润池更可能在软件栈、数据闭环、算力平台和运营网络。',
      '领先指标包括 Waymo/Tesla/Apollo Go 单量、事故/召回、车企定点、Drive 平台收入和 TSMC 先进制程利用率。',
    ],
    opportunities: [
      { name: 'Robotaxi 地理围栏扩张是真 KPI', why: '城市数量、运营面积、周单量和去安全员比例比演示视频更能说明商业化。', mispricing: '市场容易把一次发布当规模化拐点，忽视运营密度和监管限制。', alpha: '超额收益来自单位经济改善、保险/安全数据和高频里程增长。' },
      { name: '软件数据飞轮，而非激光雷达 ASP', why: '硬件价格会降，长期定价权在感知、规划、数据闭环和 OTA 能力。', mispricing: '投资者用硬件出货周期交易自动驾驶，方向可能反了。', alpha: '超额收益来自软件订阅、授权和数据规模。' },
      { name: 'Drive Thor/车载算力定点', why: '高阶智驾需要集中式大算力，芯片平台一旦定点会锁定多年车型周期。', mispricing: '市场只看消费电子芯片节奏，低估车规平台的设计周期和切换成本。', alpha: '超额收益来自车型定点、软件栈绑定和算力升级。' },
      { name: '中国城市 NOA 的规模试验场', why: '中国车企快速迭代、道路复杂、数据密度高，会推动低成本方案成熟。', mispricing: '市场容易只看美国 Robotaxi，忽视中国乘用车 NOA 的量产速度。', alpha: '超额收益来自渗透率、数据闭环和供应链降本。' },
      { name: '安全召回是反向领先指标', why: '召回、暂停和监管调查会暴露模型边界，也会筛掉无法规模化的玩家。', mispricing: '市场通常把安全事件当短期噪音，但它可能改变扩城节奏。', alpha: '超额收益来自对扩张速度、合规成本和竞争格局的提前修正。' },
    ],
  },
  hydrogen: {
    facts: [
      '氢能要区分灰氢刚需、蓝氢过渡和绿氢补贴期权；把它们混成一个 TAM 会误判周期。',
      '电解槽制造能力已明显扩张但利用率不足，真正稀缺更可能在 offtake、低价电力、PFSA 膜、催化剂和项目融资。',
      '铱/PGM 是重要变量但不是唯一硬天花板，减载、回收和路线切换会改变瓶颈强度。',
      '领先指标包括 take-or-pay 合同、FID/取消净额、45V/RED III、出货 GW、利用率、铱价和项目电价。',
    ],
    opportunities: [
      { name: 'Offtake/FID 缺口交易', why: '绿氢项目最大问题不是设备能不能造，而是谁用长期价格买单。', mispricing: '市场把项目公告当需求，忽视 FID、融资和 offtake 才是真订单。', alpha: '超额收益来自筛选已锁定买方、电力和补贴的项目链。' },
      { name: 'PFSA 质子膜寡头', why: 'PEM 路线离不开高性能膜材料，PFAS 合规和工艺积累让供给不易复制。', mispricing: '投资者追电解槽整机，低估耗材层的毛利和合规门槛。', alpha: '超额收益来自膜材料份额、替换需求和监管下的合规产能。' },
      { name: 'PGM 催化剂与回收的双向期权', why: '铱稀缺抬高催化剂价值，但减载和回收又会成为解瓶颈的关键。', mispricing: '市场把铱简单当线性短缺，忽视技术进步会重分配利润。', alpha: '超额收益来自回收率、载量下降和催化剂认证。' },
      { name: '工业气体龙头优于烧钱电解槽', why: '林德等公司掌握客户、管网、运行经验和项目融资能力，更接近真实需求。', mispricing: '市场偏爱高 beta 设备商，低估既有工业气体网络的护城河。', alpha: '超额收益来自长期合同、项目组合和资本纪律。' },
      { name: '45V 规则下的区域套利', why: '补贴、额外性电力和碳强度核算会决定项目经济性，区域差异很大。', mispricing: '市场把政策利好平均分给全行业，忽视合规电力和项目位置。', alpha: '超额收益来自政策落地、低成本电力和税收抵免可融资性。' },
    ],
  },
  advanced_packaging: {
    facts: [
      '先进封装与 HBM 已成为 AI 芯片交付的核心瓶颈，不再只是后道配套。',
      'HBM4、CoWoS、ABF/载板、混合键合和测试共同决定有效供给；任何一环良率不足都会拖累整机出货。',
      '利润池集中在 HBM 寡头、台积电 CoWoS、ABF/键合/测试设备等小而硬的环节。',
      '领先指标包括 HBM4 份额、CoWoS 月产能、ABF 出货、BESI/Hanmi/Advantest 订单和 12H/16H 良率。',
    ],
    opportunities: [
      { name: 'HBM4 认证席位重排', why: 'HBM4 从堆叠存储升级为系统级认证品，份额变化会直接改变存储厂利润结构。', mispricing: '市场用过去 HBM3E 份额外推，低估三星回归、美光追赶和客户认证节奏。', alpha: '超额收益来自认证节点、ASP、份额重排和良率兑现。' },
      { name: 'CoWoS 产能是 AI 芯片总闸门', why: 'GPU/ASIC 设计再强，也要过台积电先进封装产能和良率。', mispricing: '投资者容易把瓶颈归给英伟达自身，低估台积电封装的独立定价权。', alpha: '超额收益来自封装扩产、预订锁定和客户排队。' },
      { name: 'ABF 膜和载板的窄门', why: '大尺寸封装对基板、ABF 膜和平整度要求提升，材料小环节会卡大出货。', mispricing: '市场嫌材料市场规模小，却忽视它对 AI 加速器出货的闸门作用。', alpha: '超额收益来自高端品类 mix、客户认证和供给扩张慢。' },
      { name: '混合键合设备的下一代封装期权', why: '更高带宽和更小间距推动混合键合成为先进封装升级方向。', mispricing: '市场把它当设备小分支，低估一旦路线切换的设备弹性。', alpha: '超额收益来自订单拐点、装机基数低和工艺锁定。' },
      { name: '测试时间随复杂度上升', why: 'HBM 和多 die 封装使测试、老化和良率筛选更重要，测试设备强度提升。', mispricing: '投资者看芯片数量，忽视每颗芯片测试时间和复杂度上升。', alpha: '超额收益来自测试设备订单、耗材服务和良率管理需求。' },
    ],
  },
}

function buildSectorResearch(s) {
  const d = typeof s.demand === 'object' && s.demand ? s.demand : { what: s.demand, why_pay: s.hook, nature: s.takeaway }
  const bottlenecks = (s.layers || []).filter((l) => l.tightness === 'tight')
  const priority = bottlenecks.length ? bottlenecks : topLayers(s, 5)
  const con = s.conclusion || {}
  const inv = s.investment || {}
  const cyc = s.cycle || {}
  const rg = s.rigor || {}
  const leaders = priority.flatMap(layerPlayers).slice(0, 8)
  const topLinks = con.top_links?.length ? con.top_links.map(shortLabel).filter(Boolean) : priority.slice(0, 3).map((l) => l.layer)
  const memo = SECTOR_MEMOS[s.key] || {}
  const oppSeeds = (memo.opportunities?.length ? memo.opportunities : (con.top_links?.length ? con.top_links : priority.map((l) => l.layer))).slice(0, 5)

  return cleanReportCopy({
    definition: {
      one_liner: `${s.name}产业本质上是在利用${topLinks.join('、')}等关键供给能力，为${s.category}客户解决规模化、成本和可靠性交付问题，并通过订单增长、价格弹性、利用率和份额提升获得利润。`,
      demand: d.what || s.hook,
      business: d.why_pay || inv.upside_driver || s.hook,
      profit: con.top_links?.length
        ? `利润更可能集中在${con.top_links.join('、')}，而不是所有环节平均分配。`
        : `利润更可能集中在${priority.map((l) => l.layer).join('、')}这些供给偏紧或验证周期长的环节。`,
    },
    answers: [
      `钱从${shortText(d.what || s.category)}的真实需求来，核心变量是${shortText(inv.key_variable || '需求增长、价格、利用率和订单持续性')}。`,
      `资金会沿下游需求流向中游制造、系统集成和上游卡点；${shortText(s.cost_structure || '越稀缺、越难替代的环节越容易截留利润。')}`,
      `产业链控制权主要在${topLinks.join('、')}，验证指标包括${names(con.track_data || [inv.leading_indicator])}。`,
      `最接近“卖铲子”的位置是${topLinks[0] || priority[0]?.layer || '关键上游'}，因为它不直接赌终端赢家，而是服务多个下游玩家。`,
    ],
    fact_checks: memo.facts || [
      `市场规模与需求锚：${shortText(d.what || s.hook, 180)}`,
      `瓶颈：${names(topLinks)}`,
      `龙头与隐形冠军：${names(leaders.slice(0, 5))}`,
      `利润池：${shortText(con.top_links?.join(' / ') || inv.valuation_metric || '集中在高议价能力与高验证门槛环节', 180)}`,
      `领先指标：${names(con.track_data || [inv.leading_indicator])}`,
    ],
    value_chain: (s.layers || []).map((l) => ({
      stage: l.layer,
      revenue: l.profit_model || l.desc,
      margin: l.margin || marginFallback[l.tightness] || '中',
      moat: l.moat || l.chokepoint || l.desc,
      pricing_power: tightLabel[l.tightness] || '中',
    })),
    bottlenecks: priority.map((l) => ({
      stage: l.layer,
      substitution: l.tightness === 'tight' ? '难' : l.tightness === 'medium' ? '中' : '低',
      tech: l.chokepoint || l.moat ? '高' : '中',
      capital: l.capex || '中',
      time: l.tightness === 'tight' ? '3-7 年' : '1-3 年',
    })),
    demand_tree: [
      { driver: '需求为什么存在', reasons: [d.what, d.why_pay].filter(Boolean) },
      { driver: '增长来自哪里', reasons: [cyc.demand_driver, inv.upside_driver, inv.key_variable].filter(Boolean) },
      { driver: '最大风险', reasons: [cyc.biggest_risk, con.risk, rg.failure_mode].filter(Boolean) },
    ],
    supply_tree: [
      ...groupLayers(s.layers),
      { driver: '供给扩张与替代', items: [cyc.outlook, rg.counterexample].filter(Boolean) },
    ],
    cycle: {
      stage: cyc.state || '需要按订单、价格和产能利用率持续跟踪',
      path: cyc.outlook || inv.upside_driver || s.hook,
      misread: con.misread || rg.counterexample || '市场容易把终端需求和真正有定价权的上游卡点混为一谈。',
    },
    profit_migration: {
      past_winners: topLayers(s, 3).map((l) => l.layer),
      future_winners: topLinks,
      past_losers: (s.layers || []).filter((l) => l.tightness === 'loose').slice(0, 3).map((l) => l.layer),
      future_losers: [con.risk || cyc.biggest_risk || '无法证明 ROI、扩产过快或缺少差异化的环节'],
    },
    tech_routes: (s.layers || []).slice(0, 6).map((l) => ({
      route: l.layer,
      maturity: l.stage || s.category,
      commercial: l.tightness === 'tight' ? '已验证但扩张慢' : '扩张中',
      cost_curve: l.scale ? `规模效应${l.scale}` : '取决于产能利用率与学习曲线',
      win_rate: l.tightness === 'tight' ? '高' : l.tightness === 'medium' ? '中' : '低',
    })),
    five_forces: [
      `供应商议价能力：${priority[0]?.layer || '上游卡点'}等环节偏强。`,
      `客户议价能力：下游需求方会压价，但在${topLinks[0] || '瓶颈'}短缺时让位于供给约束。`,
      `潜在进入者威胁：${priority.some((l) => l.tightness === 'tight') ? '核心卡点进入壁垒高，非核心环节容易拥挤。' : '整体进入壁垒中等，需警惕同质化。'}`,
      `替代品威胁：${rg.counterexample || con.risk || '技术路线切换可能重排利润池。'}`,
      `行业竞争程度：${con.misread || '终端叙事热，真正利润取决于谁有定价权。'}`,
    ],
    opportunities: oppSeeds.map((seed, i) => {
      const raw = typeof seed === 'string' ? seed : seed.name
      const l = matchLayer(raw, s.layers)
      const label = shortLabel(raw) || l?.layer || `机会窗口 ${i + 1}`
      return {
        name: label,
        why: shortText(seed.why || (i === 0 ? rg.why : '') || l?.chokepoint || l?.moat || l?.desc || raw, 180),
        market: shortText(cyc.demand_driver || d.what || s.category, 140),
        beneficiaries: shortText(l?.profit_model || l?.desc || raw, 150),
        leaders: layerPlayers(l).slice(0, 5),
        signals: [inv.leading_indicator, ...(con.track_data || [])].filter(Boolean).slice(0, 3),
        metrics: [inv.key_variable, inv.valuation_metric, cyc.outlook].filter(Boolean).slice(0, 3),
        failure: [con.risk, cyc.biggest_risk, rg.counterexample].filter(Boolean).slice(0, 2),
        mispricing: shortText(seed.mispricing || (i === 0 ? con.misread : `市场常把${label}视作线性受益环节，但真正需要验证的是订单质量、供给弹性和替代路线。`), 180),
        alpha: shortText(seed.alpha || (l?.tightness === 'tight'
          ? '超额收益来自供给无法快速复制、客户迁移成本高、价格或份额改善先于市场共识。'
          : '超额收益来自产品结构升级、份额集中和下游客户从试点进入规模采购。'), 180),
      }
    }),
    investor_views: [
      { type: 'VC', position: names(topLinks.slice(0, 2)), risk: rg.failure_mode || con.risk || '商业化周期过长' },
      { type: 'PE', position: names(priority.filter((l) => l.capex !== '轻').slice(0, 2).map((l) => l.layer)), risk: cyc.biggest_risk || '资产利用率不足' },
      { type: '对冲基金', position: `${inv.key_variable || '景气度'}驱动的多空篮子`, risk: con.risk || '周期反转' },
      { type: '长期价值', position: names(topLinks), risk: con.misread || '估值透支' },
      { type: '产业资本', position: names(priority.slice(0, 3).map((l) => l.layer)), risk: rg.counterexample || '技术路线押错' },
    ],
    ten_year: {
      today_winners: names(topLayers(s, 3).map((l) => l.layer)),
      future_winners: names(topLinks),
      today_profit_pool: shortText(inv.valuation_metric || '订单、价格和利用率'),
      future_profit_pool: shortText(inv.upside_driver || con.top_links?.join(' / ') || '卡脖子环节和高粘性服务'),
    },
    research_tasks: [
      `持续跟踪：${names(con.track_data || [inv.leading_indicator])}`,
      `重点阅读：${names(leaders.slice(0, 5))}的年报、招股书、投资者日和电话会。`,
      `专家访谈：${topLinks.join('、')}的供应链、采购、工程和客户侧专家。`,
      `尚未证伪假设：${rg.why || inv.upside_driver || s.hook}`,
      `可信度不足处：${rg.failure_mode || con.risk || '需求持续性、技术路线和供给扩张节奏。'}`,
    ],
    conclusion: {
      sentence: `未来 10 年，${s.name}产业链最值得关注的环节是${topLinks.join('、')}，因为${con.misread || rg.why || '它们更接近控制权、利润池和供需错配的交汇点'}。`,
      ratings: [
        { rating: '★★★★★ 必看', items: topLinks.slice(0, 3) },
        { rating: '★★★★ 重点关注', items: priority.slice(0, 3).map((l) => l.layer) },
        { rating: '★★★ 中性', items: (s.layers || []).filter((l) => l.tightness === 'medium').slice(0, 3).map((l) => l.layer) },
        { rating: '★★ 谨慎', items: (s.layers || []).filter((l) => l.tightness === 'loose').slice(0, 3).map((l) => l.layer) },
        { rating: '★ 回避', items: ['无订单验证、无技术壁垒、只靠概念估值的环节'] },
      ],
    },
    live_signal: shortText(inv.leading_indicator || con.track_data?.[0] || '基于新版产业链深度图谱数据'),
  })
}

const STAGE_META = {
  下游: { cls: 'st-down', title: '下游 · 需求与集成', sub: '出钱的人 / 整机 / 应用' },
  中游: { cls: 'st-mid', title: '中游 · 制造与平台', sub: '核心器件 / 代工 / 系统' },
  上游: { cls: 'st-up', title: '上游 · 原料·设备·IP', sub: '卡脖子常藏在这里' },
}

// 把层按阶段(下游/中游/上游)归组，形成"包含"关系
function groupByStage(layers) {
  const groups = []
  for (const l of layers) {
    const st = l.stage || '链条'
    const last = groups[groups.length - 1]
    if (last && last.stage === st) last.items.push(l)
    else groups.push({ stage: st, items: [l] })
  }
  return groups
}

function ChainMap({ layers, onOpenStock }) {
  const grouped = layers.some((l) => l.stage)
  if (!grouped) {
    return (
      <div className="sector-flow">
        {layers.map((l, i) => (
          <div key={i}><Layer l={l} onOpenStock={onOpenStock} />
            {i < layers.length - 1 && <div className="chain-arrow" />}</div>
        ))}
      </div>
    )
  }
  const groups = groupByStage(layers)
  return (
    <div className="chain-map">
      <div className="chain-axis"><span>需求</span><span className="chain-axis-line" /><span>供给</span></div>
      <div className="chain-stages">
        {groups.map((g, gi) => {
          const m = STAGE_META[g.stage] || { cls: '', title: g.stage, sub: '' }
          return (
            <div key={gi}>
              <div className={`chain-stage ${m.cls}`}>
                <div className="chain-stage-rail">
                  <span className="chain-stage-title">{m.title}</span>
                  <span className="chain-stage-sub">{m.sub}</span>
                </div>
                <div className="chain-stage-body">
                  {g.items.map((l, i) => (
                    <div key={i}><Layer l={l} onOpenStock={onOpenStock} />
                      {i < g.items.length - 1 && <div className="chain-arrow sm" />}</div>
                  ))}
                </div>
              </div>
              {gi < groups.length - 1 && (
                <div className="chain-stage-link"><span className="chain-arrow lg" /><span className="chain-stage-link-t">依赖上游供给</span></div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function TransmissionPanel({ t, onOpenStock }) {
  if (!t || !t.links?.length) return null
  const c = t.commodity || {}
  const cls = (d) => (d === '同向' ? 'tr-same' : d === '反向' ? 'tr-rev' : 'tr-none')
  const fmt = (n) => (n == null ? '—' : Math.round(n).toLocaleString())
  return (
    <div className="sector-block trans-block">
      <div className="sector-section-t">{t.title || '实证传导'}（数据验证 · A股 · Tushare）</div>
      <div className="judge-notes" style={{ marginBottom: 8 }}>{t.headline}</div>
      <div className="trans-commodity">
        <b>{c.name}</b> · {c.proxy} · {c.window} · n={c.n} · 区间 {fmt(c.low)}–{fmt(c.high)} {c.unit}
      </div>
      <div className="trans-list">
        {t.links.map((l, i) => (
          <div className="trans-row" key={i}>
            <div className="trans-row-h">
              <span className="trans-layer">{l.layer}</span>
              {l.ts_code
                ? <span className="company-chip" onClick={() => onOpenStock && onOpenStock(l.ts_code)}>{l.name} <b>{l.ts_code}</b></span>
                : <span className="company-chip muted">{l.name}</span>}
              <span className={`trans-tag ${cls(l.direction)}`}>{l.direction}</span>
              <span className="trans-r">Δr {l.r_change > 0 ? '+' : ''}{l.r_change} · n={l.n}</span>
            </div>
            <div className="trans-read">{l.read}</div>
          </div>
        ))}
      </div>
      <div className="judge-notes trans-caveat">{t.method}　·　{t.source}　·　{t.caveat}</div>
    </div>
  )
}

function SectorDetail({ s, onBack, onOpenStock, onOpenLiveAI }) {
  const deep = typeof s.demand === 'object' && s.demand !== null
  const cyc = s.cycle, inv = s.investment, con = s.conclusion, rg = s.rigor
  const sectorResearch = buildSectorResearch(s)

  return (
    <div>
      <div className="focus-bar">
        <button className="link-btn" onClick={onBack}>← 返回图谱</button>
        {s.key === 'ai_datacenter' && onOpenLiveAI && (
          <button className="link-btn" style={{ color: 'var(--accent)' }} onClick={onOpenLiveAI}>看实时 AI 产业链动态 →</button>
        )}
      </div>
      <div className="detail-header" style={{ marginTop: 4 }}>
        <h2>{s.name}</h2>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>{s.category}</span>
      </div>
      <div className="judge-box" style={{ margin: '10px 0', display: 'block' }}>
        <div style={{ fontWeight: 700, marginBottom: 4 }}>{s.hook}</div>
        {deep ? (
          <>
            <div className="judge-notes"><b>终端需求：</b>{s.demand.what}</div>
            <div className="judge-notes"><b>为何付钱：</b>{s.demand.why_pay}</div>
            <div className="judge-notes"><b>需求性质：</b>{s.demand.nature}</div>
          </>
        ) : <div className="judge-notes">需求锚：{s.demand}</div>}
      </div>

      <div className="sector-section-t">产业链全景（下游 → 上游 · =卡脖子）</div>
      <ChainMap layers={s.layers} onOpenStock={onOpenStock} />

      {s.transmission && <TransmissionPanel t={s.transmission} onOpenStock={onOpenStock} />}

      <ResearchReport research={sectorResearch} />

      {deep && (
        <>
          {s.cost_structure && (
            <div className="sector-block">
              <div className="sector-section-t">成本结构</div>
              <div className="judge-notes">{s.cost_structure}</div>
            </div>
          )}
          {s.relationships?.length > 0 && (
            <div className="sector-block">
              <div className="sector-section-t">上下游关系 · 谁依赖谁</div>
              {s.relationships.map((r, i) => <div className="judge-notes rel-li" key={i}>· {r}</div>)}
            </div>
          )}
          {cyc && (
            <div className="sector-block">
              <div className="sector-section-t">供需周期</div>
              <div className="iv-grid">
                <Cell k="当前供需" v={cyc.state} />
                <Cell k="1/3/5 年供给" v={cyc.outlook} />
                <Cell k="需求来源" v={cyc.demand_driver} />
                <Cell k="最大风险" v={cyc.biggest_risk} />
              </div>
            </div>
          )}
          {inv && (
            <div className="sector-block">
              <div className="sector-section-t">投资逻辑</div>
              <div className="iv-grid">
                <Cell k="核心变量" v={inv.key_variable} />
                <Cell k="上涨驱动" v={inv.upside_driver} />
                <Cell k="估值口径" v={inv.valuation_metric} />
                <Cell k="最领先指标" v={inv.leading_indicator} />
              </div>
            </div>
          )}
          {con && (
            <div className="sector-block">
              <div className="sector-section-t">结论</div>
              {con.top_links?.length > 0 && (
                <div className="judge-notes"><b>最值得关注的环节：</b>{con.top_links.join(' / ')}</div>
              )}
              {con.pricing_power?.length > 0 && (
                <div style={{ margin: '6px 0' }}>
                  <div className="judge-notes" style={{ marginBottom: 4 }}><b>最有定价权的公司：</b></div>
                  {con.pricing_power.map((p, i) => (
                    <div className="pp-li" key={i}>
                      {p.ticker
                        ? <span className="company-chip" onClick={() => onOpenStock && onOpenStock(p.ticker)}>{p.name} <b>{p.ticker}</b></span>
                        : <span className="company-chip muted">{p.name}</span>}
                      <span className="judge-notes" style={{ marginLeft: 6 }}>{p.why}</span>
                    </div>
                  ))}
                </div>
              )}
              <div className="judge-notes" style={{ color: 'var(--neutral)' }}><b>最易被误解：</b>{con.misread}</div>
              <div className="judge-notes" style={{ color: 'var(--down)' }}>⚠<b>最大风险：</b>{con.risk}</div>
              {con.track_data?.length > 0 && (
                <div className="judge-notes"><b>要跟踪的数据：</b>{con.track_data.map(cleanObservationText).join(' · ')}</div>
              )}
            </div>
          )}
          {rg && (
            <div className="sector-block">
              <div className="sector-section-t">关键推演</div>
              <div className="iv-grid">
                <Cell k="为什么这么判断" v={rg.why} />
                <Cell k="关键观察" v={cleanObservationText(rg.evidence)} />
                <Cell k="反例" v={rg.counterexample} />
                <Cell k="若判断错，最可能错在" v={rg.failure_mode} />
              </div>
            </div>
          )}
        </>
      )}

      {!deep && s.takeaway && (
        <div className="judge-box" style={{ margin: '14px 0', display: 'block', borderColor: 'rgba(255,176,46,.35)' }}>
          <b>一句话拆解：</b>{s.takeaway}
        </div>
      )}
    </div>
  )
}

export default function SectorsView({ onOpenStock, onOpenLiveAI }) {
  const [data, setData] = useState(null)
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    fetchRetry('/api/sectors').then((d) => {
      if (cancelled) return
      if (d) setData(d)
      else setTimeout(() => !cancelled && setAttempt((a) => a + 1), 4000)
    })
    return () => { cancelled = true }
  }, [attempt])

  if (!data) return <div className="detail loading"><span className="spin" /> 加载产业链图谱…</div>

  if (open) {
    return (
      <div className="detail">
        <SectorDetail s={open} onBack={() => setOpen(null)} onOpenStock={onOpenStock} onOpenLiveAI={onOpenLiveAI} />
      </div>
    )
  }

  const q = query.trim().toLowerCase()
  const list = [...data.sectors].sort((a, b) => (b.researched ? 1 : 0) - (a.researched ? 1 : 0)).filter((s) =>
    !q || s.name.toLowerCase().includes(q) || s.category.toLowerCase().includes(q)
    || s.hook.includes(query) || s.layers.some((l) => l.layer.includes(query)
    || l.players.some((p) => (p.name || '').includes(query) || (p.ticker || '').toLowerCase().includes(q))))

  return (
    <div className="detail">
      <div className="detail-header">
        <h2>产业链图谱</h2>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>从下游到上游，找出每条链的卡脖子环节</span>
      </div>
      <div className="search-row" style={{ margin: '12px 0 8px' }}>
        <input placeholder="搜产业链 / 板块 / 公司：太阳能 / 机器人 / 核能 / 量子 …"
          value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className="sector-grid">
        {list.map((s) => {
          return (
            <div className="sector-card" key={s.key} onClick={() => setOpen(s)}>
              <b>{s.name}</b>
              <span className="sector-card-cat">{s.category}</span>
              <p>{s.hook}</p>
            </div>
          )
        })}
      </div>
      {!list.length && <div className="judge-notes">没找到「{query}」相关的产业链。</div>}
      <div className="judge-notes" style={{ marginTop: 14 }}>{data.disclaimer}</div>
    </div>
  )
}
