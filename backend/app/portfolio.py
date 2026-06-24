"""持仓管理：交易记录、资产总览、每日持减建议。

存储：本地 JSON 文件（单用户工具，无需数据库）。
建议引擎：复用对抗验证裁决 + 消息面信号 + 集中度规则，
输出 持有/考虑减持/关注加仓 三档建议与人话理由。
"""
import json
import threading
import uuid
from pathlib import Path

from .analysis.adversarial import run_adversarial
from .analysis.news_signal import analyze_news
from .analysis.risk import compute_risk
from .config import CURRENCY_OF, NAME_MAP, market_of
from .data.market import get_history, latest_quote
from .data.news import get_news
from .ml.features import tech_snapshot
from .ml.model import predict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _data_file(uid: str) -> Path:
    """按用户隔离持仓数据；local 用户沿用旧文件（本地开发兼容）。"""
    return DATA_DIR / ("portfolio.json" if uid == "local" else f"portfolio_{uid}.json")
_lock = threading.Lock()

MAX_WEIGHT_WARN = 0.30   # 单票占总资产超过 30% 提示集中度
CASH_LOW_WARN = 0.05     # 现金低于 5% 提示无子弹


def _load(uid: str = "local") -> dict:
    f = _data_file(uid)
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return {"initial_cash": 0.0, "transactions": []}


def _save(data: dict, uid: str = "local"):
    f = _data_file(uid)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1))


def set_settings(initial_cash: float, uid: str = "local") -> dict:
    with _lock:
        data = _load(uid)
        data["initial_cash"] = float(initial_cash)
        _save(data, uid)
    return data


def add_transaction(ticker: str, side: str, shares: float, price: float, date: str,
                    uid: str = "local") -> dict:
    tx = {
        "id": uuid.uuid4().hex[:10],
        "ticker": ticker.upper(),
        "side": side,            # buy / sell
        "shares": float(shares),
        "price": float(price),
        "date": date,
    }
    with _lock:
        data = _load(uid)
        data["transactions"].append(tx)
        _save(data, uid)
    return tx


def delete_transaction(tx_id: str, uid: str = "local") -> bool:
    with _lock:
        data = _load(uid)
        before = len(data["transactions"])
        data["transactions"] = [t for t in data["transactions"] if t["id"] != tx_id]
        _save(data, uid)
        return len(data["transactions"]) < before


def _fx_usdcny() -> float:
    """美元兑人民币汇率（A股资产折美元用）。拿不到时用保守近似值。"""
    df = get_history("CNY=X", period="1mo")
    if df is not None and not df.empty:
        return float(df["Close"].iloc[-1])
    return 7.2


def _to_usd(amount: float, ticker: str, fx: float) -> float:
    return amount / fx if market_of(ticker) == "CN" else amount


def _positions_and_cash(data: dict, fx: float) -> tuple[dict, float]:
    """平均成本法持仓 + 现金（美元口径，A股按当前汇率折算）。

    持仓成本以本币记账（盈亏直观），现金池统一折美元扣减。
    卖出超过持仓的部分按 0 成本处理（容错）。
    """
    pos: dict[str, dict] = {}
    cash = float(data.get("initial_cash", 0.0))
    for tx in sorted(data["transactions"], key=lambda t: t["date"]):
        t = tx["ticker"]
        p = pos.setdefault(t, {"shares": 0.0, "cost": 0.0})
        amount = tx["shares"] * tx["price"]          # 本币金额
        amount_usd = _to_usd(amount, t, fx)
        if tx["side"] == "buy":
            p["shares"] += tx["shares"]
            p["cost"] += amount
            cash -= amount_usd
        else:
            sell_shares = min(tx["shares"], p["shares"])
            if p["shares"] > 0:
                p["cost"] -= p["cost"] / p["shares"] * sell_shares
            p["shares"] -= sell_shares
            cash += amount_usd
    return {t: p for t, p in pos.items() if p["shares"] > 1e-9}, cash


def _advise(ticker: str, weight: float, cash_ratio: float) -> dict:
    """单票建议：对抗裁决 + 消息面 + 集中度。失败时降级为'数据不足'。"""
    df = get_history(ticker, period="2y")
    if df is None:
        return {"action": "hold", "action_cn": "持有", "reasons": ["暂时拿不到行情数据，无法给出建议"]}
    as_of = df.index[-1].strftime("%Y-%m-%d")
    analyzed = analyze_news(get_news(ticker), ticker)
    signal = analyzed["signal"] if analyzed else None
    prediction = predict(ticker, as_of)
    risk = compute_risk(df, ticker)
    adv = run_adversarial(tech_snapshot(df), signal, None, prediction, risk)
    judge = adv["judge"]

    reasons = []
    action, action_cn = "hold", "持有"

    if judge["verdict"] == "bearish":
        action, action_cn = "reduce", "考虑减持"
        reasons.append(f"对抗验证裁决偏空（置信度 {judge['confidence']*100:.0f}%）")
    if signal and signal["score"] <= -1.2:
        action, action_cn = "reduce", "考虑减持"
        reasons.append(f"消息面强利空（信号 {signal['score']:+.1f}）")
    if weight > MAX_WEIGHT_WARN:
        if action == "hold":
            action, action_cn = "trim", "建议降低集中度"
        reasons.append(f"该股占总资产 {weight*100:.0f}%，单票集中度偏高")
    if action == "hold" and judge["verdict"] == "bullish" and judge["confidence"] >= 0.15:
        if cash_ratio > 0.15:
            action, action_cn = "add_watch", "持有，可关注加仓"
            reasons.append(f"裁决偏多（置信度 {judge['confidence']*100:.0f}%）且现金充足")
        else:
            reasons.append(f"裁决偏多（置信度 {judge['confidence']*100:.0f}%），但现金不足，安心持有")
    if not reasons:
        reasons.append(f"裁决{judge['verdict_cn']}、消息面{signal['direction_cn'] if signal else '无数据'}——没有需要动手的信号")

    return {
        "action": action,
        "action_cn": action_cn,
        "reasons": reasons,
        "judge_verdict": judge["verdict_cn"],
        "judge_confidence": judge["confidence"],
        "news_label": signal["direction_cn"] if signal else "无数据",
    }


def get_portfolio(with_advice: bool = True, uid: str = "local") -> dict:
    data = _load(uid)
    fx = _fx_usdcny()
    positions, cash = _positions_and_cash(data, fx)

    rows = []
    total_mv_usd = 0.0
    quotes = {}
    for t, p in positions.items():
        df = get_history(t, period="2y")
        q = latest_quote(df) if df is not None else None
        quotes[t] = q
        mv = (q["price"] * p["shares"]) if q else 0.0   # 本币市值
        total_mv_usd += _to_usd(mv, t, fx)

    total_assets = cash + total_mv_usd
    cash_ratio = cash / total_assets if total_assets > 0 else 1.0

    for t, p in positions.items():
        q = quotes[t]
        mv = (q["price"] * p["shares"]) if q else 0.0
        mv_usd = _to_usd(mv, t, fx)
        avg_cost = p["cost"] / p["shares"] if p["shares"] else 0.0
        weight = mv_usd / total_assets if total_assets > 0 else 0.0
        row = {
            "ticker": t,
            "name_cn": NAME_MAP.get(t, t),
            "market": market_of(t),
            "currency": CURRENCY_OF[market_of(t)],
            "shares": round(p["shares"], 4),
            "avg_cost": round(avg_cost, 4),
            "price": q["price"] if q else None,
            "market_value": round(mv, 2),          # 本币
            "market_value_usd": round(mv_usd, 2),  # 折美元
            "weight": round(weight, 4),
            "pnl": round(mv - p["cost"], 2),       # 本币盈亏
            "pnl_pct": round((mv / p["cost"] - 1), 4) if p["cost"] > 0 else None,
        }
        if with_advice:
            row["advice"] = _advise(t, weight, cash_ratio)
        rows.append(row)
    rows.sort(key=lambda r: -r["market_value_usd"])
    total_mv = total_mv_usd

    # 组合级提示
    notes = []
    if rows:
        top = rows[0]
        if top["weight"] > MAX_WEIGHT_WARN:
            notes.append(f"最大持仓 {top['ticker']} 占总资产 {top['weight']*100:.0f}%——鸡蛋有点集中，建议控制单票上限。")
        if cash_ratio < CASH_LOW_WARN and data.get("initial_cash", 0) > 0:
            notes.append(f"现金仅占 {cash_ratio*100:.1f}%——满仓状态没有应对回调的子弹。")
        n_reduce = sum(1 for r in rows if r.get("advice", {}).get("action") == "reduce")
        if n_reduce:
            notes.append(f"有 {n_reduce} 只持仓收到'考虑减持'信号，详见各持仓的建议理由。")
    total_cost_usd = sum(_to_usd(p["cost"], t, fx) for t, p in positions.items())

    from .failures import match_portfolio_pitfalls
    pitfalls = match_portfolio_pitfalls(data["transactions"], rows)

    return {
        "pitfalls": pitfalls,
        "initial_cash": data.get("initial_cash", 0.0),
        "currency_note": f"组合汇总为美元口径，A股资产按当前汇率 USDCNY={fx:.2f} 折算；单票价格与盈亏用本币显示。",
        "fx_usdcny": round(fx, 4),
        "cash": round(cash, 2),
        "cash_ratio": round(cash_ratio, 4),
        "market_value": round(total_mv, 2),
        "total_assets": round(total_assets, 2),
        "total_pnl": round(total_mv - total_cost_usd, 2),
        "positions": rows,
        "notes": notes,
        "transactions": sorted(data["transactions"], key=lambda t: t["date"], reverse=True)[:50],
        "disclaimer": "建议由规则引擎基于公开数据生成，仅供参考，不构成投资建议。",
    }
