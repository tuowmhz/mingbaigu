"""AI 产业链第一性原理图谱（美股链 + A股链）。

美股链：AI 的本质是把电变成算力、把算力变成智能。
  物理链：设备→代工→芯片→存储/网络→整机→电力→云→应用；
  钱的流向相反：每一环的收入 = 下一环的成本。

A股链的第一性原理与美股不同——它有两条并行逻辑：
  ① 出海卖铲人：光模块（全球份额 60%+）、PCB、服务器代工——
     下游引擎其实是美国云厂的资本开支，跟的是全球 AI 周期；
  ② 国产替代：国产 GPU/代工/设备——引擎是制裁倒逼 + 国内智算投资，
     跟的是政策与安全逻辑，和全球周期可以脱钩。
  看 A股 AI 公司第一个问题永远是：它赚的是哪条逻辑的钱？
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yfinance as yf

from ..cache import cached, disk_cache_load, disk_cache_save
from ..data.market import get_fundamentals

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# ============ 美股链 ============

US_CHAIN = [
    {
        "layer": "设备与材料", "emoji": "🔧",
        "desc": "造芯片的机器：没有 EUV 光刻机就没有先进制程",
        "companies": [
            ("ASML", "阿斯麦", "EUV 光刻机全球垄断"),
            ("AMAT", "应用材料", "沉积/注入设备龙头"),
            ("LRCX", "泛林集团", "刻蚀设备"),
            ("KLAC", "科磊", "量测检测"),
        ],
    },
    {
        "layer": "晶圆代工", "emoji": "🏭",
        "desc": "把设计图变成实体芯片：先进制程几乎只有一家能做",
        "companies": [("TSM", "台积电", "3nm/2nm 先进制程 90%+ 份额，CoWoS 先进封装")],
    },
    {
        "layer": "AI 芯片", "emoji": "🧠",
        "desc": "算力的源头：整条链利润最厚的环节",
        "companies": [
            ("NVDA", "英伟达", "GPU + CUDA 生态王者"),
            ("AMD", "超威半导体", "GPU 第二极"),
            ("AVGO", "博通", "云厂定制 ASIC + 网络芯片"),
            ("MRVL", "迈威尔", "定制计算芯片"),
        ],
    },
    {
        "layer": "存储 HBM", "emoji": "💾",
        "desc": "高带宽内存：每张旗舰 GPU 都要配，长期供不应求",
        "companies": [("MU", "美光", "HBM 三巨头中唯一美股")],
    },
    {
        "layer": "网络与光通信", "emoji": "🔌",
        "desc": "把十万张 GPU 连成一台计算机：光模块是 AI 集群的'神经'",
        "companies": [
            ("ANET", "Arista", "AI 数据中心交换机"),
            ("COHR", "Coherent", "光模块/光器件"),
            ("LITE", "Lumentum", "光芯片/光模块"),
            ("FN", "Fabrinet", "光模块代工"),
        ],
    },
    {
        "layer": "服务器整机", "emoji": "🖥️",
        "desc": "组装成机柜交付：靠量取胜、毛利最薄的一环",
        "companies": [
            ("SMCI", "超微电脑", "AI 服务器"),
            ("DELL", "戴尔", "AI 服务器 + 企业渠道"),
        ],
    },
    {
        "layer": "电力与散热", "emoji": "⚡",
        "desc": "物理瓶颈：一座 AI 数据中心的耗电 ≈ 一座小城市",
        "companies": [
            ("VRT", "维谛技术", "供配电 + 液冷"),
            ("ETN", "伊顿", "电力设备"),
            ("CEG", "星座能源", "核电直供数据中心"),
            ("VST", "Vistra", "电力供应商"),
        ],
    },
    {
        "layer": "云与算力平台", "emoji": "☁️",
        "desc": "链条的发动机：它们的资本开支 = 上游所有人的收入",
        "companies": [
            ("MSFT", "微软", "Azure + OpenAI"),
            ("GOOGL", "谷歌", "GCP + Gemini + 自研 TPU"),
            ("AMZN", "亚马逊", "AWS + 自研 Trainium"),
            ("META", "Meta", "全自用：推荐系统 + Llama"),
            ("ORCL", "甲骨文", "OCI 算力租赁黑马"),
        ],
    },
    {
        "layer": "模型与应用", "emoji": "🤖",
        "desc": "需求的最终来源：应用赚不到钱，整条链就是空中楼阁",
        "companies": [
            ("PLTR", "Palantir", "企业 AI 落地"),
            ("CRM", "Salesforce", "Agentforce"),
            ("NOW", "ServiceNow", "企业流程 AI"),
            ("TSLA", "特斯拉", "自动驾驶 + 机器人"),
        ],
    },
]

# ============ A股链（layer 带 logic 标签：出海 / 国产替代 / 双驱动）============

CN_CHAIN = [
    {
        "layer": "半导体设备", "emoji": "🔧", "logic": "国产替代",
        "desc": "国产线的'阿斯麦+应用材料'：制裁越狠订单越满",
        "companies": [
            ("002371.SZ", "北方华创", "刻蚀/沉积设备国产龙头"),
            ("688012.SS", "中微公司", "刻蚀设备"),
        ],
    },
    {
        "layer": "晶圆代工", "emoji": "🏭", "logic": "国产替代",
        "desc": "国产算力芯片的产能瓶颈：先进制程被卡，成熟制程扩产",
        "companies": [
            ("688981.SS", "中芯国际", "大陆代工龙头，国产 AI 芯片几乎唯一选择"),
            ("688347.SS", "华虹公司", "特色工艺代工"),
        ],
    },
    {
        "layer": "国产算力芯片", "emoji": "🧠", "logic": "国产替代",
        "desc": "对标英伟达的国家队：性能有差距，但订单有保障",
        "companies": [
            ("688256.SS", "寒武纪", "国产 AI 芯片第一股"),
            ("688041.SS", "海光信息", "x86 CPU + DCU 加速卡"),
            ("300474.SZ", "景嘉微", "国产 GPU"),
        ],
    },
    {
        "layer": "存储与接口", "emoji": "💾", "logic": "双驱动",
        "desc": "内存接口芯片全球份额领先；存储国产化推进中",
        "companies": [
            ("688008.SS", "澜起科技", "内存接口芯片全球前二"),
            ("603986.SS", "兆易创新", "存储芯片设计"),
        ],
    },
    {
        "layer": "光模块与光通信", "emoji": "🔆", "logic": "出海",
        "desc": "A股 AI 链皇冠：全球 60%+ 份额，英伟达/谷歌的核心供应商——赚的是美国 capex 的钱",
        "companies": [
            ("300308.SZ", "中际旭创", "800G/1.6T 光模块全球第一"),
            ("300502.SZ", "新易盛", "光模块全球前三"),
            ("300394.SZ", "天孚通信", "光器件平台"),
            ("002281.SZ", "光迅科技", "光芯片+模块"),
        ],
    },
    {
        "layer": "PCB 高多层板", "emoji": "🟫", "logic": "出海",
        "desc": "AI 服务器衍生需求：GPU 板卡要 20 层以上高速板，单价数倍于普通板",
        "companies": [
            ("002463.SZ", "沪电股份", "AI 服务器 PCB 主力供应商"),
            ("002916.SZ", "深南电路", "高多层板"),
        ],
    },
    {
        "layer": "服务器整机", "emoji": "🖥️", "logic": "双驱动",
        "desc": "国内出货靠浪潮/曙光，全球代工靠工业富联（英伟达机柜代工）",
        "companies": [
            ("000977.SZ", "浪潮信息", "国内 AI 服务器份额第一"),
            ("601138.SS", "工业富联", "英伟达 GB 系列机柜代工"),
            ("603019.SS", "中科曙光", "算力基建+液冷"),
        ],
    },
    {
        "layer": "IDC 与液冷", "emoji": "❄️", "logic": "双驱动",
        "desc": "AI 衍生基建：高功率机柜逼出液冷渗透率拐点",
        "companies": [
            ("300442.SZ", "润泽科技", "批发型智算中心"),
            ("002837.SZ", "英维克", "液冷温控龙头"),
            ("300383.SZ", "光环新网", "IDC+云"),
        ],
    },
    {
        "layer": "算力运营（国内引擎）", "emoji": "📡", "logic": "国产替代",
        "desc": "国内智算投资主力：运营商集采 = 国产芯片/服务器的大订单",
        "companies": [
            ("600941.SS", "中国移动", "智算中心最大买家之一"),
            ("601728.SS", "中国电信", "天翼云+智算"),
        ],
    },
    {
        "layer": "模型与应用", "emoji": "🤖", "logic": "国产替代",
        "desc": "国内需求的最终来源：大模型落地与办公场景",
        "companies": [
            ("002230.SZ", "科大讯飞", "星火大模型+教育医疗落地"),
            ("688111.SS", "金山办公", "WPS AI"),
        ],
    },
]

US_HYPERSCALERS = ["MSFT", "GOOGL", "AMZN", "META", "ORCL"]
CN_CARRIERS = ["600941.SS", "601728.SS"]


def _industry_research(market: str, signals: dict) -> dict:
    """Institutional-style chain memo, parameterized by live chain signals."""
    is_cn = market == "CN"
    if not is_cn:
        engine = f"五大云厂 capex 同比 {signals.get('capex_yoy', '-')}"
        return {
            "definition": {
                "one_liner": "AI 基础设施产业本质上是在利用电力、先进半导体和网络系统，为企业与消费者解决智能生产力供给问题，并通过算力租赁、芯片销售和软件订阅获得利润。",
                "demand": "需求不是'买 GPU'，而是购买更低成本的推理、更高自动化率和更强产品差异化；GPU 只是把资本支出转化为 token 产能的当前最优工具。",
                "business": "商业本质是大规模资本开支前置，换取未来模型能力、用户留存、广告/云/办公软件 ARPU 和企业流程改造收益。",
                "profit": "利润本质来自稀缺瓶颈的定价权：先进 GPU、HBM、CoWoS、AI 网络、电力接入和最终拥有分发权的软件入口。",
            },
            "answers": [
                "钱从云厂、企业 IT 预算、广告平台现金流和终端软件订阅来。",
                "短期流向芯片、先进封装、HBM、网络、电力设备；长期若应用 ROI 被验证，会回流到云平台与企业软件。",
                "当前控制权在 NVIDIA/CUDA + TSMC 先进制造 + 云厂 capex；未来会向推理成本最低的平台和应用分发入口迁移。",
                "最容易出 10 倍公司的位置不是最大市值龙头，而是新瓶颈从 0 到 1 的环节：CPO/硅光、液冷、电力调度、AI 原生垂直软件、推理优化中间层。",
            ],
            "value_chain": [
                {"stage": "设备/材料", "revenue": "晶圆厂扩产 capex", "margin": "高", "moat": "工艺 know-how + 认证周期", "pricing_power": "强"},
                {"stage": "代工/封装", "revenue": "芯片公司 wafer + CoWoS 订单", "margin": "中高", "moat": "先进制程良率 + 封装产能", "pricing_power": "强"},
                {"stage": "GPU/HBM/网络", "revenue": "云厂与 OEM 采购", "margin": "最高", "moat": "生态、性能、供应锁定", "pricing_power": "极强"},
                {"stage": "服务器/集成", "revenue": "整机与机柜交付", "margin": "低", "moat": "供应链与交付速度", "pricing_power": "弱"},
                {"stage": "电力/散热", "revenue": "数据中心建设与长期供电", "margin": "中", "moat": "并网许可、工程经验、资产位置", "pricing_power": "增强"},
                {"stage": "云/应用", "revenue": "算力租赁、API、SaaS 订阅", "margin": "分化", "moat": "分发、数据、工作流嵌入", "pricing_power": "待验证"},
            ],
            "bottlenecks": [
                {"stage": "CoWoS/先进封装", "substitution": "极难", "tech": "极高", "capital": "高", "time": "3-5 年"},
                {"stage": "HBM", "substitution": "难", "tech": "高", "capital": "极高", "time": "2-4 年"},
                {"stage": "AI 网络/光互连", "substitution": "中高", "tech": "高", "capital": "中", "time": "1-3 年"},
                {"stage": "电力接入/液冷", "substitution": "难", "tech": "中", "capital": "极高", "time": "3-7 年"},
                {"stage": "CUDA/开发者生态", "substitution": "极难", "tech": "高", "capital": "中", "time": "5 年+"},
            ],
            "demand_tree": [
                {"driver": "模型能力 scaling", "reasons": ["训练集群扩大", "推理上下文变长", "多模态与 agent 增加 token 消耗"]},
                {"driver": "企业 ROI 验证", "reasons": ["客服/销售/研发提效", "软件 ARPU 提升", "内部自动化替代人力成本"]},
                {"driver": "主权与安全需求", "reasons": ["政府算力储备", "金融/医疗私有部署", "地缘竞争"]},
            ],
            "supply_tree": [
                {"driver": "扩产企业", "items": ["TSMC CoWoS", "SK hynix/Samsung/Micron HBM", "NVIDIA/AMD/ASIC", "电力设备与液冷厂商"]},
                {"driver": "替代路线", "items": ["ASIC 替代部分训练/推理 GPU", "以太网挑战 InfiniBand", "CPO 挑战可插拔光模块", "小模型与蒸馏降低单位算力"]},
                {"driver": "周期判断", "items": ["2026 仍偏瓶颈", "2027-2028 可能出现局部供给过剩", "真正拐点看云厂 capex 指引和 GPU 租赁价格"]},
            ],
            "cycle": {
                "stage": "爆发后半段到成长早期",
                "misread": "市场把 AI capex 当成一次性泡沫，低估了推理成本下降带来的需求再扩张；同时也低估了云厂若 ROI 不及预期时的长鞭下行。",
                "path": "训练 capex 驱动 → 推理规模化 → 电力与网络成为主瓶颈 → 应用 ROI 决定第二轮 capex 是否延续。",
            },
            "profit_migration": {
                "past_winners": ["NVIDIA", "TSMC", "ASML", "云厂资本开支供应链"],
                "future_winners": ["推理成本曲线领先者", "先进封装/HBM/硅光", "电力与热管理", "AI 原生工作流软件"],
                "past_losers": ["通用 CPU 增长故事", "低端服务器组装", "无差异 SaaS seat 模式"],
                "future_losers": ["无法证明 AI ROI 的应用", "被 ASIC 绕开的通用加速器份额", "缺电地区的数据中心项目"],
            },
            "tech_routes": [
                {"route": "GPU + CUDA + HBM", "maturity": "成熟扩张", "commercial": "已商业化", "cost_curve": "每代显著下降", "win_rate": "高"},
                {"route": "云厂自研 ASIC", "maturity": "快速成熟", "commercial": "2025-2027 放量", "cost_curve": "特定负载更优", "win_rate": "中高"},
                {"route": "CPO/硅光", "maturity": "导入期", "commercial": "2026-2028", "cost_curve": "降功耗与提升带宽", "win_rate": "中高但路线风险大"},
                {"route": "小模型/蒸馏/边缘推理", "maturity": "成长", "commercial": "已开始", "cost_curve": "大幅降低 token 成本", "win_rate": "高，但会压缩部分硬件增量"},
            ],
            "five_forces": [
                "供应商议价强：TSMC、HBM、设备和电力接入都是瓶颈。",
                "客户议价中等：云厂集中采购很强，但短缺期仍被上游定价。",
                "新进入者威胁低：先进半导体与生态壁垒高。",
                "替代品威胁中：ASIC、小模型和算法效率会改变利润分配。",
                "行业竞争分化：芯片高利润、服务器低利润、应用端胜负未定。",
            ],
            "opportunities": [
                {
                    "name": "推理成本曲线平台",
                    "why": "训练需求证明了能力，下一轮钱取决于单位 token 成本能否持续下降。",
                    "market": "云 API、企业私有推理、agent 工作流。",
                    "beneficiaries": "GPU/ASIC、推理云、模型压缩、缓存与路由中间层。",
                    "leaders": ["NVDA", "AVGO", "MSFT", "GOOGL", "AMZN"],
                    "signals": ["token 单价季度下降", "推理收入占 AI 收入提高", "企业续费率与席位扩张"],
                    "metrics": ["GPU 利用率", "推理毛利率", "AI API revenue run-rate"],
                    "failure": ["应用 ROI 停滞", "算力租赁价格雪崩"],
                    "mispricing": "市场仍用训练 capex 线性外推，忽略推理效率带来的需求弹性。",
                    "alpha": "买成本曲线下降后需求反而扩大的环节。",
                },
                {
                    "name": "先进封装与 HBM 铲子",
                    "why": "AI 芯片不再只是晶体管竞争，而是封装、内存带宽和系统集成竞争。",
                    "market": "高端 GPU、ASIC、HBM stack、CoWoS/SoIC。",
                    "beneficiaries": "TSMC、HBM 三巨头、封装设备和材料。",
                    "leaders": ["TSM", "MU", "ASML", "AMAT", "LRCX"],
                    "signals": ["CoWoS 交期", "HBM 合同价", "先进封装 capex"],
                    "metrics": ["HBM bit shipment", "CoWoS monthly capacity", "AI accelerator gross margin"],
                    "failure": ["封装产能快速过剩", "CPO/新封装路线迁移超预期"],
                    "mispricing": "市场看芯片 logo，多数时候瓶颈利润在看不见的封装和内存。",
                    "alpha": "瓶颈解除前享受量价齐升。",
                },
                {
                    "name": "AI 数据中心电力再定价",
                    "why": "当机柜功率上升，缺的不是土地而是可并网电力、变压器、UPS 和散热。",
                    "market": "电力设备、核电/PPA、液冷、数据中心工程。",
                    "beneficiaries": "电力设备、热管理、低成本电源附近数据中心。",
                    "leaders": ["VRT", "ETN", "CEG", "VST"],
                    "signals": ["电网接入排队时间", "液冷渗透率", "数据中心 PPA 溢价"],
                    "metrics": ["MW backlog", "power equipment backlog", "rack density"],
                    "failure": ["监管限制回报率", "AI capex 放缓"],
                    "mispricing": "市场把电力当周期公用事业，低估 AI 把稀缺电变成算力期权。",
                    "alpha": "从芯片叙事迁移到物理瓶颈叙事。",
                },
                {
                    "name": "AI 网络与硅光换代",
                    "why": "集群规模扩大后，瓶颈从单卡算力转向卡间通信、功耗和网络可靠性。",
                    "market": "800G/1.6T、交换机、硅光、CPO。",
                    "beneficiaries": "交换机、光模块、光器件、硅光平台。",
                    "leaders": ["ANET", "AVGO", "COHR", "LITE", "FN"],
                    "signals": ["1.6T 出货", "CPO 试点", "网络 capex 占集群成本提高"],
                    "metrics": ["optics revenue growth", "switch ASIC ASP", "cluster downtime"],
                    "failure": ["铜互连延寿", "CPO 重构现有供应链"],
                    "mispricing": "投资者容易只看 GPU，忽略十万卡集群其实是一台网络计算机。",
                    "alpha": "在架构换代前布局被动受益的网络瓶颈。",
                },
                {
                    "name": "垂直 AI 工作流",
                    "why": "硬件投资最终必须被应用 ROI 证明，最先商业化的是高人力成本、高文档密度行业。",
                    "market": "金融、法务、医疗、工业、软件开发、销售支持。",
                    "beneficiaries": "有数据和分发的垂直软件公司。",
                    "leaders": ["PLTR", "NOW", "CRM", "MSFT"],
                    "signals": ["AI SKU 独立定价", "净收入留存提升", "客户从试点转生产"],
                    "metrics": ["AI attach rate", "ARR uplift", "gross retention"],
                    "failure": ["客户只试用不付费", "模型能力同质化导致价格战"],
                    "mispricing": "市场把 AI 软件当 demo，低估嵌入工作流后的切换成本。",
                    "alpha": "找到先把 AI 从功能变成预算项的公司。",
                },
            ],
            "investor_views": [
                {"type": "VC", "position": "推理中间层、垂直 agent、数据/评测工具", "risk": "模型平台内置化"},
                {"type": "PE", "position": "电力工程、热管理、数据中心服务", "risk": "capex 周期下行"},
                {"type": "对冲基金", "position": "capex 链条多空篮子：瓶颈多、低毛利组装空", "risk": "政策与财报指引跳变"},
                {"type": "长期价值", "position": "拥有生态和现金流的云/芯片平台", "risk": "估值透支"},
                {"type": "产业资本", "position": "电力接入、封装产能、关键供应商绑定", "risk": "技术路线押错"},
            ],
            "ten_year": {
                "today_winners": "GPU、HBM、先进封装、云厂 capex 供应链",
                "future_winners": "低成本推理平台、电力资源控制者、AI 工作流入口",
                "today_profit_pool": "训练硬件和云 capex",
                "future_profit_pool": "推理规模化、垂直应用、能源/网络瓶颈服务",
            },
            "research_tasks": [
                "逐季跟踪 MSFT/GOOGL/AMZN/META/ORCL capex 指引与折旧年限变化。",
                "跟踪 GPU 租赁价格、HBM 合同价、CoWoS 产能和交期。",
                "阅读 NVIDIA/TSMC/ASML/Micron/Arista/VRT 年报和电话会。",
                "访谈数据中心电力接入、液冷工程、云采购、企业 CIO。",
                "尚未证伪假设：AI 应用 ROI 足以覆盖折旧；推理需求弹性大于硬件效率提升。",
            ],
            "conclusion": {
                "sentence": "未来 10 年，最值得关注的环节是推理成本曲线、先进封装/HBM 和电力热管理，因为它们同时决定 AI 能否从 capex 故事变成现金流故事。",
                "ratings": [
                    {"rating": "★★★★★ 必看", "items": ["先进封装/HBM", "电力与液冷", "推理云/优化"]},
                    {"rating": "★★★★ 重点关注", "items": ["AI 网络/硅光", "垂直 AI 软件"]},
                    {"rating": "★★★ 中性", "items": ["服务器整机", "通用 SaaS AI 插件"]},
                    {"rating": "★★ 谨慎", "items": ["高估值但无盈利验证的应用"]},
                    {"rating": "★ 回避", "items": ["无差异算力转租", "低壁垒组装"]},
                ],
            },
            "live_signal": engine,
        }

    engine = f"美国云厂 capex {signals.get('us_capex_yoy', '-')}；国内运营商 capex {signals.get('cn_capex_yoy', '-')}"
    return {
        "definition": {
            "one_liner": "A股 AI 产业链本质上是在利用中国制造供应链和国产替代政策，为全球 AI capex 与国内安全算力解决交付问题，并通过零部件出口、设备国产化和智算基础设施获得利润。",
            "demand": "A股需求分裂为两套系统：出海链赚美国云厂扩产的钱，国产链赚制裁与安全冗余的钱。",
            "business": "商业本质不是'中国版 NVIDIA'单线叙事，而是全球供应链份额 + 国内替代订单的双引擎组合。",
            "profit": "利润本质来自两个位置：全球不可绕开的高份额零部件，以及国内不可进口的关键设备/芯片。",
        },
        "answers": [
            "钱从美国 hyperscaler capex、NVIDIA 机柜供应链、国内运营商/互联网智算投资和政策性替代订单来。",
            "短期流向光模块、PCB、服务器代工、液冷；国产链流向设备、代工、国产芯片与智算运营。",
            "出海链控制权在海外客户和技术路线；国产链控制权在政策、制程产能和生态适配。",
            "最容易出 10 倍公司的位置是全球份额高且仍在技术迭代的光通信/硅光，以及国产替代中真正卡脖子的设备与 EDA/材料。",
        ],
        "value_chain": [
            {"stage": "国产设备", "revenue": "晶圆厂扩产和国产替代订单", "margin": "高", "moat": "工艺验证 + 客户粘性", "pricing_power": "强"},
            {"stage": "国产芯片/代工", "revenue": "智算集采和私有部署", "margin": "分化", "moat": "可获得性 + 生态适配", "pricing_power": "政策期较强"},
            {"stage": "光模块/PCB", "revenue": "海外云厂和 NVIDIA 链订单", "margin": "中高", "moat": "全球份额 + 良率 + 客户认证", "pricing_power": "强但受路线切换影响"},
            {"stage": "服务器/IDC", "revenue": "整机交付和算力租赁", "margin": "低到中", "moat": "交付、资金、机柜资源", "pricing_power": "中弱"},
            {"stage": "应用/模型", "revenue": "软件订阅、行业项目", "margin": "待验证", "moat": "场景数据与渠道", "pricing_power": "弱到中"},
        ],
        "bottlenecks": [
            {"stage": "800G/1.6T 光模块", "substitution": "中高", "tech": "高", "capital": "中", "time": "1-3 年"},
            {"stage": "先进制程代工", "substitution": "极难", "tech": "极高", "capital": "极高", "time": "5 年+"},
            {"stage": "半导体设备", "substitution": "难", "tech": "高", "capital": "高", "time": "3-7 年"},
            {"stage": "液冷/高功率机柜", "substitution": "中", "tech": "中", "capital": "中", "time": "1-3 年"},
            {"stage": "国产 AI 软件生态", "substitution": "难", "tech": "中高", "capital": "中", "time": "3-5 年"},
        ],
        "demand_tree": [
            {"driver": "美国 AI capex 外溢", "reasons": ["光模块全球份额高", "PCB 和服务器代工进入 NVIDIA 链", "海外客户扩产带来订单弹性"]},
            {"driver": "国产替代", "reasons": ["高端 GPU 进口受限", "运营商智算集采", "政企私有化与安全需求"]},
            {"driver": "AI 衍生基建", "reasons": ["高功率机柜", "液冷渗透", "IDC 从通用云转向智算中心"]},
        ],
        "supply_tree": [
            {"driver": "扩产企业", "items": ["光模块龙头扩 800G/1.6T", "PCB 高多层板扩产", "国产设备厂进入更多工艺段"]},
            {"driver": "替代路线", "items": ["CPO 可能重构光模块", "国产 GPU 生态替代 CUDA 部分场景", "液冷替代风冷"]},
            {"driver": "周期判断", "items": ["出海链 2026 仍看海外 capex", "国产链看运营商和政策节奏", "光模块最先暴露供需拐点"]},
        ],
        "cycle": {
            "stage": "出海链爆发期；国产链政策驱动成长期",
            "misread": "市场常把两条逻辑混成一个 AI 概念板块，导致估值同涨同跌；真正的研究必须拆开订单来源。",
            "path": "海外 capex → 光模块/PCB/代工；制裁升级 → 国产设备/芯片；应用 ROI → 国内智算复投。",
        },
        "profit_migration": {
            "past_winners": ["光模块", "PCB", "服务器代工", "国产设备"],
            "future_winners": ["硅光/CPO 适配者", "液冷与电力设备", "国产关键设备", "有真实订单的行业 AI"],
            "past_losers": ["纯概念大模型应用", "低端 IDC", "无核心技术服务器组装"],
            "future_losers": ["被 CPO 绕开的低端光模块", "无生态的国产芯片", "靠补贴无利用率的智算中心"],
        },
        "tech_routes": [
            {"route": "可插拔 800G/1.6T 光模块", "maturity": "成熟放量", "commercial": "已商业化", "cost_curve": "规模降本", "win_rate": "高"},
            {"route": "CPO/硅光", "maturity": "导入", "commercial": "2026-2028", "cost_curve": "降功耗", "win_rate": "中高但重构风险大"},
            {"route": "国产 GPU + 国产生态", "maturity": "追赶", "commercial": "政企/运营商先行", "cost_curve": "依赖制程和软件", "win_rate": "中"},
            {"route": "液冷智算中心", "maturity": "渗透率拐点", "commercial": "已开始", "cost_curve": "随机柜功率提升变刚需", "win_rate": "高"},
        ],
        "five_forces": [
            "供应商议价中高：海外芯片、光芯片、上游材料仍有约束。",
            "客户议价强：海外云厂/NVIDIA 和国内运营商都高度集中。",
            "新进入者威胁中：制造扩产容易，客户认证和良率难。",
            "替代品威胁高：CPO、国产路线、架构变化会重排供应链。",
            "行业竞争强：A股容易扩产，必须盯价格和毛利率。",
        ],
        "opportunities": [
            {
                "name": "全球 AI 光通信卖铲人",
                "why": "集群规模扩大让网络从配角变成主瓶颈，A股在光模块/器件有全球份额。",
                "market": "800G/1.6T、硅光、CPO 过渡期。",
                "beneficiaries": "光模块、光器件、光芯片、代工。",
                "leaders": ["中际旭创", "新易盛", "天孚通信", "光迅科技"],
                "signals": ["海外客户 capex 上修", "1.6T 订单", "CPO 路线适配进展"],
                "metrics": ["光模块收入增速", "毛利率", "客户集中度"],
                "failure": ["CPO 绕开现有供应链", "美国限制供应链"],
                "mispricing": "市场只看 AI 概念，低估这里是真正赚美元 capex 的 A股环节。",
                "alpha": "全球份额 + 技术迭代 + 客户认证形成的窗口期。",
            },
            {
                "name": "国产半导体设备纵深替代",
                "why": "制裁让先进设备不可得，国产线必须提高本土设备占比。",
                "market": "刻蚀、薄膜、量测、清洗、零部件。",
                "beneficiaries": "设备主机厂与关键零部件。",
                "leaders": ["北方华创", "中微公司"],
                "signals": ["晶圆厂国产设备中标", "新工艺段验证", "订单 backlog"],
                "metrics": ["合同负债", "毛利率", "研发费用率"],
                "failure": ["晶圆厂扩产放缓", "验证失败"],
                "mispricing": "市场常只看国产 GPU，忽略 GPU 背后的设备才是长期卖铲子。",
                "alpha": "工艺段从点到面的份额提升。",
            },
            {
                "name": "AI 服务器 PCB 高速板升级",
                "why": "GPU 板卡和交换机提高层数、材料和良率要求，ASP 远高于普通 PCB。",
                "market": "AI 服务器、交换机、加速卡。",
                "beneficiaries": "高多层板和高速材料供应商。",
                "leaders": ["沪电股份", "深南电路"],
                "signals": ["AI 服务器订单", "高速材料认证", "单机 PCB 价值量提升"],
                "metrics": ["AI 相关收入占比", "产能利用率", "毛利率"],
                "failure": ["服务器出货不及预期", "扩产导致价格战"],
                "mispricing": "传统 PCB 被看成低端制造，但 AI 高速板是完全不同的利润池。",
                "alpha": "产品结构升级带来的利润率重估。",
            },
            {
                "name": "液冷与智算中心工程",
                "why": "机柜功率提升后风冷失效，液冷从可选项变成基础设施。",
                "market": "高功率机柜、批发型智算中心、运营商数据中心改造。",
                "beneficiaries": "温控、IDC、工程集成。",
                "leaders": ["英维克", "润泽科技", "中科曙光"],
                "signals": ["液冷招标", "单机柜功率", "PUE 要求"],
                "metrics": ["液冷收入占比", "在手订单", "机柜上架率"],
                "failure": ["智算利用率低", "资本开支放缓"],
                "mispricing": "市场喜欢芯片弹性，忽略算力落地最后卡在电和热。",
                "alpha": "从主题投资转向工程订单验证。",
            },
            {
                "name": "国产算力生态适配",
                "why": "进口高端 GPU 受限使'能用且可买'成为政企采购核心标准。",
                "market": "运营商、政务云、金融私有 AI、教育医疗。",
                "beneficiaries": "国产芯片、服务器、框架迁移服务。",
                "leaders": ["寒武纪", "海光信息", "浪潮信息", "科大讯飞"],
                "signals": ["国产芯片集采", "适配框架数量", "客户从测试转生产"],
                "metrics": ["出货量", "生态伙伴数", "算力利用率"],
                "failure": ["性能差距无法被软件补齐", "政策订单不可持续"],
                "mispricing": "市场只比较峰值性能，忽略采购约束下可获得性本身就是价值。",
                "alpha": "安全需求给国产生态时间窗口。",
            },
        ],
        "investor_views": [
            {"type": "VC", "position": "国产 AI 软件生态、硅光/CPO、行业 agent", "risk": "客户付费慢"},
            {"type": "PE", "position": "液冷工程、IDC 改造、高端 PCB 产能", "risk": "利用率不足"},
            {"type": "对冲基金", "position": "出海链按美国 capex 做景气交易，国产链按政策订单做事件交易", "risk": "两条逻辑被市场同杀"},
            {"type": "长期价值", "position": "设备、光模块龙头、高质量 PCB", "risk": "估值周期化"},
            {"type": "产业资本", "position": "绑定海外客户认证和国产晶圆厂验证", "risk": "路线切换"},
        ],
        "ten_year": {
            "today_winners": "光模块、PCB、国产设备、服务器代工",
            "future_winners": "硅光/CPO、关键设备、液冷电力、国产生态服务",
            "today_profit_pool": "海外 capex 外溢和国产替代订单",
            "future_profit_pool": "全球网络瓶颈、国产关键工艺、智算运营效率",
        },
        "research_tasks": [
            "把出海链和国产链分开建模，分别跟踪海外云厂 capex 与国内运营商/互联网智算招标。",
            "阅读光模块、PCB、设备龙头年报和客户集中度披露。",
            "持续跟踪 1.6T/CPO、液冷招标、国产 GPU 集采、晶圆厂设备中标。",
            "访谈光模块供应链、服务器 ODM、运营商采购、半导体设备工程师。",
            "尚未证伪假设：海外 capex 不骤降；CPO 不会快速绕开现有龙头；国产替代订单能转化为可持续毛利。",
        ],
        "conclusion": {
            "sentence": "未来 10 年，A股 AI 链最值得关注的是全球光通信卖铲人、国产设备和液冷电力，因为它们分别卡住海外 capex 外溢、国产替代和算力落地的关键瓶颈。",
            "ratings": [
                {"rating": "★★★★★ 必看", "items": ["光模块/硅光", "国产半导体设备", "液冷温控"]},
                {"rating": "★★★★ 重点关注", "items": ["AI 高速 PCB", "服务器代工龙头"]},
                {"rating": "★★★ 中性", "items": ["国产算力芯片", "智算运营"]},
                {"rating": "★★ 谨慎", "items": ["纯主题应用", "低端 IDC"]},
                {"rating": "★ 回避", "items": ["无订单验证的概念股"]},
            ],
        },
        "live_signal": engine,
    }


def _capex_yoy(ticker: str) -> dict | None:
    try:
        cf = yf.Ticker(ticker).cashflow
        row = cf.loc["Capital Expenditure"].dropna()
        if len(row) < 2:
            return None
        latest, prev = abs(float(row.iloc[0])), abs(float(row.iloc[1]))
        return {"ticker": ticker, "capex": latest,
                "capex_yoy": round(latest / prev - 1, 4) if prev else None}
    except Exception:
        return None


def _momentum(tickers: list[str]) -> dict[str, float]:
    try:
        df = yf.download(tickers, period="6mo", auto_adjust=True, progress=False)["Close"]
        out = {}
        for t in tickers:
            s = df[t].dropna() if t in df else None
            if s is not None and len(s) > 60:
                out[t] = round(float(s.iloc[-1] / s.iloc[-61] - 1), 4)
        return out
    except Exception:
        return {}


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def _pct(v):
    return "-" if v is None else f"{v*100:+.0f}%"


def _build_layers(chain_def: list[dict]) -> tuple[list[dict], dict]:
    tickers = [t for layer in chain_def for t, _, _ in layer["companies"]]
    with ThreadPoolExecutor(max_workers=8) as ex:
        funds = dict(zip(tickers, ex.map(get_fundamentals, tickers)))
    momentum = _momentum(tickers)

    layers, growth = [], {}
    for spec in chain_def:
        comps = []
        for t, cn, role in spec["companies"]:
            f = funds.get(t) or {}
            rg = f.get("revenue_growth")
            growth[t] = rg
            comps.append({
                "ticker": t, "name_cn": cn, "role": role,
                "revenue_growth": rg,
                "earnings_growth": f.get("earnings_growth"),
                "momentum_60d": momentum.get(t),
                "pe": f.get("trailing_pe"),
            })
        layer_growth = _avg([c["revenue_growth"] for c in comps])
        if layer_growth is not None and layer_growth > 0.15:
            health, health_cn = "strong", "强劲"
        elif layer_growth is not None and layer_growth < 0:
            health, health_cn = "weak", "收缩"
        else:
            health, health_cn = "steady", "平稳"
        layers.append({
            "layer": spec["layer"], "emoji": spec["emoji"], "desc": spec["desc"],
            "logic": spec.get("logic"),
            "companies": comps,
            "avg_revenue_growth": layer_growth,
            "avg_momentum_60d": _avg([c["momentum_60d"] for c in comps]),
            "health": health, "health_cn": health_cn,
        })
    return layers, growth


def _layer_growth(layers: list[dict], name: str):
    return next((l["avg_revenue_growth"] for l in layers if l["layer"] == name), None)


@cached(21600)
def build_chain() -> dict:
    """美股 AI 链。"""
    cached_result = disk_cache_load(_DATA_DIR / "chain_us.json", 21600)
    if cached_result is not None and cached_result.get("research"):
        return cached_result
    layers, growth = _build_layers(US_CHAIN)
    with ThreadPoolExecutor(max_workers=5) as ex:
        capex = [c for c in ex.map(_capex_yoy, US_HYPERSCALERS) if c]
    capex_total = sum(c["capex"] for c in capex)
    capex_yoy = _avg([c["capex_yoy"] for c in capex])
    chip_g = _layer_growth(layers, "AI 芯片")
    equip_g = _layer_growth(layers, "设备与材料")
    power_g = _layer_growth(layers, "电力与散热")

    transmission = {
        "steps": [
            {"label": "☁️ 云厂资本开支", "value": _pct(capex_yoy), "note": "链条发动机"},
            {"label": "🧠 AI 芯片收入", "value": _pct(chip_g), "note": "最厚利润环节"},
            {"label": "🔧 半导体设备收入", "value": _pct(equip_g), "note": "滞后 2-4 个季度"},
            {"label": "⚡ 电力公司收入", "value": _pct(power_g), "note": "物理瓶颈"},
        ],
        "detail": ("五大云厂最近财年资本开支合计 $" + f"{capex_total/1e9:,.0f}B：" +
                   " · ".join(f"{c['ticker']} ${c['capex']/1e9:.0f}B({_pct(c['capex_yoy'])})" for c in capex)),
    }
    narrative = [
        "【第一性原理】AI 的本质是把电变成算力、把算力变成智能。物理链条自上而下："
        "光刻机造芯片 → 芯片提供算力 → 数据中心耗电散热 → 云出租算力 → 应用变现。"
        "钱的流向正好相反：应用付钱给云，云的资本开支变成芯片商的收入，"
        "芯片商付钱给台积电，台积电再买阿斯麦的机器。一句话：每一环的收入 = 下一环的成本。",
        f"【发动机转速】五大云厂资本开支合计 {capex_total/1e8:,.0f} 亿美元，平均同比 {_pct(capex_yoy)}——这就是整条链的总订单。",
        f"【传导现状】云 capex {_pct(capex_yoy)} → AI 芯片收入 {_pct(chip_g)} → 设备收入 {_pct(equip_g)} → 电力收入 {_pct(power_g)}。"
        "设备和电力的增速天然滞后芯片 2-4 个季度，增速逐环递减是正常形态；若芯片层增速跌破云 capex 增速，说明下游开始消化库存，要警惕。",
        "【看哪一环】瓶颈环节议价权最强。当下公认的三个瓶颈：HBM 内存、先进封装 CoWoS、电力供应。瓶颈解除之日往往是该环节超额利润见顶之时。",
        "【风险提示】资本开支是强周期变量：云厂一旦放缓 capex，会沿产业链逐级放大（长鞭效应）——"
        "离最终需求越远的环节（设备、电力基建）波动越猛。盯紧每季度云厂财报电话会里的 capex 指引。",
    ]
    research = _industry_research("US", {
        "capex_yoy": _pct(capex_yoy),
        "chip_growth": _pct(chip_g),
        "equipment_growth": _pct(equip_g),
        "power_growth": _pct(power_g),
    })
    return disk_cache_save(_DATA_DIR / "chain_us.json",
                           {"market": "US", "title": "美股 AI 产业链", "layers": layers,
                            "transmission": transmission, "narrative": narrative,
                            "research": research,
                            "n_companies": sum(len(l["companies"]) for l in layers)})


@cached(21600)
def build_chain_cn() -> dict:
    """A股 AI 链：出海卖铲人 + 国产替代双逻辑。"""
    cached_result = disk_cache_load(_DATA_DIR / "chain_cn.json", 21600)
    if cached_result is not None and cached_result.get("research"):
        return cached_result
    layers, growth = _build_layers(CN_CHAIN)
    with ThreadPoolExecutor(max_workers=7) as ex:
        us_capex = [c for c in ex.map(_capex_yoy, US_HYPERSCALERS) if c]
        cn_capex = [c for c in ex.map(_capex_yoy, CN_CARRIERS) if c]
    us_capex_yoy = _avg([c["capex_yoy"] for c in us_capex])
    cn_capex_yoy = _avg([c["capex_yoy"] for c in cn_capex])
    cn_capex_total = sum(c["capex"] for c in cn_capex)

    optics_g = _layer_growth(layers, "光模块与光通信")
    pcb_g = _layer_growth(layers, "PCB 高多层板")
    chip_g = _layer_growth(layers, "国产算力芯片")
    equip_g = _layer_growth(layers, "半导体设备")

    transmission = {
        "steps": [
            {"label": "☁️ 美国云厂 capex", "value": _pct(us_capex_yoy), "note": "出海链的发动机"},
            {"label": "🔆 光模块收入", "value": _pct(optics_g), "note": "出海链皇冠"},
            {"label": "🟫 PCB 收入", "value": _pct(pcb_g), "note": "AI 衍生需求"},
            {"label": "🧠 国产芯片收入", "value": _pct(chip_g), "note": "国产替代引擎"},
            {"label": "🔧 国产设备收入", "value": _pct(equip_g), "note": "制裁越狠订单越满"},
        ],
        "detail": (f"国内运营商资本开支合计 ¥{cn_capex_total/1e9:,.0f}B（同比 {_pct(cn_capex_yoy)}），"
                   "是国产链的可见引擎；字节/阿里/腾讯的 AI capex 不在 A股披露口径内，国产链真实需求大于运营商口径。"),
    }
    narrative = [
        "【A股链的第一性原理】A股 AI 公司赚的是两种完全不同的钱——看任何一家公司前先问这个问题。"
        "① 出海卖铲人（光模块/PCB/服务器代工）：客户是英伟达和美国云厂，跟的是全球 AI 资本开支周期，"
        "本质上是'美国 AI 故事的供应链'；② 国产替代（国产 GPU/代工/设备）：引擎是制裁倒逼 + 国内智算投资，"
        "跟的是政策与安全逻辑，和全球周期可以脱钩甚至反向（制裁升级反而利好）。",
        f"【出海链现状】美国云厂 capex 同比 {_pct(us_capex_yoy)} → A股光模块层收入同比 {_pct(optics_g)}、"
        f"PCB 层 {_pct(pcb_g)}。光模块是 A股在全球 AI 链里议价权最强的环节（份额 60%+，800G/1.6T 技术领先），"
        "但单一客户集中度高——英伟达架构每一次迭代（光铜之争、CPO）都是它的生死命题。",
        f"【国产链现状】国产算力芯片层收入同比 {_pct(chip_g)}、设备层 {_pct(equip_g)}。"
        "性能与英伟达有代差，但在'能买到的最好国产货'逻辑下订单确定性极强；"
        "瓶颈在中芯国际的先进制程产能——这是国产链的'台积电时刻'。",
        "【AI 衍生产业】除了光通信，AI 还在重塑这些 A股行业：PCB（GPU 板卡 20+ 层高速板单价数倍）、"
        "液冷（高功率机柜逼出渗透率拐点）、IDC（智算中心批发）、电力设备——逻辑同美股电力层，"
        "需求都是 AI 数据中心的物理衍生品。",
        "【风险提示】出海链的风险是美国 capex 周期 + 技术路线切换（CPO 光电共封装可能重构光模块价值链）+ 地缘政策；"
        "国产链的风险是估值（用'故事'定价而非盈利）与产能爬坡速度。两条逻辑都不便宜，仓位管理比选股更重要。",
    ]
    research = _industry_research("CN", {
        "us_capex_yoy": _pct(us_capex_yoy),
        "cn_capex_yoy": _pct(cn_capex_yoy),
        "optics_growth": _pct(optics_g),
        "pcb_growth": _pct(pcb_g),
        "chip_growth": _pct(chip_g),
        "equipment_growth": _pct(equip_g),
    })
    return disk_cache_save(_DATA_DIR / "chain_cn.json",
                           {"market": "CN", "title": "A股 AI 产业链", "layers": layers,
                            "transmission": transmission, "narrative": narrative,
                            "research": research,
                            "n_companies": sum(len(l["companies"]) for l in layers)})
