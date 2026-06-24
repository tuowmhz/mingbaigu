"""定价权 / 护城河质量评分。

"话语权"在财报上的指纹：高且稳定的毛利率（能转嫁成本）+ 高 ROE（不靠砸钱
就赚超额回报）+ 健康增长。本模块把它做成 0-100 的"定价权评分"。

诚实边界：
- 这是"定价权型"护城河的代理，会漏掉"规模/关系/瓶颈型"卡位（如薄利的代工、电力）；
- 自由数据只有约 4 个年度财报，做不出严谨的十年期点位回测——见 research_moat_ic()
  的诚实低样本结论。因此本评分作为"透明的描述性标签"呈现，不冒充已验证的 alpha。
"""
import numpy as np

from ..cache import cached

CACHE_TTL = 86400


def _annual_margins(t) -> list[dict]:
    """从年度利润表取每个财年的毛利率/营业利润率（点位，含财年末日期）。"""
    try:
        inc = t.income_stmt
        if inc is None or inc.empty:
            return []
    except Exception:
        return []

    def row(*names):
        for n in names:
            if n in inc.index:
                return inc.loc[n]
        return None

    rev = row("Total Revenue", "Operating Revenue")
    gp = row("Gross Profit")
    op = row("Operating Income", "Total Operating Income As Reported", "EBIT")
    if rev is None:
        return []
    out = []
    for col in inc.columns:
        r = rev.get(col)
        if r is None or r == 0 or (isinstance(r, float) and np.isnan(r)):
            continue
        gm = (gp.get(col) / r) if (gp is not None and gp.get(col) is not None) else None
        om = (op.get(col) / r) if (op is not None and op.get(col) is not None) else None
        out.append({"date": col, "gross_margin": gm, "op_margin": om, "revenue": float(r)})
    return out  # 最新在前


def _score_from(gm_level, gm_stability, roe, rev_growth, op_margin):
    """合成 0-100：毛利率水平 35% + 毛利率稳定度 25% + ROE 25% + 增长 15%。"""
    def clamp(x, lo, hi):
        return max(lo, min(hi, x))
    s_gm = clamp((gm_level or 0) / 0.70, 0, 1)            # 70% 毛利≈满分
    s_stab = clamp(gm_stability or 0, 0, 1)               # 稳定度已 0-1
    s_roe = clamp((roe or 0) / 0.35, 0, 1)                # 35% ROE≈满分
    s_grow = clamp(((rev_growth or 0) + 0.05) / 0.30, 0, 1)
    return round(100 * (0.35 * s_gm + 0.25 * s_stab + 0.25 * s_roe + 0.15 * s_grow), 1)


@cached(CACHE_TTL)
def moat_score(ticker: str) -> dict | None:
    import yfinance as yf
    t = yf.Ticker(ticker)
    info = t.info or {}
    margins = _annual_margins(t)
    gms = [m["gross_margin"] for m in margins if m["gross_margin"] is not None]
    gm_level = info.get("grossMargins") or (gms[0] if gms else None)
    # 毛利率稳定度：多年标准差越小越稳（→1）；不足两年则中性 0.5
    if len(gms) >= 2:
        gm_stability = float(1 / (1 + np.std(gms) * 12))
        gm_trend = float(gms[0] - gms[-1])
    else:
        gm_stability, gm_trend = 0.5, None
    roe = info.get("returnOnEquity")
    rev_growth = info.get("revenueGrowth")
    op_margin = info.get("operatingMargins") or (margins[0]["op_margin"] if margins else None)
    if gm_level is None and roe is None:
        return None
    score = _score_from(gm_level, gm_stability, roe, rev_growth, op_margin)
    tier = ("强定价权" if score >= 70 else "较强" if score >= 55 else
            "一般" if score >= 40 else "偏弱")
    return {
        "ticker": ticker.upper(),
        "score": score,
        "tier": tier,
        "gross_margin": round(gm_level, 4) if gm_level is not None else None,
        "gross_margin_stability": round(gm_stability, 3),
        "gross_margin_trend": round(gm_trend, 4) if gm_trend is not None else None,
        "roe": round(roe, 4) if roe is not None else None,
        "operating_margin": round(op_margin, 4) if op_margin is not None else None,
        "revenue_growth": round(rev_growth, 4) if rev_growth is not None else None,
        "n_years": len(gms),
        "note": "定价权型护城河的财务代理；薄利的规模/瓶颈型卡位（代工、电力）会被低估。",
    }
