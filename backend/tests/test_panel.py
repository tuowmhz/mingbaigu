"""横截面面板量化模型：产物指标、校准器单调、特征构造（不联网）。"""
import numpy as np
import pandas as pd
import pytest

from app.ml import panel


def test_metrics_artifact_present_and_skillful():
    """已训练并提交的产物：核心指标存在且体现真实选股力。"""
    m = panel.metrics()
    if m is None:
        pytest.skip("本机未训练产物")
    assert m["horizon_days"] == 126
    for k in ("ic", "top_tier_hit_rate", "beat_base_rate", "long_short_6m_pct", "n_oos"):
        assert k in m
    # 顶档跑赢大盘命中率应 > 50%（诚实口径的"正确率"）
    assert m["top_tier_hit_rate"] > 0.50
    # 且高于随机基准（有真实 edge）
    assert m["top_tier_hit_rate"] > m["beat_base_rate"]
    assert m["ic"] > 0  # 信息系数为正 = 有选股力


def test_calibrator_monotonic():
    art = panel._load()[0]
    if art is None:
        pytest.skip("本机未训练产物")
    cal = art["calibrator"]
    xs = np.linspace(-0.3, 0.3, 25)
    ys = cal.predict(xs)
    assert all(ys[i] <= ys[i + 1] + 1e-9 for i in range(len(ys) - 1))  # 预测超额↑→跑赢概率↑
    assert ys.min() >= 0.04 and ys.max() <= 0.96  # 概率被夹在合理区间


def test_base_features_no_lookahead_columns():
    idx = pd.bdate_range("2022-01-01", periods=400)
    rng = np.random.default_rng(0)
    close = pd.Series(100 * np.cumprod(1 + rng.normal(0.0003, 0.012, 400)), index=idx)
    spy = pd.Series(100 * np.cumprod(1 + rng.normal(0.0003, 0.009, 400)), index=idx)
    f = panel._base_features(close, spy)
    for c in panel.BASE_FEAT:
        assert c in f.columns
    assert not f[panel.BASE_FEAT].dropna().empty
    assert "fwd_excess" not in f.columns  # 特征里不含未来标签
