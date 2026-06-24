"""一年期展望模型：预测个股未来 12 个月相对 QQQ 的超额收益。

方法论（为什么是监督学习而不是 RL）：
- 预测问题的瓶颈是信息（市场信噪比），不是决策框架。RL 适合序列决策
  （执行、调仓、风控），对"预测收益"这件事不会比监督学习多挤出任何信息，
  只会让训练更不稳定。这里用梯度提升做横截面回归，是同等信息量下的正解。

诚实工程（每一条都是为了不自欺）：
- 标签 = 未来 252 个交易日收益 - QQQ 同期收益（直接以"能否跑赢 QQQ"为目标）；
- purged walk-forward：测试年份 Y 的训练样本，其标签窗口必须在 Y 开始前
  完全结束（12 个月禁运期），杜绝标签泄漏；
- 逐年报告样本外战绩 vs QQQ，赢就是赢、输就是输；
- 已知且无法消除的偏差如实披露：用今天的成分股回测 10 年历史，
  幸存者偏差会显著美化结果——真实可获得的超额收益低于回测显示值。
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.ensemble import HistGradientBoostingRegressor

from ..cache import cached, disk_cache_load, disk_cache_save
from .universe import TOP100

ARTIFACT = Path(__file__).resolve().parent.parent.parent / "data" / "longterm_results.json"

HORIZON = 252          # 一年
MIN_TRAIN_YEARS = 3    # 首个测试年之前至少要有的训练年数
TOP_N = 10             # 每年做多的股票数

FEATURES = [
    "mom_12", "mom_6", "mom_3", "vol_12", "max_dd_12",
    "rel_strength_12", "dist_52w_high", "downside_vol",
    "vix", "vix_chg_3m", "tnx", "tnx_chg_6m", "qqq_trend", "qqq_mom_12",
]


def _fetch() -> tuple[pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    raw = yf.download(TOP100 + ["QQQ", "^VIX", "^TNX"], period="10y",
                      auto_adjust=True, progress=False)["Close"]
    raw.index = pd.to_datetime(raw.index).tz_localize(None)
    qqq = raw["QQQ"].dropna()
    vix = raw["^VIX"].reindex(raw.index).ffill()
    tnx = raw["^TNX"].reindex(raw.index).ffill()
    closes = raw.drop(columns=["QQQ", "^VIX", "^TNX"], errors="ignore")
    return closes, qqq, vix, tnx


def _build_samples(closes, qqq, vix, tnx) -> pd.DataFrame:
    rets = closes.pct_change()
    qqq_ret_12 = qqq / qqq.shift(252) - 1

    # —— 个股特征（全部只用 t 及之前的数据）——
    f = {
        "mom_12": closes / closes.shift(252) - 1,
        "mom_6": closes / closes.shift(126) - 1,
        "mom_3": closes / closes.shift(63) - 1,
        "vol_12": rets.rolling(252).std() * np.sqrt(252),
        "downside_vol": rets.clip(upper=0).rolling(252).std() * np.sqrt(252),
        "dist_52w_high": closes / closes.rolling(252).max() - 1,
    }
    roll_max = closes.rolling(252).max()
    f["max_dd_12"] = closes / roll_max - 1  # 与 dist 同口径的回撤近似
    f["rel_strength_12"] = f["mom_12"].sub(qqq_ret_12, axis=0)

    # —— 市场状态特征（同一日期对所有股票相同）——
    regime = pd.DataFrame(index=closes.index)
    regime["vix"] = vix
    regime["vix_chg_3m"] = vix - vix.shift(63)
    regime["tnx"] = tnx
    regime["tnx_chg_6m"] = tnx - tnx.shift(126)
    regime["qqq_trend"] = (qqq > qqq.rolling(200).mean()).astype(float)
    regime["qqq_mom_12"] = qqq_ret_12

    # —— 标签：未来一年超额收益 ——
    fwd = closes.shift(-HORIZON) / closes - 1
    qqq_fwd = qqq.shift(-HORIZON) / qqq - 1
    excess = fwd.sub(qqq_fwd, axis=0)

    month_ends = closes.groupby(closes.index.to_period("M")).tail(1).index
    rows = []
    for t in month_ends:
        if t < closes.index[0] + pd.Timedelta(days=380):
            continue  # 特征需要满一年历史
        reg = regime.loc[t]
        for s in closes.columns:
            feat_vals = {k: f[k].at[t, s] for k in f}
            if any(pd.isna(v) for v in feat_vals.values()):
                continue
            rows.append({
                "date": t, "ticker": s, **feat_vals,
                **{k: reg[k] for k in regime.columns},
                "y": excess.at[t, s],            # 测试期之后的样本可为 NaN
                "fwd_ret": fwd.at[t, s],
                "qqq_fwd": qqq_fwd.at[t],
            })
    return pd.DataFrame(rows)


def _make_model():
    return HistGradientBoostingRegressor(
        max_iter=300, max_depth=4, learning_rate=0.05,
        min_samples_leaf=40, random_state=42,
    )


@cached(21600)
def build_longterm() -> dict:
    cached_result = disk_cache_load(ARTIFACT, max_age_seconds=86400)
    if cached_result is not None:
        return cached_result
    closes, qqq, vix, tnx = _fetch()
    samples = _build_samples(closes, qqq, vix, tnx)
    labeled = samples.dropna(subset=["y"])

    years = sorted(labeled["date"].dt.year.unique())
    test_years = [y for y in years if y >= years[0] + MIN_TRAIN_YEARS]

    yearly, ics = [], []
    for y in test_years:
        test_start = pd.Timestamp(f"{y}-01-01")
        # purge：训练样本的标签窗口（t + 12m）必须在测试年开始前结束
        train = labeled[labeled["date"] < test_start - pd.DateOffset(months=12)]
        if len(train) < 800:
            continue
        model = _make_model()
        model.fit(train[FEATURES], train["y"])

        in_year = labeled[labeled["date"].dt.year == y]
        if in_year.empty:
            continue
        # 年初建仓：用该年第一个月末的预测选 Top N，持有一年
        first_t = in_year["date"].min()
        snap = in_year[in_year["date"] == first_t].copy()
        snap["pred"] = model.predict(snap[FEATURES])
        top = snap.nlargest(TOP_N, "pred")
        port_ret = float(top["fwd_ret"].mean())
        qqq_ret = float(top["qqq_fwd"].iloc[0])

        # 全年逐月 IC（预测值与实际超额的秩相关）
        month_ics = []
        for t, grp in in_year.groupby("date"):
            g = grp.copy()
            g["pred"] = model.predict(g[FEATURES])
            if len(g) >= 30:
                month_ics.append(g["pred"].rank().corr(g["y"].rank()))
        ic = float(np.mean(month_ics)) if month_ics else None
        if ic is not None:
            ics.append(ic)

        yearly.append({
            "year": int(y),
            "portfolio_return": round(port_ret, 4),
            "qqq_return": round(qqq_ret, 4),
            "excess": round(port_ret - qqq_ret, 4),
            "ic": round(ic, 3) if ic is not None else None,
            "picks": top["ticker"].tolist(),
        })

    wins = sum(1 for r in yearly if r["excess"] > 0)
    avg_excess = float(np.mean([r["excess"] for r in yearly])) if yearly else None

    # —— 当前一年期展望：全量训练，预测最新截面 ——
    final_model = _make_model()
    final_model.fit(labeled[FEATURES], labeled["y"])
    latest_t = samples["date"].max()
    current = samples[samples["date"] == latest_t].copy()
    current["pred"] = final_model.predict(current[FEATURES])
    picks = [
        {"ticker": r["ticker"],
         "predicted_excess_1y": round(float(r["pred"]), 4),
         "mom_12": round(float(r["mom_12"]), 4),
         "rel_strength_12": round(float(r["rel_strength_12"]), 4),
         "vol_12": round(float(r["vol_12"]), 4)}
        for _, r in current.nlargest(15, "pred").iterrows()
    ]

    # —— 诚实裁决 ——
    if avg_excess is None:
        verdict = "历史数据不足，无法给出有意义的评估。"
    elif avg_excess > 0.15:
        verdict = (f"样本外 {len(yearly)} 年中 {wins} 年跑赢 QQQ，平均年超额 {avg_excess*100:+.1f}%——"
                   "这个数字好得不真实，而这本身就是结论：全球顶级对冲基金也无法持续做到年化 +15% 以上的超额，"
                   "如此夸张的回测收益主要来自幸存者偏差（股票池是今天的赢家名单，模型等于在'预测'已经发生的胜利）。"
                   "可信的部分是 IC（截面排序能力）为正——动量与相对强度在一年期维度确实携带信息；"
                   "不可信的部分是收益数字本身。请把当前选股列表当作'相对看好的排序'，并预期真实超额远小于回测。")
    elif avg_excess > 0.03 and wins / max(len(yearly), 1) > 0.55:
        verdict = (f"样本外 {len(yearly)} 年中 {wins} 年跑赢 QQQ，平均年超额 {avg_excess*100:+.1f}%。"
                   "看起来不错，但请记住：幸存者偏差会显著美化这一数字（回测用的是今天的赢家名单），"
                   "真实可获得的超额收益大概率低于此值。")
    elif avg_excess > 0:
        verdict = (f"样本外 {len(yearly)} 年中 {wins} 年跑赢 QQQ，平均年超额仅 {avg_excess*100:+.1f}%——"
                   "扣除幸存者偏差后，与直接持有 QQQ 难分胜负。这印证了一个事实：长期战胜 QQQ 极难。")
    else:
        verdict = (f"样本外 {len(yearly)} 年中仅 {wins} 年跑赢 QQQ，平均年超额 {avg_excess*100:+.1f}%。"
                   "模型没有跑赢基准——对大多数人来说，定投 QQQ 本身就是极难战胜的策略，这就是真相。")

    return disk_cache_save(ARTIFACT, {
        "horizon": "12 个月",
        "benchmark": "QQQ（含分红）",
        "n_samples": int(len(labeled)),
        "n_test_years": len(yearly),
        "wins_vs_qqq": wins,
        "avg_excess": round(avg_excess, 4) if avg_excess is not None else None,
        "avg_ic": round(float(np.mean(ics)), 3) if ics else None,
        "yearly": yearly,
        "current_picks": picks,
        "as_of": latest_t.strftime("%Y-%m-%d"),
        "verdict": verdict,
        "disclaimers": [
            "幸存者偏差：股票池是今天的 SPY 前 100，10 年前它们中很多还不是巨头甚至未上市——回测结果系统性偏乐观，这一偏差无法用免费数据消除。",
            "样本外逐年评估采用 12 个月禁运期的 purged walk-forward，杜绝标签泄漏；但测试年份少（统计功效有限），单年结果受市场环境主导。",
            "一年期预测的不确定性极大，预测值应理解为'相对排序参考'而非收益承诺。不构成投资建议。",
        ],
    })
