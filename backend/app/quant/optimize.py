"""组合优化：Ledoit-Wolf 收缩协方差 + 最大夏普（长仓、单票上限）。

预期收益对优化结果影响巨大而历史均值噪音极大。若直接采信历史涨幅，
刚暴涨的动量股会霸占权重上限、堆出高波动组合。因此锚定 8% 长期先验，
个股倾斜用横截面标准化后封顶 ±2%：
    mu_i = 8% + 2% × clip(zscore(hist_i), -2, 2) / 2
让协方差（分散化）成为主导，预期收益只做温和排序。
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf

RISK_FREE = 0.045
MAX_WEIGHT = 0.15
MARKET_PRIOR = 0.08   # 长期股权收益先验
TILT_MAX = 0.02       # 个股倾斜上限（年化 ±2%）


def optimize_portfolio(closes: pd.DataFrame, tickers: list[str]) -> dict | None:
    """对给定标的做最大夏普优化，用最近一年的日收益估计协方差。"""
    rets = closes[tickers].pct_change().tail(252).dropna(how="all")
    rets = rets.dropna(axis=1)
    tickers = list(rets.columns)
    if len(tickers) < 5 or len(rets) < 120:
        return None

    lw = LedoitWolf().fit(rets.values)
    cov = lw.covariance_ * 252  # 年化

    hist_mu = rets.mean().values * 252
    z = (hist_mu - hist_mu.mean()) / (hist_mu.std() or 1.0)
    mu = MARKET_PRIOR + TILT_MAX * np.clip(z, -2, 2) / 2

    n = len(tickers)

    def neg_sharpe(w):
        r = w @ mu
        v = np.sqrt(w @ cov @ w)
        return -(r - RISK_FREE) / v if v > 0 else 0.0

    res = minimize(
        neg_sharpe, np.full(n, 1 / n), method="SLSQP",
        bounds=[(0.0, MAX_WEIGHT)] * n,
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
        options={"maxiter": 500},
    )
    if not res.success:
        return None
    w = res.x

    def port_stats(weights):
        r = float(weights @ mu)
        v = float(np.sqrt(weights @ cov @ weights))
        return {"exp_return": round(r, 4), "exp_vol": round(v, 4),
                "exp_sharpe": round((r - RISK_FREE) / v, 2) if v > 0 else None}

    eq = np.full(n, 1 / n)
    weights = sorted(
        ({"ticker": t, "weight": round(float(x), 4)} for t, x in zip(tickers, w) if x >= 0.01),
        key=lambda d: -d["weight"],
    )
    return {
        "method": "max_sharpe / Ledoit-Wolf 收缩协方差 / 长仓 / 单票≤15%",
        "weights": weights,
        "stats": port_stats(w),
        "equal_weight_stats": port_stats(eq),
        "lw_shrinkage": round(float(lw.shrinkage_), 3),
        "note": ("预期收益锚定8%长期先验、个股倾斜封顶±2%（不直接采信历史涨幅），"
                 "协方差用Ledoit-Wolf收缩估计，分散化主导配置。"
                 "优化解对输入敏感，权重是参考配置而非精确答案。"),
    }
