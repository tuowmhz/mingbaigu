"""横截面面板量化模型：全池 pooled、6 个月、预测相对大盘的超额收益。

为什么比旧模型强（旧：单票·5日·绝对涨跌 → 样本外 edge 为负）：
- 把全池 ~100 只票 × 10 年 pooled 训练（数万样本，而非单票 350 行）；
- 预测 126 日（6 个月）相对 SPY 的超额收益——长周期有可学的动量/质量信号；
- 目标是"跑赢大盘"（基准 ~50%），而非"绝对上涨"（牛市基准 ~70% 无法体现技巧）；
- 横截面排名归一化 + 严格 walk-forward + embargo 防标签穿越。

诚实：universe 用当前 SPY 前100权重，有幸存者偏差，结果系统性偏乐观，应用层如实标注。
模型的技巧在"排序/两端"，对中段个股近乎掷硬币——成绩单只对'高/低评级'计真章。
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# 产物存放在 app 包内（随 Docker COPY backend/app 一起进镜像；/app/data 是 Fly 卷会遮挡，故不放那）
ART = Path(__file__).resolve().parent / "artifacts" / "panel_model.pkl"
META = Path(__file__).resolve().parent / "artifacts" / "panel_model.json"
HORIZON = 126  # 6 个月 ≈ 126 交易日
BENCHMARK = "SPY"

BASE_FEAT = ["ret_21", "ret_63", "ret_126", "ret_252", "mom_12_1", "c_sma50",
             "sma50_200", "c_sma200", "rsi14", "dist_hi", "dist_lo", "vol20",
             "vol60", "rs_63", "mkt_bull", "mkt_vol"]
RANK_FEAT = ["ret_126", "ret_21", "mom_12_1", "vol20", "dist_hi", "rsi14"]
FEAT = BASE_FEAT + [f"rk_{c}" for c in RANK_FEAT]


def _rsi(c, w=14):
    d = c.diff(); g = d.clip(lower=0).rolling(w).mean(); l = (-d.clip(upper=0)).rolling(w).mean()
    return 100 - 100 / (1 + g / l.replace(0, np.nan))


def _base_features(close: pd.Series, spy: pd.Series) -> pd.DataFrame:
    """单票时间序列特征（不含横截面排名、不含未来标签）。"""
    c = close.dropna()
    s = spy.reindex(c.index)
    f = pd.DataFrame(index=c.index)
    f["ret_21"] = c.pct_change(21); f["ret_63"] = c.pct_change(63)
    f["ret_126"] = c.pct_change(126); f["ret_252"] = c.pct_change(252)
    f["mom_12_1"] = c.shift(21).pct_change(231)
    sma50 = c.rolling(50).mean(); sma200 = c.rolling(200).mean()
    f["c_sma50"] = c / sma50 - 1; f["sma50_200"] = sma50 / sma200 - 1; f["c_sma200"] = c / sma200 - 1
    f["rsi14"] = _rsi(c)
    hi = c.rolling(252, min_periods=120).max(); lo = c.rolling(252, min_periods=120).min()
    f["dist_hi"] = c / hi - 1; f["dist_lo"] = c / lo - 1
    f["vol20"] = c.pct_change().rolling(20).std(); f["vol60"] = c.pct_change().rolling(60).std()
    f["rs_63"] = c.pct_change(63) - s.pct_change(63)
    sma200_spy = spy.rolling(200).mean().reindex(c.index)
    f["mkt_bull"] = (s > sma200_spy).astype(float)
    f["mkt_vol"] = spy.pct_change().rolling(20).std().reindex(c.index)
    return f


# ───────────────────────── 训练 ─────────────────────────

def train_and_save(period: str = "10y") -> dict:
    import joblib
    import yfinance as yf
    from scipy.stats import spearmanr
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.isotonic import IsotonicRegression

    from ..quant.universe import TRAIN_UNIVERSE

    raw = yf.download(TRAIN_UNIVERSE + [BENCHMARK], period=period, auto_adjust=True, progress=False)["Close"]
    raw = raw.dropna(axis=1, how="all")
    spy = raw[BENCHMARK]
    stocks = [t for t in raw.columns if t != BENCHMARK]

    parts = []
    for t in stocks:
        c = raw[t].dropna()
        if len(c) < 300:
            continue
        f = _base_features(c, spy)
        s = spy.reindex(c.index)
        fwd = c.shift(-HORIZON) / c - 1
        fwd_spy = s.shift(-HORIZON) / s - 1
        f["fwd_excess"] = fwd - fwd_spy
        f["ticker"] = t; f["date"] = c.index
        parts.append(f)
    panel = pd.concat(parts, ignore_index=True)
    for col in RANK_FEAT:
        panel[f"rk_{col}"] = panel.groupby("date")[col].rank(pct=True)
    panel = panel.dropna(subset=FEAT).sort_values("date").reset_index(drop=True)

    # 月度采样降低重叠标签的自相关
    panel["di"] = panel.groupby("ticker").cumcount()
    samp = panel[panel["di"] % 21 == 0].copy()
    labeled = samp.dropna(subset=["fwd_excess"]).reset_index(drop=True)

    # walk-forward（embargo≈一个 horizon）求样本外指标 + 校准器
    dates = np.sort(labeled["date"].unique()); n = len(dates); start = int(n * 0.4)
    edges = np.linspace(start, n, 7).astype(int)
    oos_pred, oos_excess = [], []
    for i in range(6):
        te0, te1 = edges[i], edges[i + 1]
        if te1 <= te0:
            continue
        cut = pd.Timestamp(dates[te0]); emb = cut - pd.Timedelta(days=int(HORIZON * 1.6))
        tr = labeled[labeled["date"] < emb]
        te = labeled[labeled["date"].isin(set(dates[te0:te1]))]
        if len(tr) < 800 or len(te) < 50:
            continue
        m = _make_reg()
        m.fit(tr[FEAT].to_numpy(), tr["fwd_excess"].to_numpy())
        oos_pred.extend(m.predict(te[FEAT].to_numpy()))
        oos_excess.extend(te["fwd_excess"].to_numpy())
    oos_pred, oos_excess = np.array(oos_pred), np.array(oos_excess)

    ic = float(spearmanr(oos_pred, oos_excess).correlation)
    q = pd.qcut(oos_pred, 5, labels=False, duplicates="drop")
    top_hit = float((oos_excess[q == 4] > 0).mean())          # 顶档真实跑赢大盘比例
    bot_hit = float((oos_excess[q == 0] > 0).mean())
    long_short = float(oos_excess[q == 4].mean() - oos_excess[q == 0].mean())
    sign_acc = float(((oos_pred > 0) == (oos_excess > 0)).mean())
    base_rate = float((oos_excess > 0).mean())

    # 校准器：预测超额 → P(跑赢大盘)，等距回归，单调
    cal = IsotonicRegression(out_of_bounds="clip", y_min=0.05, y_max=0.95)
    cal.fit(oos_pred, (oos_excess > 0).astype(float))

    # 最终模型：全部已标注数据
    final = _make_reg()
    final.fit(labeled[FEAT].to_numpy(), labeled["fwd_excess"].to_numpy())

    # 排名快照：每只票最新一行的 RANK_FEAT 原值（供单票横截面定位）
    latest = panel.sort_values("date").groupby("ticker").tail(1)
    rank_ref = {c: np.sort(latest[c].dropna().to_numpy()) for c in RANK_FEAT}
    # 预测超额的全池参考分布（供分档 tier）
    pred_ref = np.sort(final.predict(latest[FEAT].to_numpy()))

    importances = _feature_importance(final, labeled[FEAT].to_numpy(), labeled["fwd_excess"].to_numpy())

    meta = {
        "horizon_days": HORIZON, "n_oos": int(len(oos_pred)), "n_train": int(len(labeled)),
        "ic": round(ic, 4), "top_tier_hit_rate": round(top_hit, 4),
        "bottom_tier_hit_rate": round(bot_hit, 4), "sign_accuracy": round(sign_acc, 4),
        "beat_base_rate": round(base_rate, 4), "long_short_6m_pct": round(long_short * 100, 2),
        "n_universe": len(stocks),
        "top_features": importances,
    }
    ART.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": final, "calibrator": cal, "feat": FEAT, "rank_feat": RANK_FEAT,
                 "rank_ref": rank_ref, "pred_ref": pred_ref, "horizon": HORIZON}, ART)
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return meta


def _make_reg():
    from sklearn.ensemble import HistGradientBoostingRegressor
    return HistGradientBoostingRegressor(max_iter=300, max_depth=4, learning_rate=0.05,
                                         min_samples_leaf=40, l2_regularization=1.0, random_state=42)


def _feature_importance(model, X, y, n_top=5):
    rng = np.random.default_rng(42)
    base = _r2(model.predict(X), y)
    drops = []
    for i, col in enumerate(FEAT):
        Xp = X.copy(); Xp[:, i] = rng.permutation(Xp[:, i])
        drops.append((col, float(base - _r2(model.predict(Xp), y))))
    drops.sort(key=lambda t: -t[1])
    return [{"feature": c, "importance": round(d, 4)} for c, d in drops[:n_top] if d > 0]


def _r2(p, y):
    ss = ((y - y.mean()) ** 2).sum()
    return float(1 - ((y - p) ** 2).sum() / ss) if ss else 0.0


# ───────────────────────── 推理 ─────────────────────────

_CACHE = {}


def _load():
    if "art" not in _CACHE:
        try:
            import joblib
            _CACHE["art"] = joblib.load(ART)
            _CACHE["meta"] = json.loads(META.read_text())
        except Exception:
            _CACHE["art"] = None; _CACHE["meta"] = None
    return _CACHE["art"], _CACHE["meta"]


def metrics() -> dict | None:
    return _load()[1]


def predict_panel(ticker: str, as_of: str) -> dict | None:
    art, meta = _load()
    if art is None:
        return None
    from ..data.market import get_history
    df = get_history(ticker, period="2y")
    spy_df = get_history(BENCHMARK, period="2y")
    if df is None or spy_df is None or len(df) < 252:
        return None
    f = _base_features(df["Close"], spy_df["Close"]).dropna(subset=BASE_FEAT)
    if f.empty:
        return None
    row = f.iloc[-1]
    # 横截面排名：与训练时全池最新分布对比定位
    ranks = {}
    for c in art["rank_feat"]:
        ref = art["rank_ref"][c]
        ranks[f"rk_{c}"] = float(np.searchsorted(ref, row[c]) / max(len(ref), 1))
    x = np.array([[row[c] if c in BASE_FEAT else ranks[c] for c in art["feat"]]])
    pred_excess = float(art["model"].predict(x)[0])
    prob_beat = float(art["calibrator"].predict([pred_excess])[0])
    tier_pct = float(np.searchsorted(art["pred_ref"], pred_excess) / max(len(art["pred_ref"]), 1))
    tier = ("top" if tier_pct >= 0.8 else "upper" if tier_pct >= 0.6
            else "mid" if tier_pct >= 0.4 else "lower" if tier_pct >= 0.2 else "bottom")

    return {
        "horizon_days": art["horizon"],
        "target": "excess_vs_market",
        "prob_up": round(prob_beat, 4),                 # 兼容旧键：语义=跑赢大盘概率
        "expected_return_pct": round(pred_excess * 100, 2),  # 预期相对大盘超额收益
        "direction": "outperform" if pred_excess > 0 else "underperform",
        "rank_pct": round(tier_pct * 100, 1),
        "tier": tier,
        "backtest": {
            "n_oos": meta["n_oos"],
            "ic": meta["ic"],
            "accuracy": meta["top_tier_hit_rate"],   # 顶档"跑赢大盘"命中率（≥50% 的诚实口径）
            "baseline": meta["beat_base_rate"],
            "edge": round(meta["top_tier_hit_rate"] - meta["beat_base_rate"], 4),
            "long_short_6m_pct": meta["long_short_6m_pct"],
            "sign_accuracy": meta["sign_accuracy"],
            "high_conf_accuracy": meta["top_tier_hit_rate"],
        },
        "top_features": meta["top_features"],
        "n_train_samples": meta["n_train"],
        "as_of": as_of,
    }
