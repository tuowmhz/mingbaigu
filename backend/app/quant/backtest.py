"""回测：月度调仓、做多综合得分 Top N、扣交易成本、对标 SPY。

诚实原则：
- 只回测价格因子（时点正确）；
- 因子 IC 用 Spearman 秩相关（对离群值稳健）；
- 扣 20bps 往返成本 × 换手率；
- 用今日成分股回测历史有幸存者偏差，结果偏乐观，披露在 meta 里。
"""
import numpy as np
import pandas as pd

from .factors import PRICE_FACTORS, composite_at, price_factor_panel

TOP_N = 20
COST_ROUNDTRIP = 0.002  # 20bps 往返
WARMUP_DAYS = 273       # 252+21，保证首个调仓日因子完整


def month_end_dates(closes: pd.DataFrame) -> list:
    """每个自然月最后一个交易日。"""
    return list(closes.groupby(closes.index.to_period("M")).tail(1).index)


def run_backtest(closes: pd.DataFrame, bench: pd.Series) -> dict:
    panel = price_factor_panel(closes)
    dates = [d for d in month_end_dates(closes) if d >= closes.index[0] + pd.Timedelta(days=WARMUP_DAYS)]
    if len(dates) < 8:
        raise ValueError("历史太短，无法回测")

    # 每个调仓日的前向 1 月收益（标签）
    rows, ics = [], {k: [] for k in panel}
    prev_holdings: set = set()
    strat_curve = [1.0]
    bench_curve = [1.0]
    curve_dates = [dates[0]]

    for i in range(len(dates) - 1):
        t, t1 = dates[i], dates[i + 1]
        fwd = closes.loc[t1] / closes.loc[t] - 1  # 前向收益标签

        # 因子 IC（Spearman：秩相关）
        for key, df in panel.items():
            f = df.loc[t]
            valid = f.notna() & fwd.notna()
            if valid.sum() >= 30:
                ics[key].append(f[valid].rank().corr(fwd[valid].rank()))

        score = composite_at(panel, t).dropna()
        holdings = set(score.nlargest(TOP_N).index)
        turnover = 1.0 if not prev_holdings else len(holdings - prev_holdings) / TOP_N
        prev_holdings = holdings

        port_ret = fwd[list(holdings)].mean() - turnover * COST_ROUNDTRIP
        bench_ret = bench.loc[:t1].iloc[-1] / bench.loc[:t].iloc[-1] - 1

        rows.append({"date": t1.strftime("%Y-%m-%d"), "ret": port_ret,
                     "bench_ret": bench_ret, "turnover": turnover})
        strat_curve.append(strat_curve[-1] * (1 + port_ret))
        bench_curve.append(bench_curve[-1] * (1 + bench_ret))
        curve_dates.append(t1)

    df = pd.DataFrame(rows)

    def stats(rets: pd.Series) -> dict:
        n_years = len(rets) / 12
        cum = (1 + rets).prod()
        cagr = cum ** (1 / n_years) - 1 if n_years > 0 else 0
        vol = rets.std() * np.sqrt(12)
        curve = (1 + rets).cumprod()
        max_dd = (curve / curve.cummax() - 1).min()
        return {
            "cagr": round(float(cagr), 4),
            "annual_vol": round(float(vol), 4),
            "sharpe": round(float((cagr - 0.045) / vol), 2) if vol > 0 else None,
            "max_drawdown": round(float(max_dd), 4),
            "total_return": round(float(cum - 1), 4),
        }

    factor_report = []
    for key, vals in ics.items():
        arr = np.array(vals)
        name_cn, desc = PRICE_FACTORS[key]
        factor_report.append({
            "key": key, "name_cn": name_cn, "desc_cn": desc,
            "ic_mean": round(float(arr.mean()), 4),
            "ic_ir": round(float(arr.mean() / arr.std()), 2) if arr.std() > 0 else None,
            "ic_positive_pct": round(float((arr > 0).mean()), 3),
            "n_months": int(len(arr)),
        })

    return {
        "curve": [{"date": d.strftime("%Y-%m-%d"),
                   "strategy": round(s, 4), "spy": round(b, 4)}
                  for d, s, b in zip(curve_dates, strat_curve, bench_curve)],
        "stats": {"strategy": stats(df["ret"]), "spy": stats(df["bench_ret"])},
        "monthly_win_rate_vs_spy": round(float((df["ret"] > df["bench_ret"]).mean()), 3),
        "avg_turnover": round(float(df["turnover"].mean()), 3),
        "n_months": int(len(df)),
        "top_n": TOP_N,
        "cost_roundtrip_bps": int(COST_ROUNDTRIP * 10000),
        "factors": factor_report,
    }
