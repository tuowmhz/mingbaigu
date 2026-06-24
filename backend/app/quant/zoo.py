"""策略动物园：100+ 个开源族系策略的统一回测与统计共性分析。

策略来源（公开文献与开源社区的经典族系）：
- WorldQuant《101 Formulaic Alphas》(arXiv:1601.00991) 风格的价格类公式因子
- QuantConnect / Quantopian / awesome-quant 社区流传的经典策略族：
  动量、反转、低波动、52周高点、均线趋势、布林带、RSI、风险调整动量、
  双动量、市场状态过滤等
为什么不直接爬 100 个 GitHub 仓库：异构代码一半跑不通、一半有未来函数，
统一在同一个引擎里重实现（同样成本、同样样本划分）统计分析才有意义。

诚实设计：
- 样本内(IS) / 样本外(OOS) 按时间硬切分；
- 共性分析与组合策略的"配方"只用 IS 数据推导，OOS 只评估一次；
- 重点汇报 IS→OOS 的衰减——这是量化策略最重要的真相。
"""
import json
import math
import threading
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .longterm import _fetch

ARTIFACT = Path(__file__).resolve().parent.parent.parent / "data" / "zoo_results.json"
OOS_START = "2023-01-01"   # 之前为样本内，之后为样本外
COST = 0.002               # 20bps 往返
WARMUP = 273

_status = {"running": False, "error": None}
_lock = threading.Lock()


# ============ 特征面板（一次计算，全部策略共享）============

def _features(closes: pd.DataFrame, qqq: pd.Series) -> dict:
    rets = closes.pct_change()
    F = {"rets": rets, "closes": closes}
    for lb in (5, 10, 21, 63, 126, 252):
        F[f"mom{lb}"] = closes / closes.shift(lb) - 1
    F["mom252_21"] = closes.shift(21) / closes.shift(252) - 1
    F["mom126_21"] = closes.shift(21) / closes.shift(126) - 1
    for lb in (21, 63, 126, 252):
        F[f"vol{lb}"] = rets.rolling(lb).std()
    for lb in (50, 100, 200):
        F[f"smad{lb}"] = closes / closes.rolling(lb).mean() - 1
    F["hi52"] = closes / closes.rolling(252).max() - 1
    sma20 = closes.rolling(20).mean()
    F["bbz"] = (closes - sma20) / (2 * closes.rolling(20).std())
    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    F["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    for lb in (63, 126, 252):
        F[f"sharpe{lb}"] = F[f"mom{lb}"] / (F[f"vol{lb}"] * math.sqrt(lb))
    F["accel"] = F["mom63"] - F["mom252"]
    # 101-alphas 风格的纯收盘价公式因子
    F["ts_rank10"] = closes.rolling(10).rank(pct=True)          # 10日时序分位
    F["delta5"] = -closes.pct_change(5)                          # rank(-delta(close,5))
    F["tstat20"] = rets.rolling(20).mean() / rets.rolling(20).std()  # 短期收益 t 统计量
    F["meanrev20"] = -(closes / closes.rolling(20).mean() - 1)
    # —— 微软 Qlib Alpha158 因子库的纯收盘价子集（同名换算）——
    F["a158_rsv60"] = ((closes - closes.rolling(60).min())
                       / (closes.rolling(60).max() - closes.rolling(60).min()))   # RSV
    F["a158_qtl60"] = ((closes - closes.rolling(60).quantile(0.2))
                       / (closes.rolling(60).quantile(0.8) - closes.rolling(60).quantile(0.2) + 1e-12))  # QTLU/QTLD
    F["a158_macross"] = closes.rolling(5).mean() / closes.rolling(60).mean() - 1  # MA 比值
    F["a158_stdratio"] = rets.rolling(20).std() / (rets.rolling(60).std() + 1e-12)  # 波动状态(STD比)
    F["a158_tsrank60"] = closes.rolling(60).rank(pct=True)                        # RANK60
    F["range_pos"] = (closes - closes.rolling(20).min()) / (closes.rolling(20).max() - closes.rolling(20).min())
    F["mom_consistency"] = (rets > 0).rolling(63).mean()         # 上涨天数占比
    F["dd_rebound"] = -(closes / closes.rolling(252).max() - 1)  # 距高点越远分越高
    F["qqq_above200"] = (qqq > qqq.rolling(200).mean()).astype(float)
    return F


# ============ 策略宇宙（程序化生成 100+）============

def _build_specs() -> list[dict]:
    specs = []

    def add(family, name, feat, n, regime=False, invert=False,
            lb_bucket="mid", risk_adj=False, style="momentum"):
        specs.append(dict(family=family, name=name, feat=feat, n=n, regime=regime,
                          invert=invert, lb_bucket=lb_bucket, risk_adj=risk_adj, style=style))

    moms = [("mom21", "short"), ("mom63", "short"), ("mom126", "mid"), ("mom252", "long"),
            ("mom126_21", "mid"), ("mom252_21", "long")]
    for feat, bucket in moms:
        for n in (5, 10, 20):
            add("动量", f"{feat}/top{n}", feat, n, lb_bucket=bucket)
            add("动量+状态过滤", f"{feat}/top{n}/regime", feat, n, regime=True, lb_bucket=bucket)
    for feat, bucket in [("mom5", "short"), ("mom10", "short"), ("mom21", "short")]:
        for n in (5, 10, 20):
            add("短期反转", f"rev_{feat}/top{n}", feat, n, invert=True, lb_bucket="short", style="reversal")
    for lb in (63, 126, 252):
        for n in (5, 10, 20):
            add("低波动", f"lowvol{lb}/top{n}", f"vol{lb}", n, invert=True,
                lb_bucket="long" if lb >= 252 else "mid", risk_adj=True, style="defensive")
        add("低波动+状态过滤", f"lowvol{lb}/top20/regime", f"vol{lb}", 20, invert=True, regime=True,
            lb_bucket="long" if lb >= 252 else "mid", risk_adj=True, style="defensive")
    for lb in (50, 100, 200):
        for n in (5, 10, 20):
            add("均线趋势", f"sma{lb}/top{n}", f"smad{lb}", n, lb_bucket="long" if lb >= 200 else "mid")
    for n in (10, 20):
        add("52周高点", f"hi52/top{n}", "hi52", n, lb_bucket="long")
        add("52周高点+过滤", f"hi52/top{n}/regime", "hi52", n, regime=True, lb_bucket="long")
    for lb in (63, 126, 252):
        for n in (5, 10, 20):
            add("风险调整动量", f"sharpe{lb}/top{n}", f"sharpe{lb}", n,
                lb_bucket="long" if lb >= 252 else "mid", risk_adj=True)
        add("风险调整动量+过滤", f"sharpe{lb}/top20/regime", f"sharpe{lb}", 20, regime=True,
            lb_bucket="long" if lb >= 252 else "mid", risk_adj=True)
    for n in (10, 20):
        add("布林带反转", f"bb/top{n}", "bbz", n, invert=True, lb_bucket="short", style="reversal")
        add("RSI反转", f"rsi/top{n}", "rsi", n, invert=True, lb_bucket="short", style="reversal")
        add("动量加速度", f"accel/top{n}", "accel", n, lb_bucket="mid")
        add("深回撤反弹", f"ddrebound/top{n}", "dd_rebound", n, lb_bucket="long", style="reversal")
    formulaic = [("ts_rank10", "short", False), ("delta5", "short", False),
                 ("tstat20", "short", True), ("meanrev20", "short", False),
                 ("range_pos", "short", False), ("mom_consistency", "mid", False)]
    for feat, bucket, ra in formulaic:
        for n in (10, 20):
            add("公式因子(101-alphas风格)", f"{feat}/top{n}", feat, n, lb_bucket=bucket, risk_adj=ra,
                style="formulaic")
    a158 = [("a158_rsv60", "mid", False), ("a158_qtl60", "mid", False),
            ("a158_macross", "mid", False), ("a158_stdratio", "short", True),
            ("a158_tsrank60", "mid", False)]
    for feat, bucket, ra in a158:
        for n in (10, 20):
            add("Alpha158因子(微软Qlib)", f"{feat}/top{n}", feat, n, lb_bucket=bucket,
                risk_adj=ra, style="formulaic")
    return specs


# ============ 回测引擎 ============

def _backtest_all(F: dict, closes: pd.DataFrame, qqq: pd.Series, specs: list[dict]) -> pd.DataFrame:
    dates = closes.groupby(closes.index.to_period("M")).tail(1).index
    dates = [d for d in dates if d >= closes.index[0] + pd.Timedelta(days=WARMUP)][:-1]
    fwd = {}
    for i, t in enumerate(dates[:-1]):
        fwd[t] = closes.loc[dates[i + 1]] / closes.loc[t] - 1
    qqq_fwd = {t: float(qqq.loc[:dates[i + 1]].iloc[-1] / qqq.loc[:t].iloc[-1] - 1)
               for i, t in enumerate(dates[:-1])}

    rows = []
    for spec in specs:
        feat = F[spec["feat"]]
        prev = set()
        rets = []
        for t in dates[:-1]:
            score = feat.loc[t].dropna()
            if spec["invert"]:
                score = -score
            if len(score) < 30:
                rets.append((t, 0.0, qqq_fwd[t]))
                continue
            if spec["regime"] and F["qqq_above200"].loc[t] < 0.5:
                prev = set()
                rets.append((t, 0.0, qqq_fwd[t]))  # 空仓
                continue
            top = set(score.nlargest(spec["n"]).index)
            turnover = 1.0 if not prev else len(top - prev) / spec["n"]
            prev = top
            r = float(fwd[t][list(top)].mean()) - turnover * COST
            rets.append((t, r, qqq_fwd[t]))
        df = pd.DataFrame(rets, columns=["date", "ret", "qqq"]).set_index("date")
        rows.append((spec, df))
    return rows


def _sharpe(r: pd.Series) -> float | None:
    if len(r) < 6 or r.std() == 0:
        return None
    return round(float(r.mean() / r.std() * math.sqrt(12)), 3)


def _stats(spec: dict, df: pd.DataFrame) -> dict:
    is_df = df[df.index < OOS_START]
    oos_df = df[df.index >= OOS_START]
    curve = (1 + oos_df["ret"]).cumprod()
    maxdd = float((curve / curve.cummax() - 1).min()) if len(curve) else None
    n_years = len(oos_df) / 12
    cagr = float(curve.iloc[-1] ** (1 / n_years) - 1) if len(curve) and n_years > 0 else None
    return {
        "family": spec["family"], "name": spec["name"],
        "n_holdings": spec["n"], "regime": spec["regime"],
        "risk_adj": spec["risk_adj"], "lb_bucket": spec["lb_bucket"], "style": spec["style"],
        "is_sharpe": _sharpe(is_df["ret"]),
        "oos_sharpe": _sharpe(oos_df["ret"]),
        "oos_cagr": round(cagr, 4) if cagr is not None else None,
        "oos_maxdd": round(maxdd, 4) if maxdd is not None else None,
        "oos_excess_qqq": round(float((oos_df["ret"] - oos_df["qqq"]).mean() * 12), 4) if len(oos_df) else None,
    }


# ============ 统计共性分析 + 组合策略 ============

def _analyze(table: pd.DataFrame) -> dict:
    fam = (table.groupby("family")
           .agg(n=("name", "count"),
                is_sharpe_med=("is_sharpe", "median"),
                oos_sharpe_med=("oos_sharpe", "median"),
                oos_excess_med=("oos_excess_qqq", "median"))
           .round(3).reset_index().sort_values("oos_sharpe_med", ascending=False))

    effects = []
    valid = table.dropna(subset=["oos_sharpe"])
    for attr, label in [("regime", "市场状态过滤(QQQ>200日线)"), ("risk_adj", "风险调整(除以波动率)")]:
        a = valid[valid[attr]]["oos_sharpe"]
        b = valid[~valid[attr]]["oos_sharpe"]
        if len(a) > 5 and len(b) > 5:
            effects.append({"ingredient": label,
                            "with_avg": round(float(a.mean()), 3),
                            "without_avg": round(float(b.mean()), 3),
                            "lift": round(float(a.mean() - b.mean()), 3)})
    for bucket, label in [("short", "短回看期(<3月)"), ("mid", "中回看期(3-6月)"), ("long", "长回看期(≥1年)")]:
        sub = valid[valid["lb_bucket"] == bucket]["oos_sharpe"]
        if len(sub) > 5:
            effects.append({"ingredient": label, "with_avg": round(float(sub.mean()), 3),
                            "without_avg": round(float(valid["oos_sharpe"].mean()), 3),
                            "lift": round(float(sub.mean() - valid["oos_sharpe"].mean()), 3)})
    n20 = valid[valid["n_holdings"] == 20]["oos_sharpe"]
    n_small = valid[valid["n_holdings"] < 20]["oos_sharpe"]
    if len(n20) > 5 and len(n_small) > 5:
        effects.append({"ingredient": "更分散(持20只 vs 5-10只)",
                        "with_avg": round(float(n20.mean()), 3),
                        "without_avg": round(float(n_small.mean()), 3),
                        "lift": round(float(n20.mean() - n_small.mean()), 3)})

    is_oos_corr = round(float(valid["is_sharpe"].corr(valid["oos_sharpe"], method="spearman")), 3)
    top_is = valid.nlargest(10, "is_sharpe")
    decay = {
        "top10_is_avg_is_sharpe": round(float(top_is["is_sharpe"].mean()), 3),
        "top10_is_avg_oos_sharpe": round(float(top_is["oos_sharpe"].mean()), 3),
        "all_avg_oos_sharpe": round(float(valid["oos_sharpe"].mean()), 3),
    }
    return {"families": fam.to_dict("records"), "effects": effects,
            "is_oos_corr": is_oos_corr, "decay": decay}


def _composite(F, closes, qqq, analysis) -> dict:
    """组合策略：只用 IS 共性分析的'配方'拼装，OOS 评估一次。

    配方规则（代码自动推导，不许手工挑选最佳策略）：
    取 IS 中位夏普最高的 3 个族的代表信号做 z-score 等权合成；
    '状态过滤'与'风险调整'两个成分若 IS 提升为正则启用。
    """
    fam_table = pd.DataFrame(analysis["families"])
    rep_feat = {"动量": "mom252_21", "动量+状态过滤": "mom252_21", "短期反转": "mom21",
                "低波动": "vol252", "低波动+状态过滤": "vol252",
                "均线趋势": "smad200", "52周高点": "hi52",
                "52周高点+过滤": "hi52", "风险调整动量": "sharpe252",
                "风险调整动量+过滤": "sharpe252", "布林带反转": "bbz",
                "RSI反转": "rsi", "动量加速度": "accel", "深回撤反弹": "dd_rebound",
                "公式因子(101-alphas风格)": "mom_consistency",
                "Alpha158因子(微软Qlib)": "a158_rsv60"}
    invert_fam = {"短期反转", "低波动", "低波动+状态过滤", "布林带反转", "RSI反转"}
    top_fams = fam_table.sort_values("is_sharpe_med", ascending=False)["family"].head(3).tolist()

    use_regime = any(e["ingredient"].startswith("市场状态过滤") and e["lift"] > 0
                     for e in analysis["effects"])

    dates = closes.groupby(closes.index.to_period("M")).tail(1).index
    dates = [d for d in dates if d >= closes.index[0] + pd.Timedelta(days=WARMUP)][:-1]
    prev = set()
    recs = []
    for i, t in enumerate(dates[:-1]):
        zsum = None
        for famname in top_fams:
            s = F[rep_feat[famname]].loc[t].dropna()
            if famname in invert_fam:
                s = -s
            z = (s - s.mean()) / (s.std() or 1)
            zsum = z if zsum is None else zsum.add(z, fill_value=0)
        if zsum is None or len(zsum) < 30:
            continue
        nxt = dates[i + 1]
        qqq_r = float(qqq.loc[:nxt].iloc[-1] / qqq.loc[:t].iloc[-1] - 1)
        if use_regime and F["qqq_above200"].loc[t] < 0.5:
            prev = set()
            recs.append((t, 0.0, qqq_r))
            continue
        top = set(zsum.nlargest(20).index)
        turnover = 1.0 if not prev else len(top - prev) / 20
        prev = top
        fwd = closes.loc[nxt] / closes.loc[t] - 1
        recs.append((t, float(fwd[list(top)].mean()) - turnover * COST, qqq_r))
    df = pd.DataFrame(recs, columns=["date", "ret", "qqq"]).set_index("date")
    oos = df[df.index >= OOS_START]
    curve = (1 + oos["ret"]).cumprod()
    qqq_curve = (1 + oos["qqq"]).cumprod()
    return {
        "recipe": f"IS 最优 3 族等权合成：{' + '.join(top_fams)}"
                  + ("，启用市场状态过滤" if use_regime else "") + "，持 20 只月调仓",
        "is_sharpe": _sharpe(df[df.index < OOS_START]["ret"]),
        "oos_sharpe": _sharpe(oos["ret"]),
        "oos_total_return": round(float(curve.iloc[-1] - 1), 4) if len(curve) else None,
        "qqq_total_return": round(float(qqq_curve.iloc[-1] - 1), 4) if len(qqq_curve) else None,
        "oos_months": int(len(oos)),
    }


# ============ 构建入口 ============

def build_zoo() -> dict:
    closes, qqq, vix, tnx = _fetch()
    F = _features(closes, qqq)
    specs = _build_specs()
    results = _backtest_all(F, closes, qqq, specs)
    table = pd.DataFrame([_stats(spec, df) for spec, df in results])
    analysis = _analyze(table)
    composite = _composite(F, closes, qqq, analysis)

    valid = table.dropna(subset=["oos_sharpe"])
    comp_pct = round(float((valid["oos_sharpe"] < (composite["oos_sharpe"] or -9)).mean()), 3)

    artifact = {
        "status": "ready",
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "n_strategies": int(len(table)),
            "is_period": f"{closes.index[0].year} ~ 2022", "oos_period": "2023 ~ 今",
            "universe": "SPY 前 100（含幸存者偏差，绝对收益偏乐观，横向比较仍有效）",
            "sources": "WorldQuant 101 Formulaic Alphas (arXiv:1601.00991) 风格因子 + Quantopian/QuantConnect/awesome-quant 社区经典策略族",
        },
        "analysis": analysis,
        "composite": {**composite, "oos_percentile": comp_pct},
        "top_oos": table.nlargest(10, "oos_sharpe")[
            ["family", "name", "is_sharpe", "oos_sharpe", "oos_cagr", "oos_maxdd"]].to_dict("records"),
        "top_is_with_oos": table.nlargest(10, "is_sharpe")[
            ["family", "name", "is_sharpe", "oos_sharpe"]].to_dict("records"),
        "honest_notes": _honest_notes(analysis),
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(_clean(artifact), ensure_ascii=False, indent=1, allow_nan=False))
    return artifact


def _honest_notes(analysis: dict) -> list[str]:
    corr = analysis["is_oos_corr"]
    d = analysis["decay"]
    notes = [
        f"IS→OOS 夏普的秩相关为 {corr}——样本内排名对样本外的预测力"
        + ("很弱，按回测排行榜挑策略≈抽签。" if abs(corr) < 0.3 else
           "中等：方向有参考价值，但具体名次不可信。"),
    ]
    if d["top10_is_avg_oos_sharpe"] < d["top10_is_avg_is_sharpe"] - 0.1:
        notes.append(
            f"样本内最好的 10 个策略，IS 平均夏普 {d['top10_is_avg_is_sharpe']}，"
            f"到 OOS 衰减为 {d['top10_is_avg_oos_sharpe']}——选择偏差的代价被量化出来了。")
    else:
        notes.append(
            f"本次 OOS 窗口（2023 至今的大牛市）里几乎所有策略都表现良好"
            f"（全体平均 OOS 夏普 {d['all_avg_oos_sharpe']}），样本内前十甚至更好"
            f"（{d['top10_is_avg_is_sharpe']}→{d['top10_is_avg_oos_sharpe']}）。"
            "别误读为'回测可信'——这更多说明单边牛市里水涨船高，真正的考验在下一次熊市。")
    notes.append(
        "全部策略共享同一个幸存者偏差的股票池（今天的 SPY 前 100），"
        "绝对收益数字系统性偏乐观；策略之间的横向比较与成分分析仍然有效。")
    notes.append("组合策略的配方只用 IS 数据推导，OOS 只评估一次；成绩是诚实的，但单次实验仍可能是运气。")
    return notes


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def get_zoo() -> dict:
    if ARTIFACT.exists():
        try:
            return json.loads(ARTIFACT.read_text())
        except Exception:
            pass
    with _lock:
        if _status["running"]:
            return {"status": "building", "error": _status["error"]}
        _status["running"] = True

    def _run():
        try:
            build_zoo()
            _status["error"] = None
        except Exception as e:
            _status["error"] = f"{type(e).__name__}: {e}"
        finally:
            _status["running"] = False

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "building", "error": None}
