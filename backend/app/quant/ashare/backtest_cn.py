"""A股低频多因子回测引擎。

诚实护栏（全部照搬主项目 zoo/backtest 的纪律，并按 A 股调参）：
1. 时点成分股掩码：每个调仓日只在「当日真实成分股」里选，抗幸存者偏差。
2. 因子全部 shift 实现，t 日因子只含 t 日及之前信息，无前视偏差。
3. IS 只筛因子方向、OOS 只评一次：先用样本内 IC 决定纳入哪些因子，
   再到样本外评估一次综合策略，并披露 IS→OOS 衰减。
4. 扣 A 股真实成本：佣金双边 + 印花税(卖出) + 滑点，按换手率计提，并做成本敏感性。
5. 对标对应指数（中证500=000905 / 沪深300=000300）。
"""
import numpy as np
import pandas as pd

import data_cn as dc
from factors_cn import FACTOR_DOC, composite_at, factor_panels

RF = 0.02            # 中国无风险利率近似（年化）
WARMUP_DAYS = 273    # 252+21，保证首个调仓日 12-1 动量完整
IS_END = "2021-12-31"  # 样本内/样本外硬切分


def month_end_dates(idx: pd.DatetimeIndex) -> list:
    s = pd.Series(idx, index=idx)
    return list(s.groupby(s.index.to_period("M")).tail(1).index)


def _stats(rets: pd.Series, rf: float = RF) -> dict:
    rets = rets.dropna()
    if len(rets) < 2:
        return {}
    n_years = len(rets) / 12
    cum = float((1 + rets).prod())
    cagr = cum ** (1 / n_years) - 1
    vol = float(rets.std() * np.sqrt(12))
    curve = (1 + rets).cumprod()
    max_dd = float((curve / curve.cummax() - 1).min())
    downside = rets[rets < 0].std() * np.sqrt(12)
    return {
        "cagr": round(cagr, 4),
        "annual_vol": round(vol, 4),
        "sharpe": round((cagr - rf) / vol, 2) if vol > 0 else None,
        "sortino": round((cagr - rf) / float(downside), 2) if downside and downside > 0 else None,
        "max_drawdown": round(max_dd, 4),
        "calmar": round(cagr / abs(max_dd), 2) if max_dd < 0 else None,
        "total_return": round(cum - 1, 4),
        "n_months": int(len(rets)),
    }


def _spearman(a: pd.Series, b: pd.Series) -> float | None:
    v = a.notna() & b.notna()
    if v.sum() < 30:
        return None
    return float(a[v].rank().corr(b[v].rank()))


def run_backtest(universe: str = "zz500", top_n: int = 30,
                 cost_roundtrip: float = 0.003, factor_keys: list[str] | None = None,
                 select_on_is: bool = True) -> dict:
    bench_close = dc.bench_series(universe)
    # 用基准的交易日历做主索引
    cons = dc.load_constituents()
    if universe == "zz800":
        all_codes = sorted(set(c for v in cons["hs300"].values() for c in v) |
                           set(c for v in cons["zz500"].values() for c in v))
    else:
        all_codes = sorted({c for v in cons[universe].values() for c in v})
    panels_raw = dc.build_panels(all_codes)
    close, turn, amount = panels_raw["close"], panels_raw["turn"], panels_raw["amount"]
    close = close.sort_index()
    bench = bench_close.reindex(close.index).ffill()

    fpanels = factor_panels(close, turn, amount)
    mask = dc.membership_mask(universe, close.index)

    rebal = [d for d in month_end_dates(close.index)
             if d >= close.index[0] + pd.Timedelta(days=WARMUP_DAYS)]
    is_end = pd.Timestamp(IS_END)

    all_keys = list(FACTOR_DOC.keys())
    # —— 第一遍：算每个因子的 IS / OOS / 全样本 IC（用于选因子 + 披露衰减）——
    ic = {k: {"is": [], "oos": []} for k in all_keys}
    for i in range(len(rebal) - 1):
        t, t1 = rebal[i], rebal[i + 1]
        elig = mask.columns[mask.loc[t].values]
        elig = close.columns.intersection(elig)
        fwd = (close.loc[t1] / close.loc[t] - 1).reindex(elig)
        seg = "is" if t <= is_end else "oos"
        for k in all_keys:
            val = fpanels[k].loc[t].reindex(elig)
            c = _spearman(val, fwd)
            if c is not None:
                ic[k][seg].append(c)

    def ic_summary(vals):
        arr = np.array(vals, dtype=float)
        if arr.size == 0:
            return {"mean": None, "ir": None, "pos_pct": None, "n": 0}
        return {"mean": round(float(arr.mean()), 4),
                "ir": round(float(arr.mean() / arr.std()), 2) if arr.std() > 0 else None,
                "pos_pct": round(float((arr > 0).mean()), 3), "n": int(arr.size)}

    factor_report = []
    for k in all_keys:
        name, desc = FACTOR_DOC[k]
        factor_report.append({"key": k, "name_cn": name, "desc_cn": desc,
                              "ic_is": ic_summary(ic[k]["is"]),
                              "ic_oos": ic_summary(ic[k]["oos"]),
                              "ic_full": ic_summary(ic[k]["is"] + ic[k]["oos"])})

    # —— 选因子：只用样本内 IC（IS IC 均值 > 0 且方向稳定）——
    if factor_keys is not None:
        keys = factor_keys
    elif select_on_is:
        keys = [k for k in all_keys
                if (ic[k]["is"] and np.mean(ic[k]["is"]) > 0
                    and np.mean(np.array(ic[k]["is"]) > 0) >= 0.50)]
    else:
        keys = all_keys
    if not keys:
        keys = ["reversal_1m"]

    # —— 第二遍：用选定因子组合做实盘式回测 ——
    rows, prev = [], set()
    curve_s, curve_b, cdates = [1.0], [1.0], [rebal[0]]
    holdings_log = {}
    for i in range(len(rebal) - 1):
        t, t1 = rebal[i], rebal[i + 1]
        elig = close.columns.intersection(mask.columns[mask.loc[t].values])
        # 可交易：t 与 t1 都有有效价
        px_t, px_t1 = close.loc[t].reindex(elig), close.loc[t1].reindex(elig)
        tradeable = elig[px_t.notna() & px_t1.notna() & (px_t > 0)]
        score = composite_at(fpanels, t, keys, tradeable).dropna()
        if score.empty:
            continue
        hold = list(score.nlargest(top_n).index)
        fwd = (close.loc[t1, hold] / close.loc[t, hold] - 1)
        port = float(fwd.mean())
        turnover = 1.0 if not prev else len(set(hold) - prev) / top_n
        prev = set(hold)
        net = port - turnover * cost_roundtrip
        bret = float(bench.loc[t1] / bench.loc[t] - 1)
        rows.append({"date": t1.strftime("%Y-%m-%d"), "ret": net, "gross": port,
                     "bench_ret": bret, "turnover": turnover,
                     "seg": "IS" if t <= is_end else "OOS"})
        curve_s.append(curve_s[-1] * (1 + net))
        curve_b.append(curve_b[-1] * (1 + bret))
        cdates.append(t1)
        holdings_log[t1.strftime("%Y-%m-%d")] = hold

    df = pd.DataFrame(rows)
    is_mask = df["seg"] == "IS"
    excess = df["ret"] - df["bench_ret"]

    return {
        "config": {"universe": universe, "top_n": top_n,
                   "cost_roundtrip_bps": round(cost_roundtrip * 1e4, 1),
                   "selected_factors": keys, "is_end": IS_END,
                   "n_stocks_pool": len(all_codes)},
        "stats": {
            "full": _stats(df["ret"]), "bench_full": _stats(df["bench_ret"]),
            "is": _stats(df.loc[is_mask, "ret"]), "oos": _stats(df.loc[~is_mask, "ret"]),
            "bench_oos": _stats(df.loc[~is_mask, "bench_ret"]),
            "excess_full": _stats(excess),
        },
        "monthly_win_rate_vs_bench": round(float((df["ret"] > df["bench_ret"]).mean()), 3),
        "avg_turnover": round(float(df["turnover"].mean()), 3),
        "factors": factor_report,
        "curve": [{"date": d.strftime("%Y-%m-%d"), "strategy": round(s, 4),
                   "bench": round(b, 4)} for d, s, b in zip(cdates, curve_s, curve_b)],
        "monthly": rows,
        "holdings_last": holdings_log.get(df["date"].iloc[-1], []) if len(df) else [],
    }
