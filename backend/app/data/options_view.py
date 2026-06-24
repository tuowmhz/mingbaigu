"""财报日历 + 期权隐含波动率：市场对未来波动的定价。"""
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from ..cache import cached
from ..config import market_of


@cached(43200)
def get_event_view(ticker: str) -> dict | None:
    """下次财报日 + ATM 隐含波动率 + 隐含波动幅度。A股无期权数据。"""
    if market_of(ticker) == "CN":
        return None
    t = yf.Ticker(ticker)
    out = {}

    # —— 财报日历 ——
    try:
        cal = t.calendar or {}
        dates = cal.get("Earnings Date") or []
        future = [d for d in dates if pd.Timestamp(d) >= pd.Timestamp.now().normalize()]
        if future:
            ed = pd.Timestamp(min(future))
            out["earnings_date"] = ed.strftime("%Y-%m-%d")
            out["days_to_earnings"] = int((ed - pd.Timestamp.now().normalize()).days)
    except Exception:
        pass

    # —— 期权隐含波动率（取 25-60 天后的月度到期）——
    try:
        expiries = t.options or []
        now = datetime.now(timezone.utc)
        target = None
        for e in expiries:
            days = (datetime.strptime(e, "%Y-%m-%d").replace(tzinfo=timezone.utc) - now).days
            if 25 <= days <= 60:
                target = (e, days)
                break
        if target is None and expiries:
            e = expiries[min(1, len(expiries) - 1)]
            days = (datetime.strptime(e, "%Y-%m-%d").replace(tzinfo=timezone.utc) - now).days
            target = (e, max(days, 1))
        if target:
            expiry, days = target
            chain = t.option_chain(expiry)
            spot = float(t.fast_info["lastPrice"])
            calls, puts = chain.calls, chain.puts
            atm_call = calls.iloc[(calls["strike"] - spot).abs().argsort()[:2]]
            atm_put = puts.iloc[(puts["strike"] - spot).abs().argsort()[:2]]
            ivs = pd.concat([atm_call["impliedVolatility"], atm_put["impliedVolatility"]]).dropna()
            if not ivs.empty:
                iv = float(ivs.mean())
                move = iv * (days / 365) ** 0.5
                out.update({
                    "expiry": expiry,
                    "atm_iv": round(iv, 4),
                    "implied_move_pct": round(move, 4),
                    "implied_move_note": (
                        f"期权市场为未来 {days} 天定价的波动幅度约 ±{move*100:.1f}%"
                        f"（年化隐含波动率 {iv*100:.0f}%）——这是交易员用真金白银投出来的'预期波动'。"
                    ),
                })
    except Exception:
        pass

    return out or None
