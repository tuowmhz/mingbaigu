"""内部人交易（高管/董事增减持）：来自 SEC Form 4 公开披露（经 Yahoo 聚合）。

解读原则：高管卖出的原因有一万种（分散、买房、交税），
买入的原因只有一种——觉得便宜。所以买入信号远比卖出信号有分量。
"""
import pandas as pd
import yfinance as yf

from ..cache import cached

CACHE_TTL = 43200  # 12 小时
LOOKBACK_DAYS = 120


def _classify(text: str) -> tuple[str, str]:
    """从交易描述里识别类型。返回 (key, 中文)。"""
    t = (text or "").lower()
    if "purchase" in t or "buy" in t:
        return "buy", "买入"
    if "sale" in t:
        return "sell", "卖出"
    if "gift" in t:
        return "gift", "赠与"
    if "exercise" in t or "conversion" in t:
        return "exercise", "行权"
    return "other", "其他"


@cached(CACHE_TTL)
def get_insider(ticker: str) -> dict | None:
    """最近 ~4 个月的内部人交易汇总 + 明细。"""
    try:
        df = yf.Ticker(ticker).insider_transactions
    except Exception:
        return None
    if df is None or df.empty or "Start Date" not in df.columns:
        return None

    df = df.copy()
    df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    df = df.dropna(subset=["Start Date"])
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=LOOKBACK_DAYS)
    df = df[df["Start Date"] >= cutoff]
    if df.empty:
        return {"items": [], "summary": None, "window_days": LOOKBACK_DAYS}

    def _num(v) -> float:
        """NaN 安全转换：'NaN or 0' 会放过 NaN，必须显式判断。"""
        return 0.0 if v is None or pd.isna(v) else float(v)

    items = []
    buy_value = sell_value = 0.0
    n_buys = n_sells = 0
    for _, row in df.iterrows():
        key, cn = _classify(str(row.get("Text", "")))
        value = _num(row.get("Value"))
        if key == "buy":
            n_buys += 1
            buy_value += value
        elif key == "sell":
            n_sells += 1
            sell_value += value
        items.append({
            "insider": row.get("Insider", ""),
            "position": row.get("Position", ""),
            "type": key,
            "type_cn": cn,
            "shares": int(_num(row.get("Shares"))),
            "value": value,
            "date": row["Start Date"].strftime("%Y-%m-%d"),
        })
    items.sort(key=lambda x: x["date"], reverse=True)

    # 人话判断
    if n_buys == 0 and n_sells == 0:
        judge = "近 4 个月没有实质性的买卖动作（只有行权/赠与等中性操作）。"
    elif n_buys > 0 and buy_value > sell_value:
        judge = (f"内部人在净买入（买 {buy_value/1e6:.1f}M vs 卖 {sell_value/1e6:.1f}M 美元）——"
                 "高管用真金白银加仓自家股票，这是内部人数据里最有分量的信号。")
    elif n_buys > 0:
        judge = (f"有 {n_buys} 笔内部人买入（{buy_value/1e6:.1f}M 美元），但卖出更多"
                 f"（{sell_value/1e6:.1f}M）。买入值得留意，常规减持不必过度解读。")
    else:
        judge = (f"近 4 个月内部人只卖不买（{n_sells} 笔、共 {sell_value/1e6:.1f}M 美元）。"
                 "高管减持原因很多（分散/纳税/既定计划），单独看不构成利空，"
                 "但若伴随基本面转弱则需警惕。")

    return {
        "items": items[:12],
        "summary": {
            "n_buys": n_buys,
            "n_sells": n_sells,
            "buy_value": buy_value,
            "sell_value": sell_value,
            "net_value": buy_value - sell_value,
            "judge": judge,
        },
        "window_days": LOOKBACK_DAYS,
        "source": "SEC Form 4 公开披露",
    }
