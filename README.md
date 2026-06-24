<div align="center">

<img src="frontend/public/logo.svg" width="92" alt="明白股 mingbaigu" />

# 明白股 · mingbaigu

**用人话把一只股票、一条产业链、一个判断讲清楚的开源投研工具**

*An honesty-first, plain-language research tool for retail investors — US stocks & China A-shares*

<br/>

[![Live](https://img.shields.io/badge/live-mingbaigu.com-2ea44f?style=flat-square)](https://mingbaigu.com)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI_·_Python_3.12-009688?style=flat-square&logo=fastapi&logoColor=white)](backend/)
[![React](https://img.shields.io/badge/frontend-React_·_Vite-61dafb?style=flat-square&logo=react&logoColor=black)](frontend/)
[![Claude](https://img.shields.io/badge/LLM-Claude-d97757?style=flat-square&logo=anthropic&logoColor=white)](backend/app/ai_budget.py)
[![FinBERT](https://img.shields.io/badge/sentiment-FinBERT_·_FinBERT2-8a5cf6?style=flat-square)](sentiment_service/)
[![License](https://img.shields.io/badge/license-AGPL--3.0-red?style=flat-square)](LICENSE)

[**在线体验 →**](https://mingbaigu.com) &nbsp;·&nbsp; [日报入口](https://renhuagu.com) &nbsp;·&nbsp; [产品宪法](#产品宪法) &nbsp;·&nbsp; [快速开始](#快速开始) &nbsp;·&nbsp; [架构](#架构)

</div>

---

> ### 这不是交易终端，是一个低门槛的信息决策平台
> 散户真正缺的不是行情速度，是"看得懂的判断依据"。过高的时效性不创造价值，只制造焦虑。
>
> **不荐股 · 不喊单 · 不给仓位/目标价 · 模型跑输基准就照实显示 · 数据拿不到就说"无法验证"**
>
> 口号：**这里帮你想清楚，不帮你着急。**

<a name="产品宪法"></a>

## 四种用法

<table>
<tr>
<td width="50%" valign="top">

### 看懂「一只股票」
行情 + 估值/盈利基本面 + 风险指标，最后用人话合成"这是家什么公司 → 生意现状 → 市场定价 → 多空力量 → 底线"。
**多空对抗验证**：多头 vs 空头四维度互找证据，裁判按论据强度 + 模型样本外战绩裁决；证据矛盾就主动压低置信度。

</td>
<td width="50%" valign="top">

### 想清楚「一个判断」
说一句你对当下的判断（"锂价见底了，看好锂电链"），AI 以真实产业链与实证传导数据为地基，拆成
**核心假设 → 多空证据 → 标的×关系 → 情景敏感度 → 怎么验证 + 一条证伪触发**。

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 核验「别人的叙事」
把一条 KOL 荐股原文 + 代码丢进去 → 拆成原子主张(事实/预测/观点) → 拉**真实 Tushare 财报/估值**接地 →
逐条 **真伪裁决**（拿不到数据只能判"无法验证"）→ 多视角对抗质检 → 可分享竖图。

</td>
<td width="50%" valign="top">

### 看懂「一条产业链」
一条链下游→上游分层铺开，标出真正有定价权的**卡点环节**与代表公司。
**实证传导**：单季毛利率对大宗商品期货价做相关性，验证"上游涨价是否真传导到某环节"。

</td>
</tr>
</table>

还有：**炒股体质测试**（12 场景测你最易栽的坑，生成可晒的体质卡）、**自建恐惧贪婪指数**、**财报拆解**（任意公司 → 五个人话问题）、**说人话学堂**（每条强制带"最大风险"与"常见误区"）、**今日人话日报**。
每个洞见都能一键出 **1080×1440 品牌竖图 + 小红书/微信文案**（`shareCard.js` 统一引擎）。

> 持仓 / IBKR 提案交易 / 价格提醒 / 量化组合 / A股 smart-beta / 公开成绩单 等"终端类"功能**代码完整保留**，
> 为 0.1 版精简分发在前端默认隐藏（见 [功能开关](#功能开关)），一键可恢复。

---

## 技术栈

| 层 | 选型 |
|---|---|
| **后端** | FastAPI（Python 3.12）· yfinance / pandas / numpy / scikit-learn / scipy |
| **前端** | React + Vite（手写 CSS，无 UI 框架）· canvas 出图 · PWA |
| **LLM** | Claude（Anthropic）——论点拆解 / 叙事验证 / 人话日报；统一走 `ai_budget` 电表，按真实 token 计费，超 `$1/天`（可配）自动熔断 |
| **情绪模型** | 独立 **FinBERT 微服务**：英文 `ProsusAI/finbert` + 自微调中文 **FinBERT2**（acc≈93%），单独部署 |
| **数据** | Yahoo Finance · FDIC BankFind · SEC EDGAR/Form 4 · 东方财富 · Tushare(MCP) · 可选 Finnhub |
| **部署** | Fly.io + Docker（主站一个 app，情绪服务一个 app）|

> Monorepo：`backend/`（API + 模型 + 分析）、`frontend/`（React）、`sentiment_service/`（FinBERT 独立服务）。

---

## 快速开始

需要 **Python 3.12** 与 **Node 18+**。

```bash
git clone https://github.com/tuowmhz/mingbaigu.git
cd mingbaigu
./run.sh          # 首次自动建 venv + 装依赖，再起前后端
```

打开 <http://localhost:5173> 即可。不配任何密钥也能跑——依赖 LLM 的功能会优雅降级提示"未配置"。

<details>
<summary><b>手动分开启动</b></summary>

```bash
# 后端（:8000）
cd backend && python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000

# 前端（:5173，另开终端）
cd frontend && npm install && npm run dev
```
</details>

<details>
<summary><b>测试</b></summary>

```bash
cd backend && .venv/bin/python -m pytest tests/ -v
```
GitHub Actions 在每次 push 跑后端测试 + 前端构建。
</details>

---

## 环境变量

全部**可选**——缺了只是关掉对应能力，核心行情/分析照常。后端从环境或 `backend/.env` 读取。

| 变量 | 作用 |
|---|---|
| `ANTHROPIC_API_KEY` | 开启 AI：论点拆解 / 叙事验证 / 人话日报 |
| `AI_DAILY_BUDGET_USD` | AI 每日预算熔断阈值，默认 `1.0`（UTC 零点滚动）|
| `TS_TOKEN` | Tushare token——A股实证传导 + 叙事验证的真实财报/估值（走 MCP，绕过 10-IP 绑定）|
| `SENTIMENT_URL` | FinBERT 微服务地址（不设则情绪走词典法）|
| `FINNHUB_KEY` | 个股新闻升级为结构化 API（可选）|
| `ADMIN_TOKEN` | owner 流量看板 `?view=traffic` 令牌（不设则该端点 fail-closed 403）|
| `CLAUDE_ANALYST_MODEL` / `CLAUDE_DIGEST_MODEL` | 模型覆盖，默认 `claude-sonnet-4-6` |

<a name="功能开关"></a>

## 功能开关

终端类功能默认隐藏、**代码不删**：

- `frontend/src/features.js` — `portfolio / quant / ashare / record` 改 `true` 即恢复入口（导航 + 视图 + 深链）。
- `IS_RENHUAGU` — 按域名（`renhuagu.*`）切换为"日报优先"入口与品牌名。

改完 `npm run build` 重新部署即可。

---

## 主要 API

| 端点 | 说明 |
|---|---|
| `GET /api/stock/{ticker}` | 完整个股分析：行情/基本面/风险/新闻/预测/对抗/人话 |
| `GET /api/earnings/{query}` | 财报拆解（支持代码/中文名/模糊搜索）|
| `GET /api/thesis?q=…` | 论点拆解：一句判断 → 多空 + 标的 + 验证 |
| `POST /api/narrative` | 叙事验证：`{ticker, text}` → 真伪核验卡（数据接地）|
| `GET /api/sectors` | 产业链图谱（含实证传导）|
| `GET /api/fear-greed` | 自建恐惧贪婪指数 |
| `GET /api/quiz` · `POST /api/quiz` | 炒股体质测试 |
| `GET /api/ai-budget` | AI 电表状态（已花 / 预算 / 是否熔断）|

---

## 架构

```
backend/app/
├── main.py            # FastAPI 路由
├── ai_budget.py       # Claude 调用电表 + 每日预算熔断（所有 AI 唯一入口）
├── cache.py           # TTL 内存缓存 + 磁盘缓存
├── data/              # market / news / banks 抓取
├── ml/                # 特征工程(防未来函数) + 梯度提升 + walk-forward
├── analysis/
│   ├── thesis.py      # 论点拆解（LLM + 真实数据目录约束）
│   ├── narrative.py   # 叙事验证（拆解→Tushare接地→裁决→对抗质检）
│   ├── transmission.py# 实证传导（Tushare MCP）
│   ├── fear_greed.py  # 自建恐惧贪婪指数
│   ├── sectors.py     # 产业链图谱
│   ├── adversarial.py # 多空对抗 + 裁判
│   ├── news_signal.py # 事件抽取 + 时间衰减 → 涨跌研判
│   └── explain.py     # 人话解读
└── quant/             # 量化管线（SPY 前 100，默认隐藏）

frontend/src/
├── App.jsx                  # 入口 + 路由 + 头部
├── shareCard.js             # 统一分享卡引擎（出图 + 文案 + 分发）
├── features.js              # 功能开关
└── components/              # HomeFeed / ThesisView / NarrativeCheckView / SectorsView / StockDetail / PitfallQuiz …

sentiment_service/           # 独立 FinBERT 情绪微服务（英文 FinBERT + 中文 FinBERT2）
```

---

## 诚实声明（重要）

- **量化回测只含价格因子**：免费数据没有历史时点财报，财报因子强行回测会引入前视偏差，故只参与当前打分。用今天的成分股回测历史还有幸存者偏差，结果偏乐观——界面主动点破而非邀功。
- 股价短期走势接近随机游走；模型回测的"优势"通常只有几个百分点，且可能随市场消失。界面**如实展示样本外命中率 vs 无脑基准**，从不隐藏。
- 叙事验证/对抗验证的意义：证据矛盾或模型没有真实优势时主动降低置信度，提醒你别上头；拿不到公开数据的主张诚实标"无法验证"，绝不用记忆补。
- 一切输出**不构成投资建议**。投资有风险，决策请独立判断、控制仓位。

## 数据源

[Yahoo Finance](https://finance.yahoo.com)（via yfinance）· [FDIC BankFind](https://banks.data.fdic.gov/docs/) · [SEC EDGAR](https://www.sec.gov/edgar) · 东方财富 · [Tushare](https://tushare.pro)（via MCP）· 可选 [Finnhub](https://finnhub.io)

## 贡献 & 协议

欢迎 issue / PR——改动前请跑通 `pytest` 与 `npm run build`，并遵循上面的**产品宪法**（不荐股、诚实标注、不制造焦虑）。

开源协议 **[AGPL-3.0](LICENSE)**：自由使用 / 修改 / 分发；但**若把（修改后的）本项目作为网络服务对外提供，必须同样开源你的修改**。商业自营不受限。

<div align="center"><sub>这里帮你想清楚，不帮你着急。</sub></div>
