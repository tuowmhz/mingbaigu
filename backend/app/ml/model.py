"""机器学习预测：梯度提升 + walk-forward（滚动前推）回测。

诚实原则：
- 回测全部使用样本外（out-of-sample）预测，不用训练集成绩自欺；
- 同时报告"无脑看多"基准的命中率，模型优势 = 模型命中率 - 基准命中率；
- 短期股价信噪比极低，任何模型的优势都很薄，结果仅供参考。
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from ..cache import cached
from ..config import CACHE_TTL_MODEL
from ..data.market import get_history
from .features import FEATURE_COLS, HORIZON, build_features

MIN_TRAIN = 150       # 首个训练窗口的最小样本数
N_FOLDS = 6           # walk-forward 折数


def _make_clf():
    return HistGradientBoostingClassifier(
        max_iter=200, max_depth=3, learning_rate=0.05,
        min_samples_leaf=20, random_state=42,
    )


def _make_reg():
    return HistGradientBoostingRegressor(
        max_iter=200, max_depth=3, learning_rate=0.05,
        min_samples_leaf=20, random_state=42,
    )


def walk_forward_backtest(X: np.ndarray, y_up: np.ndarray) -> dict:
    """滚动前推：每折用过去全部数据训练、预测下一段，纯样本外。"""
    n = len(X)
    fold_size = max(20, (n - MIN_TRAIN) // N_FOLDS)
    preds, probs, actuals = [], [], []
    start = MIN_TRAIN
    while start < n:
        end = min(start + fold_size, n)
        clf = _make_clf()
        clf.fit(X[:start], y_up[:start])
        p = clf.predict_proba(X[start:end])[:, 1]
        probs.extend(p)
        preds.extend((p > 0.5).astype(int))
        actuals.extend(y_up[start:end])
        start = end
    preds, probs, actuals = np.array(preds), np.array(probs), np.array(actuals)
    if len(preds) == 0:
        return {"n_oos": 0, "accuracy": None, "baseline": None, "edge": None,
                "high_conf_accuracy": None}
    acc = float((preds == actuals).mean())
    baseline = float(max(actuals.mean(), 1 - actuals.mean()))  # 多数类基准
    high_conf = np.abs(probs - 0.5) > 0.1
    return {
        "n_oos": int(len(preds)),
        "accuracy": round(acc, 4),
        "baseline": round(baseline, 4),
        "edge": round(acc - baseline, 4),
        "high_conf_accuracy": round(float((preds[high_conf] == actuals[high_conf]).mean()), 4)
        if high_conf.sum() >= 20 else None,
    }


@cached(CACHE_TTL_MODEL)
def predict(ticker: str, as_of: str) -> dict | None:
    """横截面面板量化模型：预测未来约半年（126 交易日）相对大盘的超额收益。

    实现见 ml/panel.py——全池 pooled 训练、严格 walk-forward + embargo、
    目标为"跑赢大盘"（基准 ~50%，可被检验）。旧的单票·5日·绝对涨跌范式已弃用
    （样本外 edge 为负，无法做 benchmark）。as_of 仅作缓存键。
    """
    from .panel import predict_panel
    return predict_panel(ticker, as_of)


def _permutation_importance_proxy(clf, X, y, n_top=4):
    """轻量特征重要性：逐列打乱看准确率掉多少。"""
    rng = np.random.default_rng(42)
    base = (clf.predict(X) == y).mean()
    drops = []
    for i, col in enumerate(FEATURE_COLS):
        Xp = X.copy()
        Xp[:, i] = rng.permutation(Xp[:, i])
        drops.append((col, float(base - (clf.predict(Xp) == y).mean())))
    drops.sort(key=lambda t: -t[1])
    return [{"feature": c, "importance": round(d, 4)} for c, d in drops[:n_top] if d > 0]
