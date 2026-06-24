"""StockPrediction 后端 API。

GET /api/watchlist        跟踪列表（报价 + 30 日走势）
GET /api/summary/{t}      单只股票的轻量分析（预测 + 对抗裁决），给卡片角标用
GET /api/stock/{t}        完整分析：行情/基本面/风险/新闻/预测/对抗验证/人话解释
"""
import json
import math
from concurrent.futures import ThreadPoolExecutor

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .analysis.adversarial import run_adversarial
from .analysis.chain import build_chain, build_chain_cn
from .analysis.earnings import get_earnings
from .analysis.fear_greed import get_fear_greed
from .analysis.explain import (explain_bank, explain_fundamentals, explain_news,
                               explain_prediction, explain_risk, synthesize)
from .analysis.news_signal import analyze_news
from .analysis.risk import compute_risk
from .cache import cached
from .config import (CATEGORY_MAP, CURRENCY_OF, NAME_MAP, WATCHLIST,
                     market_of)
from .data.banks import get_bank_financials
from . import alerts_engine, auth, broker, portfolio, track
from .academy import get_academy
from .data.edgar13f import get_famous_13f
from .data.holders import get_holders
from .data.insider import get_insider
from .data.macro_news import get_ai_news, get_cn_news, get_market_news
from .data.options_view import get_event_view
from .data.market import get_fundamentals, get_history, history_to_series, latest_quote
from .data.news import get_news
from .ml.features import tech_snapshot
from .ml.model import predict
from .quant.pipeline import build_status, load_artifact, refresh_async

def _nan_clean(o):
    """递归把 NaN/Inf 转成 null：金融数据源到处藏着 NaN，统一在出口兜底。"""
    if isinstance(o, dict):
        return {k: _nan_clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_nan_clean(v) for v in o]
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    return o


class SafeJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(_nan_clean(content), ensure_ascii=False,
                          allow_nan=False, separators=(",", ":")).encode("utf-8")


app = FastAPI(title="StockPrediction API", version="1.0",
              default_response_class=SafeJSONResponse)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.middleware.gzip import GZipMiddleware  # noqa: E402
app.add_middleware(GZipMiddleware, minimum_size=500)  # 压缩大 JSON(如产业链图谱)，加快传输

DISCLAIMER = (
    "本工具基于公开数据与统计模型，所有预测均为概率性参考，不构成投资建议。"
    "股价短期走势接近随机，任何模型都无法精确预测，请独立判断、控制仓位。"
)


@app.on_event("startup")
def _start_alerts():
    alerts_engine.start_checker()


@app.on_event("startup")
def _start_cache_warmer():
    """后台预热重缓存：部署/重启后台线程先把重端点算热；TTL 到期也由后台巡检重算，
    让用户首次进入各板块不再干等几十秒（恐惧贪婪~54s、日报~37s、AI链~26s 等）。"""
    import threading
    import time

    def _warm_once():
        from .analysis.sectors import get_sectors
        from .analysis.fear_greed import get_fear_greed
        from .analysis.ai_bubble import get_ai_bubble
        from .analysis.chain import build_chain, build_chain_cn
        from .brief import build_brief
        for fn in (get_sectors, get_fear_greed, get_ai_bubble,
                   build_chain, build_chain_cn, build_brief):
            try:
                fn()
            except Exception:
                pass
        # 首页热门票也预热（暖各自的行情/新闻/基本面子缓存，常点的票秒开）
        try:
            for t in _hot_us(6):
                try:
                    stock_detail(t)
                except Exception:
                    pass
        except Exception:
            pass

    def _loop():
        time.sleep(5)  # 让进程先就绪
        while True:
            _warm_once()        # 新鲜则秒回；过期则此后台线程重算，不让用户等
            time.sleep(720)     # 每 12 分钟巡检一次

    threading.Thread(target=_loop, daemon=True, name="cache-warmer").start()


def _mount_frontend():
    """生产部署时由 FastAPI 直接伺服前端构建产物（单容器）。

    缓存策略：index.html 必须每次回源校验（否则发新版后老用户卡在旧页面），
    /assets/ 下的文件名带内容哈希，可以放心长缓存。
    """
    from pathlib import Path
    here = Path(__file__).resolve()
    for cand in (here.parent.parent / "frontend" / "dist",          # 容器内
                 here.parent.parent.parent / "frontend" / "dist"):  # 本地
        if cand.exists():
            from fastapi.staticfiles import StaticFiles

            class CacheAwareStatic(StaticFiles):
                async def get_response(self, path, scope):
                    resp = await super().get_response(path, scope)
                    if path.startswith("assets/"):
                        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
                    else:
                        resp.headers["Cache-Control"] = "no-cache"
                    return resp

            app.mount("/", CacheAwareStatic(directory=cand, html=True), name="frontend")
            break


@app.get("/api/health")
def health():
    return {"status": "ok"}


# —— 持仓管理 ——

@app.get("/api/portfolio")
def portfolio_view(advice: bool = True, uid: str = Depends(auth.current_uid)):
    return portfolio.get_portfolio(with_advice=advice, uid=uid)


@app.post("/api/portfolio/settings")
def portfolio_settings(body: dict = Body(...), uid: str = Depends(auth.current_uid)):
    return portfolio.set_settings(float(body.get("initial_cash", 0)), uid=uid)


@app.post("/api/portfolio/transaction")
def portfolio_add_tx(body: dict = Body(...), uid: str = Depends(auth.current_uid)):
    for field in ("ticker", "side", "shares", "price", "date"):
        if not body.get(field):
            raise HTTPException(422, f"缺少字段: {field}")
    if body["side"] not in ("buy", "sell"):
        raise HTTPException(422, "side 必须是 buy 或 sell")
    return portfolio.add_transaction(body["ticker"], body["side"],
                                     body["shares"], body["price"], body["date"], uid=uid)


@app.delete("/api/portfolio/transaction/{tx_id}")
def portfolio_del_tx(tx_id: str, uid: str = Depends(auth.current_uid)):
    if not portfolio.delete_transaction(tx_id, uid=uid):
        raise HTTPException(404, "找不到这条交易记录")
    return {"deleted": tx_id}


# —— 价格提醒 ——

@app.get("/api/alerts")
def alerts_list(uid: str = Depends(auth.current_uid)):
    return alerts_engine.list_alerts(uid)


@app.post("/api/alerts")
def alerts_add(body: dict = Body(...), uid: str = Depends(auth.current_uid)):
    try:
        return alerts_engine.add_rule(body["ticker"], body["kind"], body["value"], uid=uid)
    except (KeyError, ValueError) as e:
        raise HTTPException(422, str(e))


@app.delete("/api/alerts/{rule_id}")
def alerts_delete(rule_id: str, uid: str = Depends(auth.current_uid)):
    if not alerts_engine.delete_rule(rule_id, uid=uid):
        raise HTTPException(404, "找不到这条提醒规则")
    return {"deleted": rule_id}


@app.post("/api/alerts/seen")
def alerts_seen(uid: str = Depends(auth.current_uid)):
    alerts_engine.mark_seen(uid)
    return {"ok": True}


# —— 账号 ——

@app.post("/api/auth/register")
def auth_register(body: dict = Body(...)):
    return auth.register(body.get("email", ""), body.get("password", ""))


@app.post("/api/auth/login")
def auth_login(body: dict = Body(...)):
    return auth.login(body.get("email", ""), body.get("password", ""))


@app.post("/api/auth/delete")
def auth_delete(body: dict = Body(...)):
    """注销账号并删除全部个人数据（App Store 合规：能注册就必须能删号）。"""
    return auth.delete_account(body.get("email", ""), body.get("password", ""))


@app.get("/api/auth/status")
def auth_status():
    return {"auth_enabled": auth.auth_enabled()}


# —— 埋点与流量 ——

@app.post("/api/track")
def track_view(body: dict = Body(...), request: Request = None):
    ip = request.headers.get("Fly-Client-IP") or (request.client.host if request.client else "?")
    track.record(body.get("view", "other"), ip, request.headers.get("User-Agent", "?"),
                 source=body.get("source"), campaign=body.get("campaign"),
                 event=body.get("event"))
    return {"ok": True}


@app.get("/api/traffic")
def traffic_report(days: int = 30, _admin: bool = Depends(auth.require_admin)):
    """流量报告：owner 专用，需 ADMIN_TOKEN（X-Admin-Token 头或 ?key=）。"""
    return track.report(days)


@app.get("/api/sectors")
def sectors_endpoint():
    """产业链图谱：16+ 条产业链的下游→上游拆解 + 供给松紧 + 卡脖子环节（教育性）。"""
    from .analysis.sectors import get_sectors
    return get_sectors()


@app.get("/api/moat/{ticker}")
def moat_endpoint(ticker: str):
    """定价权/护城河评分——描述性财务画像，非涨跌预测（已诚实回测：单独不预测超额）。"""
    from .ml.moat import moat_score
    result = moat_score(_resolve_ticker(ticker))
    if result is None:
        raise HTTPException(404, f"拿不到 {ticker} 的财报数据")
    return result


@app.get("/api/fundmom/{ticker}")
def fundamental_momentum_endpoint(ticker: str):
    """基本面动量（分析师盈利预期修正）——前瞻信号，免费数据无法回测，非买卖指令。"""
    from .ml.fundamental import fundamental_momentum
    result = fundamental_momentum(_resolve_ticker(ticker))
    if result is None:
        raise HTTPException(404, f"拿不到 {ticker} 的分析师预期数据")
    return result


# —— Claude 深度解读（配 ANTHROPIC_API_KEY 即激活）——

@app.get("/api/deep/{ticker}")
def deep_analysis_endpoint(ticker: str):
    from .analysis.claude_analyst import build_context, deep_analysis, enabled
    if not enabled():
        return {"enabled": False,
                "note": "配置 ANTHROPIC_API_KEY 后，这里会由 Claude 生成深度人话研报（约$0.03/股/天）"}
    detail = stock_detail(ticker)
    as_of = detail["quote"]["as_of"]
    result = deep_analysis(f"{ticker.upper()}:{as_of}", build_context(detail))
    if result:
        return {"enabled": True, **result}
    from .ai_budget import status as ai_status
    st = ai_status()
    if st["remaining_usd"] <= 0:
        return {"enabled": True,
                "error": f"今日 AI 预算（${st['budget_usd']:.2f}）已用完，UTC 零点自动恢复。规则版'一页看懂'不受影响。"}
    return {"enabled": True, "error": "生成失败，稍后重试。"}


@app.get("/api/ai/budget")
def ai_budget_status():
    """AI 花费电表：今天花了多少、还剩多少额度。"""
    from .ai_budget import status
    return status()


# —— 公开成绩单（预测落盘 + GitHub 公证 + 到期对账）——

@app.get("/api/track-record/today")
def track_record_today():
    """当日预测快照（同日内容固定）。公证仓库的定时任务每天拉这个。"""
    from .track_record import build_today_snapshot
    return build_today_snapshot()


@app.get("/api/track-record")
def track_record():
    """对账后的成绩单：命中率 vs 无脑看多、错的不删、亏的置顶。"""
    from .track_record import build_track_record
    return build_track_record()


# —— A股低频策略·纸面跟踪 ——

@app.get("/api/strategy/ashare")
def ashare_strategy():
    """A股低频多因子「低波蓝筹」策略的纸面跟踪成绩单（公开免登录）。

    每月持仓快照先 git 公证、后对账，自建仓日起对标沪深300。只读账本，不依赖行情源。
    """
    from .quant.ashare.ledger import build_track_record
    return build_track_record()


# —— 价值投资面板 ——

@app.get("/api/value/{ticker}")
def value_panel(ticker: str):
    from .analysis.value_invest import value_analysis
    result = value_analysis(ticker.upper())
    if result is None:
        raise HTTPException(404, f"拿不到 {ticker} 的财务数据")
    return result


# —— 策略动物园 ——

@app.get("/api/zoo")
def strategy_zoo():
    from .quant.zoo import get_zoo
    return get_zoo()


# —— 说人话学堂 ——

@app.get("/api/academy")
def academy():
    return get_academy()


@app.get("/api/failures")
def failures_map():
    """跌倒地图：芒格逆向思维——所有经典死法与规避路标。"""
    from .failures import get_failures
    return get_failures()


@app.get("/api/quiz")
def quiz_questions():
    """跌倒体质测试：12 道情景题。"""
    from .profile_quiz import get_quiz
    return get_quiz()


@app.post("/api/quiz")
def quiz_score(body: dict = Body(...)):
    """提交答案 → 体质报告（人格原型 + 前三高危死法 + 处方）。"""
    from .profile_quiz import score_quiz
    result = score_quiz(body.get("answers") or {})
    if "error" in result:
        raise HTTPException(422, result["error"])
    return result


# —— IBKR 提案-审批交易 ——

@app.get("/api/broker/status")
async def broker_status():
    return await broker.status()


@app.post("/api/broker/connect")
async def broker_connect():
    return await broker.connect()


@app.post("/api/broker/settings")
def broker_settings(body: dict = Body(...)):
    return broker.save_settings(body)


@app.post("/api/broker/proposals")
async def broker_proposals():
    return await broker.generate_proposals()


@app.post("/api/broker/execute")
async def broker_execute(body: dict = Body(...)):
    ids = body.get("ids") or []
    if not ids:
        raise HTTPException(422, "没有勾选任何提案")
    return await broker.execute(ids, acknowledge_live=bool(body.get("acknowledge_live")))


# —— 13F 大佬持仓 ——

@app.get("/api/13f")
def famous_13f():
    return get_famous_13f()


@app.get("/api/news/market")
def market_news():
    """宏观要闻：CNBC + MarketWatch + CNN + Google News 聚合。"""
    result = get_market_news()
    if result is None:
        raise HTTPException(503, "暂时抓不到宏观新闻，稍后重试")
    return result


@app.get("/api/news/ai")
def ai_news():
    """AI 产业链专题要闻。"""
    result = get_ai_news()
    if result is None:
        raise HTTPException(503, "暂时抓不到 AI 专题新闻，稍后重试")
    return result


@app.get("/api/news/cn")
def cn_news():
    """A股实时要闻：东方财富 7×24 快讯 + Google 中文财经。"""
    result = get_cn_news()
    if result is None:
        raise HTTPException(503, "暂时抓不到 A股快讯，稍后重试")
    return result


@app.get("/api/chain/ai")
def ai_chain(market: str = "US"):
    """AI 产业链图谱：分层公司 + 财报传导分析 + 第一性原理解读。

    market=US 美股链；market=CN A股链（出海卖铲人 + 国产替代双逻辑）。
    """
    return build_chain_cn() if market.upper() == "CN" else build_chain()


@app.get("/api/earnings/{query}")
def earnings(query: str):
    """财报拆解：输入任意美股代码或公司名（如 AAPL / 苹果 / nike）。"""
    result = get_earnings(query)
    if result is None:
        raise HTTPException(404, f"找不到「{query}」的财报数据，请尝试输入美股代码（如 AAPL）")
    return result


@app.get("/api/longterm")
def longterm():
    """一年期展望：个股未来 12 个月 vs QQQ 的超额收益预测 + 样本外战绩。"""
    from .quant.longterm import build_longterm
    return build_longterm()


@app.get("/api/quant")
def quant_results():
    """量化管线结果（因子/回测/排名/组合）。无缓存结果时自动触发后台构建。"""
    artifact = load_artifact()
    status = build_status()
    if artifact is None:
        refresh_async()
        return {"status": "building", "error": status["error"]}
    return {"status": "ready", "building": status["running"],
            "error": status["error"], **artifact}


@app.post("/api/quant/refresh")
def quant_refresh():
    started = refresh_async()
    return {"started": started, **build_status()}


def _quote_card(ticker: str) -> dict | None:
    df = get_history(ticker, period="2y")
    if df is None:
        return None
    quote = latest_quote(df)
    spark = [round(float(v), 2) for v in df["Close"].tail(30)]
    return {
        "ticker": ticker,
        "name_cn": NAME_MAP.get(ticker, ticker),
        "category": CATEGORY_MAP.get(ticker, "other"),
        "currency": CURRENCY_OF[market_of(ticker)],
        **quote,
        "sparkline": spark,
    }


def _res(future, default=None):
    """取并行任务结果——单个数据源抛错时降级为 default，不连累整个响应。"""
    try:
        return future.result()
    except Exception:
        return default


def _safe_quote(ticker):
    try:
        return _quote_card(ticker)
    except Exception:
        return None


# 首页美股池：流动性强 + 散户活跃的代表性标的，按"近期成交额 + 放量"实时排序取热门
HOT_US_POOL = [
    "NVDA", "TSLA", "AAPL", "AMD", "AMZN", "MSFT", "META", "GOOGL", "NFLX", "AVGO",
    "PLTR", "MU", "INTC", "COIN", "SMCI", "MARA", "SOFI", "F", "BAC", "NIO",
    "BABA", "UBER", "SHOP", "DIS", "PFE", "NKE", "QCOM", "MRVL", "ARM", "CRM",
]


@cached(1800)  # 30 分钟刷新一次足够
def _hot_us(n: int = 12) -> list[str]:
    """按"近 5 日成交额 + 放量(5日量/60日量)"综合排序，选出近期最活跃的美股。"""
    import numpy as np
    with ThreadPoolExecutor(max_workers=8) as ex:
        hist = list(ex.map(lambda t: (t, get_history(t, period="2y")), HOT_US_POOL))
    rows = []
    for t, df in hist:
        if df is None or len(df) < 70:
            continue
        v = df["Volume"].astype(float); c = df["Close"].astype(float)
        dvol = float((c.tail(5) * v.tail(5)).mean())            # 近 5 日日均成交额
        v5, v60 = float(v.tail(5).mean()), float(v.tail(60).mean())
        surge = v5 / v60 if v60 > 0 else 1.0                    # 放量倍数
        if dvol > 0:
            rows.append((t, dvol, surge))
    if not rows:
        return HOT_US_POOL[:n]

    def _z(a):
        s = a.std()
        return (a - a.mean()) / s if s > 0 else a * 0.0
    dv = np.array([r[1] for r in rows]); sg = np.array([r[2] for r in rows])
    score = _z(np.log(dv + 1.0)) + _z(sg)                       # 成交额 + 放量 各半
    return [rows[i][0] for i in np.argsort(-score)[:n]]


@app.get("/api/watchlist")
def watchlist():
    """首页：美股按近期成交额/放量排出的热门 + A股人气榜热门（已去掉固定银行/权重池）。"""
    from .data.retail_heat import get_retail_heat
    us = _hot_us(12)
    cn_names = {}
    try:
        heat = get_retail_heat(10) or {}
        for it in (heat.get("items") or [])[:10]:
            cn_names[it["ticker"]] = it.get("name")
    except Exception:
        pass
    cn = list(cn_names.keys())

    def _card(ticker, cat):
        c = _safe_quote(ticker)
        if c:
            c["category"] = cat
            if cat == "cn" and cn_names.get(ticker):   # 用人气榜解析出的中文名
                c["name_cn"] = cn_names[ticker]
        return c

    with ThreadPoolExecutor(max_workers=8) as ex:
        us_cards = list(ex.map(lambda t: _card(t, "us"), us))
        cn_cards = list(ex.map(lambda t: _card(t, "cn"), cn))
    stocks = [c for c in us_cards + cn_cards if c]
    return {"stocks": stocks, "disclaimer": DISCLAIMER}


@app.get("/api/heat")
def retail_heat():
    """散户热度榜（东方财富股吧人气榜）。"""
    from .data.retail_heat import get_retail_heat
    result = get_retail_heat()
    if result is None:
        raise HTTPException(503, "热度榜暂时不可用")
    return result


@app.get("/api/digest")
def daily_digest():
    """每日财经爆款精选（跨源共振排序，Newsletter 内容引擎）。"""
    from .data.digest import build_digest
    result = build_digest()
    if result is None:
        raise HTTPException(503, "爆款精选暂时不可用")
    return result


@app.get("/api/brief")
def daily_brief():
    """每日人话简报（Newsletter 引擎）：三分钟看懂今天。"""
    from .brief import build_brief
    return build_brief()


@app.get("/api/market/sentiment")
def market_sentiment():
    """恐惧贪婪指数（自研五成分，CNN 同源方法论）。"""
    result = get_fear_greed()
    if result is None:
        raise HTTPException(503, "市场情绪数据暂时不可用")
    return result


@app.get("/api/ai-bubble")
def ai_bubble():
    """AI 泡沫指数（诚实免费版：龙头 vs 故事股质量结构，不构成投资建议）。"""
    from .analysis.ai_bubble import get_ai_bubble
    result = get_ai_bubble()
    if result is None:
        raise HTTPException(503, "AI 泡沫指数数据暂时不可用")
    return result


@app.get("/api/thesis")
def thesis_endpoint(q: str):
    """论点拆解：一句判断→多空+标的+验证（数据为地基、不构成投资建议）。"""
    from .analysis.thesis import build_thesis, enabled
    if not enabled():
        raise HTTPException(503, "论点拆解需要 AI（未配置 ANTHROPIC_API_KEY）")
    res = build_thesis(q)
    if res is None:
        raise HTTPException(503, "AI 暂不可用或今日预算已用尽，稍后再试")
    return res


@app.post("/api/narrative")
def narrative_endpoint(body: dict = Body(...)):
    """叙事验证器：粘一条 KOL 荐股叙事 + A股代码 → 真伪核验卡（数据接地、不构成投资建议）。"""
    from .analysis.narrative import build_card, enabled
    if not enabled():
        raise HTTPException(503, "叙事验证需要 AI（未配置 ANTHROPIC_API_KEY）")
    ticker = (body.get("ticker") or "").strip()
    text = (body.get("text") or "").strip()
    if not ticker or not text:
        raise HTTPException(422, "需要 ticker（A股代码）和 text（叙事原文）")
    card = build_card(text, ticker)
    if not card.get("ok"):
        stage, err = card.get("stage"), card.get("error")
        if stage == "input":
            raise HTTPException(422, err)
        if stage == "config" or err == "budget_exhausted":
            raise HTTPException(503, "AI 暂不可用或今日预算已用尽，稍后再试")
        raise HTTPException(502, f"核验失败（{stage}）：{err}")
    return card


def _resolve_ticker(q: str) -> str:
    """把用户输入解析成 yfinance 代码：6 位 A股代码自动补市场后缀，中文名反查。"""
    import re
    q = q.strip()
    for tk, cn in NAME_MAP.items():
        if q == cn:
            return tk
    qu = q.upper()
    if re.fullmatch(r"\d{6}", qu):
        first = qu + (".SS" if qu.startswith("6") else ".SZ")
        if get_history(first, period="5d") is not None:
            return first
        return qu + (".SZ" if qu.startswith("6") else ".SS")
    return qu


@app.get("/api/quote/{ticker}")
def quote(ticker: str):
    """轻量报价卡片（美股代码 / A股6位代码 / 中文名），给自选股用。"""
    card = _quote_card(_resolve_ticker(ticker))
    if card is None:
        raise HTTPException(404, f"拿不到 {ticker} 的行情数据")
    return card


@app.get("/api/summary/{ticker}")
def summary(ticker: str):
    ticker = _resolve_ticker(ticker)
    df = get_history(ticker, period="2y")
    if df is None:
        raise HTTPException(404, f"拿不到 {ticker} 的行情数据")
    as_of = df.index[-1].strftime("%Y-%m-%d")
    prediction = predict(ticker, as_of)
    tech = tech_snapshot(df)
    risk = compute_risk(df, ticker)
    analyzed = analyze_news(get_news(ticker), ticker)
    signal = analyzed["signal"] if analyzed else None
    adv = run_adversarial(tech, signal, None, prediction, risk, mood=get_fear_greed())
    return {
        "ticker": ticker,
        "prediction": prediction,
        "judge": adv["judge"],
        "news_label": signal["direction_cn"] if signal else "无数据",
        "news_score": signal["score"] if signal else None,
    }


@app.get("/api/stock/{ticker}")
def stock_detail(ticker: str):
    ticker = _resolve_ticker(ticker)
    df = get_history(ticker, period="2y")
    if df is None:
        raise HTTPException(404, f"拿不到 {ticker} 的行情数据")
    as_of = df.index[-1].strftime("%Y-%m-%d")
    name = NAME_MAP.get(ticker, ticker)

    # 外部请求并行化
    with ThreadPoolExecutor(max_workers=7) as ex:
        f_news = ex.submit(get_news, ticker)
        f_fund = ex.submit(get_fundamentals, ticker)
        f_pred = ex.submit(predict, ticker, as_of)
        f_insider = ex.submit(get_insider, ticker)
        f_holders = ex.submit(get_holders, ticker)
        f_events = ex.submit(get_event_view, ticker)
        f_bank = (ex.submit(get_bank_financials, ticker)
                  if CATEGORY_MAP.get(ticker) == "bank" else None)
        news = _res(f_news)
        fundamentals = _res(f_fund)
        prediction = _res(f_pred)
        insider = _res(f_insider)
        holders = _res(f_holders)
        events = _res(f_events)
        bank = _res(f_bank) if f_bank else None

    analyzed = analyze_news(news, ticker)
    signal = analyzed["signal"] if analyzed else None
    tech = tech_snapshot(df)
    risk = compute_risk(df, ticker)
    mood = get_fear_greed()
    adv = run_adversarial(tech, signal, fundamentals, prediction, risk, mood=mood)

    from .failures import match_stock_pitfalls
    pitfalls = match_stock_pitfalls(tech, risk, signal)

    explanation = {
        "summary": synthesize(name, ticker, fundamentals, risk, adv["judge"],
                              signal, prediction, tech, mood=mood),
        "news": explain_news(analyzed, name),
        "risk": explain_risk(risk, name),
        "prediction": explain_prediction(prediction, adv["judge"], name),
        "fundamentals": explain_fundamentals(fundamentals, name),
        "bank": explain_bank(bank),
    }

    return {
        "ticker": ticker,
        "name_cn": name,
        "category": CATEGORY_MAP.get(ticker, "other"),
        "currency": CURRENCY_OF[market_of(ticker)],
        "quote": latest_quote(df),
        "series": history_to_series(df),
        "fundamentals": fundamentals,
        "risk": risk,
        "tech": tech,
        "news": analyzed or news or {},
        "prediction": prediction,
        "adversarial": adv,
        "bank": bank,
        "insider": insider,
        "holders": holders,
        "events": events,
        "pitfalls": pitfalls,
        "explanation": explanation,
        "disclaimer": DISCLAIMER,
    }


_mount_frontend()
