# 明白股 · mingbaigu

**用人话把一只股票、一条产业链、一个判断讲清楚的开源投研工具。美股 + A股。**
*A plain-language, honesty-first stock & supply-chain research tool for retail investors. US + China A-shares.*

🌏 线上：**[mingbaigu.com](https://mingbaigu.com)** ｜ 日报入口 [renhuagu.com](https://renhuagu.com)

![stack](https://img.shields.io/badge/stack-FastAPI%20%2B%20React-blue)
![ml](https://img.shields.io/badge/ML-scikit--learn-orange)
![llm](https://img.shields.io/badge/LLM-Claude-8a5cf6)
![data](https://img.shields.io/badge/data-Yahoo%20%2B%20FDIC%20%2B%20Tushare-green)
![license](https://img.shields.io/badge/license-AGPL--3.0-red)

---

## 这是什么

这**不是交易终端，是一个低门槛的信息决策平台**。

散户真正缺的不是行情速度，是"看得懂的判断依据"。过高的时效性不创造价值，只制造焦虑。所以这个项目有一条贯穿所有功能的**产品宪法**：

- ❌ 不荐股、不喊单、不给仓位/目标价/涨幅承诺、不做秒级刷新与倒计时
- ✅ 优先做"钩子"（散户热度、产业链联想、体质测试）和"讲明白"（一页看懂、说人话）
- ✅ 模型与回测的真实战绩、数据时效，都用不喧哗的方式**如实标注**，跑输基准就照实显示
- 🧭 口号：**这里帮你想清楚，不帮你着急。**

> ⚠️ 所有输出均为概率性参考与信息整理，**不构成投资建议**。

---

## 功能

### 看懂「一只股票」
- **一页看懂个股** — 行情 + 估值/盈利基本面 + 风险指标（波动率、最大回撤、夏普、VaR、Beta），最后用人话合成一段"这是家什么公司 → 生意现状 → 市场定价 → 多空力量 → 你该知道的底线"。
- **多空对抗验证** — 多头分析师 vs 空头分析师从技术面/消息面/基本面/模型四个维度互找证据，裁判综合论据强度与模型样本外战绩裁决；证据矛盾或模型无真实优势时**主动压低置信度**。
- **机器学习预判** — 梯度提升（HistGradientBoosting）+ 技术面特征，walk-forward 样本外回测，并对照"无脑看多"基准披露真实优势（通常只有几个百分点，照实说）。
- **消息面研判** — 多源抓取（Yahoo / Google News / 东方财富 7×24 / 中文财经媒体）→ 金融事件抽取（评级/业绩/指引/并购/回购/分红等 20+ 类）→ 半衰期加权 → 五档涨跌信号。英文/中文情绪由独立的 **FinBERT 微服务**打分（见下），未接通时优雅退回词典法。
- **财报拆解（任意公司）** — 输入 `AAPL / 茅台 / 特斯拉`，自动抓三大报表，拆成五个人话问题：生意做多大了 / 真能赚钱吗 / 利润是真是假 / 会不会暴雷 / 对股东大方吗。
- 内部人交易（SEC Form 4）、机构持仓与 13F、财报日历 + 期权隐含波动等辅助面板。

### 想清楚「一个判断」
- **论点拆解（AI）** — 说一句你对当下的判断（"锂价见底了，看好锂电链"），AI 以平台真实产业链与实证传导数据为**地基**，把它拆成：核心假设 → 多空证据 → 标的×与判断的关系 → 情景敏感度 → **怎么验证 + 一条证伪触发**。只能用数据目录里的真实标的，不编；强制看反面、给认错条件。

### 看懂「一条产业链」
- **产业链图谱** — 一条链下游→上游分层铺开，标出真正有定价权的卡点环节与代表公司，点公司直达财报拆解。
- **实证传导** — 用单季毛利率（去累计）对大宗商品期货价格做相关性，验证"上游涨价是否真传导到某环节"（锂/铜/铝/金等多条链，季度数 < 阈值的链诚实标注"样本不足"）。A股数据走 **Tushare MCP Server**（服务端消费 token，绕开 IP 绑定）。

### 别踩坑 & 看懂大盘情绪
- **炒股体质测试** — 12 个真实场景测出你的投资人格与最易栽的坑，生成可分享的体质卡。
- **恐惧贪婪指数** — 自建（非 CNN）：市场动量/波动/避险需求/垃圾债胃口/广度多维合成 0–100，含 NaN 容错与覆盖度过滤。
- **说人话学堂** — 高级金融概念的路人版讲解（期权=车险、备兑=收房租…），每条强制带"最大风险"与"常见误区"——只讲好处的科普是销售话术。
- **今日人话日报** — 三分钟看懂今天的市场，不堆术语。

### 分发
- **统一分享卡引擎** — 任意洞见 → 1080×1440 品牌竖图 PNG + 自动配好的小红书/微信文案 + 真二维码。**手机端**弹出"长按存到相册"浮层（小红书不收浏览器直传的文件），桌面端走系统分享/下载。

> 🔒 **默认隐藏的"终端类"功能**：持仓管理 / IBKR 提案式交易 / 价格提醒 / 量化组合（SPY 前 100 多因子）/ A股 smart-beta / 公开成绩单 / AI 泡沫指数。
> 它们**代码完整保留**，只是为 0.1 版精简分发在前端关掉了入口（见 [功能开关](#功能开关)），随时可一键恢复。

---

## 技术栈

| 层 | 选型 |
|----|------|
| 后端 | **FastAPI** (Python 3.12)，yfinance / pandas / numpy / scikit-learn / scipy |
| 前端 | **React + Vite**（无 UI 框架，手写 CSS），canvas 出图，PWA |
| LLM | **Claude**（Anthropic）：论点拆解、人话日报。统一走 `ai_budget` 电表，按真实 token 计费，超 `$1/天`（可配）自动熔断 |
| 情绪模型 | 独立 **FinBERT 微服务**（`sentiment_service/`）：英文 FinBERT + 中文 FinBERT2（微调 acc≈93%），单独部署 |
| 数据 | Yahoo Finance、FDIC BankFind、SEC EDGAR/Form 4、东方财富、Tushare(MCP)、可选 Finnhub |
| 部署 | **Fly.io** + Docker（主站一个 app，情绪服务一个 app）|

这是一个 **monorepo**：`backend/`（API + 模型 + 分析）、`frontend/`（React）、`sentiment_service/`（FinBERT 独立服务）。

---

## 快速开始

需要 **Python 3.12** 与 **Node 18+**。

```bash
git clone https://github.com/tuowmhz/StockPrediction.git
cd StockPrediction
./run.sh          # 首次自动建 venv + 装依赖，再起前后端
```

打开 http://localhost:5173 即可。不配任何密钥也能跑——依赖 LLM 的功能（论点拆解、日报）会优雅降级提示"未配置"。

<details>
<summary>手动分开启动</summary>

```bash
# 后端（:8000）
cd backend && python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000

# 前端（:5173，另开终端）
cd frontend && npm install && npm run dev
```
</details>

### 测试

```bash
cd backend && .venv/bin/python -m pytest tests/ -v
```

GitHub Actions 在每次 push 跑后端测试 + 前端构建。

---

## 环境变量

全部**可选**——缺了只是关掉对应能力，核心行情/分析照常。后端从环境或 `backend/.env` 读取。

| 变量 | 作用 |
|------|------|
| `ANTHROPIC_API_KEY` | 开启 AI 论点拆解 / 人话日报 |
| `AI_DAILY_BUDGET_USD` | AI 每日预算熔断阈值，默认 `1.0`（UTC 零点滚动）|
| `CLAUDE_ANALYST_MODEL` | 论点拆解模型，默认 `claude-sonnet-4-6` |
| `CLAUDE_DIGEST_MODEL` | 日报模型 |
| `SENTIMENT_URL` | FinBERT 微服务地址（不设则情绪走词典法）|
| `TS_TOKEN` | Tushare token（A股实证传导数据）|
| `FINNHUB_KEY` | 个股新闻升级为结构化 API（可选）|
| `ADMIN_TOKEN` | owner 流量看板 `?view=traffic` 的访问令牌（不设则该端点 fail-closed 403）|
| `AUTH_SECRET` | 账号相关签名密钥 |

---

## 功能开关

为"分发精简"把终端类功能在前端隐藏，**代码不删**：

- `frontend/src/features.js` — `portfolio / quant / ashare / record` 改 `true` 即恢复对应入口（导航 + 视图 + 深链）。
- `IS_RENHUAGU` — 按域名（`renhuagu.*`）切换为"日报优先"入口与品牌名（人话股）。

改完 `npm run build` 重新部署即可。

---

## 部署

主站与情绪服务各自一个 Fly.io app（Docker 构建）：

```bash
fly deploy --ha=false                  # 主站（仓库根）
cd sentiment_service && fly deploy     # FinBERT 情绪服务
```

---

## 主要 API

| 端点 | 说明 |
|------|------|
| `GET /api/stock/{ticker}` | 完整个股分析：行情/基本面/风险/新闻/预测/对抗/人话 |
| `GET /api/earnings/{query}` | 财报拆解（支持代码/中文名/模糊搜索）|
| `GET /api/thesis?q=...` | 论点拆解：一句判断 → 多空 + 标的 + 验证（数据为地基）|
| `GET /api/sectors` | 产业链图谱（含实证传导）|
| `GET /api/fear-greed` | 自建恐惧贪婪指数 |
| `GET /api/quiz` · `POST /api/quiz` | 炒股体质测试题目 / 评分 |
| `GET /api/news/{market\|ai\|cn}` | 多源要闻聚合 + 事件抽取 |
| `GET /api/ai-budget` | AI 电表状态（已花/预算/是否熔断）|

---

## 目录结构

```
backend/app/
├── main.py            # FastAPI 路由
├── ai_budget.py       # Claude 调用电表 + 每日预算熔断
├── auth.py            # 令牌校验（owner 看板等）
├── cache.py           # TTL 内存缓存 + 磁盘缓存
├── academy.py         # 说人话学堂内容
├── data/              # market / news / banks 抓取
├── ml/                # 特征工程(防未来函数) + 梯度提升 + walk-forward
├── analysis/
│   ├── thesis.py      # 论点拆解（LLM + 真实数据目录约束）
│   ├── transmission.py# 实证传导（Tushare MCP）
│   ├── fear_greed.py  # 自建恐惧贪婪指数
│   ├── sectors.py     # 产业链图谱
│   ├── adversarial.py # 多空对抗 + 裁判
│   ├── news_signal.py # 事件抽取 + 时间衰减 → 涨跌研判
│   ├── risk.py        # 波动率/回撤/夏普/VaR/Beta
│   └── explain.py     # 人话解读
└── quant/             # 量化管线（SPY 前 100，默认隐藏）

frontend/src/
├── App.jsx            # 入口 + 路由 + 头部
├── shareCard.js       # 统一分享卡引擎（出图 + 文案 + 分发）
├── features.js        # 功能开关
└── components/        # HomeFeed / ThesisView / SectorsView / StockDetail / PitfallQuiz …

sentiment_service/     # 独立 FinBERT 情绪微服务（英文 FinBERT + 中文 FinBERT2）
```

---

## 诚实声明（重要）

- **量化回测只含价格因子**：免费数据没有历史时点财报，财报因子强行回测会引入前视偏差，故只参与当前打分。用今天的成分股回测历史还有幸存者偏差，结果偏乐观——界面会主动点破而非邀功。
- 股价短期走势接近随机游走；模型回测的"优势"通常只有几个百分点，且可能随市场消失。界面**如实展示样本外命中率 vs 无脑基准**，从不隐藏。
- 对抗验证的意义：证据矛盾或模型没有真实优势时，主动降低置信度，提醒你别上头。
- 一切输出**不构成投资建议**。投资有风险，决策请独立判断、控制仓位。

---

## 数据源

[Yahoo Finance](https://finance.yahoo.com)（via yfinance）· [FDIC BankFind](https://banks.data.fdic.gov/docs/) · [SEC EDGAR](https://www.sec.gov/edgar) · 东方财富 · [Tushare](https://tushare.pro)（via MCP）· 可选 [Finnhub](https://finnhub.io)。

---

## 贡献

欢迎 issue / PR。改动前请跑通 `pytest` 与 `npm run build`；新功能请遵循上面的**产品宪法**（不荐股、诚实标注、不制造焦虑）。

## 开源协议

**[AGPL-3.0](LICENSE)**。你可以自由使用、修改、分发；但**若把（修改后的）本项目作为网络服务对外提供，必须同样开源你的修改**。商业自营不受限——作者自己运营 mingbaigu.com 即属此列。
