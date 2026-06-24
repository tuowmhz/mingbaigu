"""IBKR 接入：提案-审批模式的策略交易。

安全设计（每一条都是刻意的）：
- 不做全自动交易：软件只生成"交易提案"，每一笔都要用户在 UI 勾选确认后才下单；
- 默认模拟账户（paper, 端口 7497）；连实盘(7496)必须显式承认风险；
- 硬护栏：单笔金额上限、只允许执行刚生成的提案（防止重放）、只交易正股不碰杠杆衍生品；
- 我们自己的回测显示策略没有稳定优势——这是工具，不是印钞机，UI 上同样写明。
"""
import asyncio
import json
import uuid
from pathlib import Path

from .analysis.adversarial import run_adversarial
from .analysis.news_signal import analyze_news
from .analysis.risk import compute_risk
from .config import NAME_MAP
from .data.market import get_history, latest_quote
from .data.news import get_news
from .ml.features import tech_snapshot
from .ml.model import predict

try:
    from ib_async import IB, LimitOrder, Stock
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False

SETTINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "trade_settings.json"

PAPER_PORT = 7497
MAX_ORDER_NOTIONAL = 25_000   # 单笔订单金额硬上限（美元）
MAX_ORDERS_PER_BATCH = 10

RISK_PROFILES = {
    "conservative": {"label": "保守", "max_position_pct": 0.05, "min_confidence": 0.30, "max_positions": 5},
    "balanced": {"label": "平衡", "max_position_pct": 0.10, "min_confidence": 0.20, "max_positions": 8},
    "aggressive": {"label": "进取", "max_position_pct": 0.15, "min_confidence": 0.10, "max_positions": 10},
}

_ib = None
_lock = asyncio.Lock()
_pending_proposals: dict[str, dict] = {}  # 只允许执行刚生成的提案


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except Exception:
            pass
    return {
        "host": "127.0.0.1", "port": PAPER_PORT, "client_id": 9,
        "risk_level": "balanced", "horizon": "short",   # short=5日信号 / long=一年期动量
        "universe": ["NVDA", "MSFT", "AAPL", "GOOGL", "AMZN"],
    }


def save_settings(patch: dict) -> dict:
    s = load_settings()
    for k in ("host", "port", "client_id", "risk_level", "horizon", "universe"):
        if k in patch and patch[k] is not None:
            s[k] = patch[k]
    if s["risk_level"] not in RISK_PROFILES:
        s["risk_level"] = "balanced"
    s["universe"] = [t.strip().upper() for t in s["universe"] if t.strip()][:20]
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=1))
    return s


async def _get_ib():
    global _ib
    if _ib is None:
        _ib = IB()
    return _ib


async def connect() -> dict:
    """连接本机 TWS / IB Gateway。失败时返回人话指引。"""
    if not IB_AVAILABLE:
        return {"connected": False, "error": "ib_async 未安装"}
    s = load_settings()
    ib = await _get_ib()
    async with _lock:
        if ib.isConnected():
            return await status()
        try:
            await ib.connectAsync(s["host"], int(s["port"]), clientId=int(s["client_id"]), timeout=6)
        except Exception as e:
            return {
                "connected": False,
                "error": f"连不上 {s['host']}:{s['port']}（{type(e).__name__}）",
                "setup_guide": [
                    "1. 安装并登录 IBKR 的 TWS 或 IB Gateway（建议先用模拟账户登录）",
                    "2. TWS 菜单 File → Global Configuration → API → Settings",
                    "3. 勾选 Enable ActiveX and Socket Clients，端口填 7497（模拟）",
                    "4. 取消勾选 Read-Only API（否则只能看不能下单）",
                    "5. 回到本页面点'连接'",
                ],
            }
    return await status()


async def status() -> dict:
    if not IB_AVAILABLE:
        return {"connected": False, "error": "ib_async 未安装"}
    ib = await _get_ib()
    s = load_settings()
    base = {"connected": ib.isConnected(), "port": s["port"],
            "mode": "模拟盘 paper" if int(s["port"]) == PAPER_PORT else "⚠️ 实盘 LIVE",
            "settings": s, "risk_profiles": {k: v["label"] for k, v in RISK_PROFILES.items()}}
    if not ib.isConnected():
        return base
    try:
        summary = await ib.accountSummaryAsync()
        vals = {v.tag: v.value for v in summary if v.tag in ("NetLiquidation", "AvailableFunds", "TotalCashValue")}
        positions = [{
            "ticker": p.contract.symbol, "shares": p.position,
            "avg_cost": round(p.avgCost, 2),
        } for p in ib.positions()]
        base.update({"account": vals, "positions": positions})
    except Exception as e:
        base["error"] = f"读取账户失败: {e}"
    return base


def _signal_for(ticker: str) -> dict | None:
    """复用全套分析管线给出信号（同步，供线程池调用）。"""
    df = get_history(ticker, period="2y")
    if df is None:
        return None
    as_of = df.index[-1].strftime("%Y-%m-%d")
    analyzed = analyze_news(get_news(ticker), ticker)
    signal = analyzed["signal"] if analyzed else None
    adv = run_adversarial(tech_snapshot(df), signal, None, predict(ticker, as_of),
                          compute_risk(df, ticker))
    quote = latest_quote(df)
    close = df["Close"]
    mom_12 = float(close.iloc[-1] / close.iloc[-252] - 1) if len(close) > 252 else None
    return {
        "ticker": ticker, "price": quote["price"],
        "verdict": adv["judge"]["verdict"], "verdict_cn": adv["judge"]["verdict_cn"],
        "confidence": adv["judge"]["confidence"],
        "news": signal["direction_cn"] if signal else "无数据",
        "mom_12": mom_12,
    }


async def generate_proposals() -> dict:
    """按设置生成买卖提案。只生成，不执行。"""
    global _pending_proposals
    s = load_settings()
    profile = RISK_PROFILES[s["risk_level"]]
    st = await status()
    if not st.get("connected"):
        return {"error": "未连接 IBKR——先在上方连接（建议模拟账户）", "proposals": []}

    funds = float(st.get("account", {}).get("AvailableFunds", 0) or 0)
    held = {p["ticker"]: p for p in st.get("positions", [])}
    universe = list(dict.fromkeys(s["universe"] + list(held.keys())))

    signals = await asyncio.gather(*[asyncio.to_thread(_signal_for, t) for t in universe])
    signals = [x for x in signals if x]

    proposals = []
    # 卖出提案：持仓中裁决偏空的
    for sig in signals:
        pos = held.get(sig["ticker"])
        if pos and sig["verdict"] == "bearish" and sig["confidence"] >= 0.15 and pos["shares"] > 0:
            proposals.append({
                "action": "SELL", "ticker": sig["ticker"], "qty": int(pos["shares"]),
                "est_price": sig["price"],
                "reason": f"对抗验证裁决偏空（置信度 {sig['confidence']*100:.0f}%），消息面{sig['news']}",
            })

    # 买入提案：未持有/未满仓的偏多标的，按置信度或动量排序
    candidates = [x for x in signals
                  if x["verdict"] == "bullish" and x["confidence"] >= profile["min_confidence"]
                  and x["ticker"] not in held]
    key = (lambda x: -(x["mom_12"] or 0)) if s["horizon"] == "long" else (lambda x: -x["confidence"])
    candidates.sort(key=key)
    budget_per = min(funds * profile["max_position_pct"], MAX_ORDER_NOTIONAL)
    slots = max(0, profile["max_positions"] - len(held))
    for sig in candidates[:slots]:
        qty = int(budget_per // sig["price"]) if sig["price"] else 0
        if qty < 1:
            continue
        horizon_note = "12月动量靠前" if s["horizon"] == "long" else f"短线置信度 {sig['confidence']*100:.0f}%"
        proposals.append({
            "action": "BUY", "ticker": sig["ticker"], "qty": qty,
            "est_price": sig["price"],
            "reason": f"裁决偏多（{horizon_note}），消息面{sig['news']}，预算 {profile['label']}档 {profile['max_position_pct']*100:.0f}%",
        })

    _pending_proposals = {}
    for p in proposals[:MAX_ORDERS_PER_BATCH]:
        pid = uuid.uuid4().hex[:8]
        p["id"] = pid
        p["notional"] = round(p["qty"] * p["est_price"], 2)
        _pending_proposals[pid] = p

    return {
        "proposals": list(_pending_proposals.values()),
        "funds": funds,
        "profile": profile["label"],
        "note": ("提案基于公开数据信号，不构成投资建议。我们的回测显示策略没有稳定优势——"
                 "请逐笔审查，强烈建议先在模拟账户运行数周。"),
    }


async def execute(proposal_ids: list[str], acknowledge_live: bool = False) -> dict:
    """执行用户勾选的提案。限价单（按现价±0.2%），逐笔护栏检查。"""
    ib = await _get_ib()
    s = load_settings()
    if not ib.isConnected():
        return {"error": "未连接 IBKR"}
    if int(s["port"]) != PAPER_PORT and not acknowledge_live:
        return {"error": "当前连接的是实盘端口——必须勾选'我已知晓实盘风险'才能执行"}

    results = []
    for pid in proposal_ids[:MAX_ORDERS_PER_BATCH]:
        p = _pending_proposals.pop(pid, None)
        if p is None:
            results.append({"id": pid, "status": "rejected", "msg": "提案不存在或已过期，请重新生成"})
            continue
        if p["notional"] > MAX_ORDER_NOTIONAL:
            results.append({"id": pid, "status": "rejected", "msg": f"超过单笔上限 ${MAX_ORDER_NOTIONAL:,}"})
            continue
        try:
            contract = Stock(p["ticker"], "SMART", "USD")
            await ib.qualifyContractsAsync(contract)
            # 限价单：买单加 0.2% 容忍、卖单减 0.2%，避免市价单滑点失控
            lmt = round(p["est_price"] * (1.002 if p["action"] == "BUY" else 0.998), 2)
            order = LimitOrder(p["action"], p["qty"], lmt, tif="DAY")
            trade = ib.placeOrder(contract, order)
            await asyncio.sleep(1.0)  # 给 IB 一拍返回状态
            results.append({"id": pid, "ticker": p["ticker"], "action": p["action"],
                            "qty": p["qty"], "limit": lmt,
                            "status": trade.orderStatus.status or "Submitted"})
        except Exception as e:
            results.append({"id": pid, "ticker": p.get("ticker"), "status": "error", "msg": str(e)})
    return {"results": results}
