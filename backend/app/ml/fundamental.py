"""基本面动量：分析师盈利预期修正（estimate revision momentum）。

学术上这是最稳健的异象之一——一致预期被上修的股票后续倾向跑赢。两个分量：
- 修正动能：当前财年/次年一致 EPS 相对 90 天前的变化（正=被上修）；
- 修正广度：近 30 天上修家数 vs 下修家数的净占比。

诚实边界（与 moat 同）：
- 免费数据（yfinance）只有"当前快照"，没有带时间戳的历史预期序列，
  **我们无法在十年历史上独立回测它**。学术 IC 通常 0.03–0.07，但那不是我们验证的。
- 因此本因子作为"透明的前瞻信号"呈现，**不**并入已回测的模型 IC、**不**当买卖指令。

防前视：涉及财报实际值时，必须用"披露日"而非"财年末"（见 pit_quarter_ends）；
本模块的预期数据是 as-of 当前，天然无未来函数。前视单测见 tests/test_lookahead.py。
"""
from datetime import timedelta

import numpy as np

from ..cache import cached

CACHE_TTL = 86400
FILING_LAG_DAYS = 75  # 财报披露滞后保守值：季报~40d、年报~75d，取大者防偷看


def pit_quarter_ends(period_ends, asof) -> list:
    """点位过滤：只保留'财年末 + 披露滞后 <= asof'的财报期，杜绝用未公开数据。"""
    import pandas as pd
    out = []
    for c in period_ends:
        if pd.Timestamp(c).tz_localize(None) + timedelta(days=FILING_LAG_DAYS) <= pd.Timestamp(asof).tz_localize(None):
            out.append(c)
    return out


def _revision_momentum(eps_trend) -> float | None:
    """当前财年(0y)与次年(+1y)一致 EPS 相对 90 天前的变化率，取均值。"""
    vals = []
    for period in ["0y", "+1y"]:
        try:
            cur = float(eps_trend.loc[period, "current"])
            old = float(eps_trend.loc[period, "90daysAgo"])
        except Exception:
            continue
        if old and not np.isnan(old) and not np.isnan(cur) and abs(old) > 1e-6:
            vals.append((cur - old) / abs(old))
    return float(np.mean(vals)) if vals else None


def _revision_breadth(eps_rev) -> float | None:
    """近 30 天净上修占比：(上修 - 下修) / (上修 + 下修)，范围 -1..+1。"""
    try:
        up = float(eps_rev.loc["0y", "upLast30days"])
        down = float(eps_rev.loc["0y", "downLast30days"])
    except Exception:
        return None
    tot = up + down
    return float((up - down) / tot) if tot > 0 else None


def _score(rev_mom, breadth) -> float:
    def clamp(x, lo, hi):
        return max(lo, min(hi, x))
    s_mom = clamp(((rev_mom or 0) + 0.05) / 0.20, 0, 1)   # +15% 90日上修≈满分
    s_brd = clamp(((breadth or 0) + 1) / 2, 0, 1)         # -1..1 → 0..1
    return round(100 * (0.6 * s_mom + 0.4 * s_brd), 1)


@cached(CACHE_TTL)
def fundamental_momentum(ticker: str) -> dict | None:
    import yfinance as yf
    t = yf.Ticker(ticker)
    try:
        eps_trend = t.eps_trend
        eps_rev = t.eps_revisions
    except Exception:
        return None
    if eps_trend is None or eps_trend.empty:
        return None
    rev_mom = _revision_momentum(eps_trend)
    breadth = _revision_breadth(eps_rev) if eps_rev is not None and not eps_rev.empty else None
    if rev_mom is None and breadth is None:
        return None
    score = _score(rev_mom, breadth)
    tier = ("强上修" if score >= 68 else "温和上修" if score >= 55 else
            "中性" if score >= 42 else "下修")
    return {
        "ticker": ticker.upper(),
        "score": score,
        "tier": tier,
        "revision_momentum_90d": round(rev_mom, 4) if rev_mom is not None else None,
        "revision_breadth_30d": round(breadth, 3) if breadth is not None else None,
        "note": "分析师盈利预期修正动量（学术异象，IC约0.03-0.07）；免费数据无历史预期序列，"
                "我们无法独立回测——作前瞻信号，非已验证 alpha，不构成买卖指令。",
    }
