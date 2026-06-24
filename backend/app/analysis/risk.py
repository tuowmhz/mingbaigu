"""风险与收益度量：波动率、最大回撤、夏普、VaR、Beta。"""
import numpy as np
import pandas as pd

from ..config import BENCHMARK_OF, RISK_FREE_RATE, market_of
from ..data.market import get_history

TRADING_DAYS = 252


def compute_risk(df: pd.DataFrame, ticker: str) -> dict:
    close = df["Close"]
    rets = close.pct_change().dropna()
    year = rets.tail(TRADING_DAYS)

    ann_vol = float(year.std() * np.sqrt(TRADING_DAYS))
    ann_ret = float((1 + year).prod() ** (TRADING_DAYS / max(len(year), 1)) - 1)
    sharpe = (ann_ret - RISK_FREE_RATE) / ann_vol if ann_vol > 0 else 0.0

    cum = (1 + rets).cumprod()
    drawdown = cum / cum.cummax() - 1
    max_dd = float(drawdown.min())

    var95 = float(np.percentile(year, 5))  # 历史法单日 VaR(95%)

    bench_ticker, bench_name = BENCHMARK_OF[market_of(ticker)]
    beta = _beta_vs_benchmark(rets, ticker, bench_ticker)

    return {
        "annual_volatility": round(ann_vol, 4),
        "annual_return_1y": round(ann_ret, 4),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown": round(max_dd, 4),
        "var_95_daily": round(var95, 4),
        "beta_vs_spy": beta,
        "benchmark_name": bench_name,
        "best_day": round(float(year.max()), 4),
        "worst_day": round(float(year.min()), 4),
    }


def _beta_vs_benchmark(rets: pd.Series, ticker: str, bench: str) -> float | None:
    if ticker == bench:
        return 1.0
    spy = get_history(bench, period="2y")
    if spy is None:
        return None
    spy_rets = spy["Close"].pct_change().dropna()
    joined = pd.concat([rets, spy_rets], axis=1, join="inner").dropna()
    joined.columns = ["stock", "mkt"]
    if len(joined) < 60:
        return None
    cov = joined["stock"].cov(joined["mkt"])
    var = joined["mkt"].var()
    return round(float(cov / var), 2) if var > 0 else None
