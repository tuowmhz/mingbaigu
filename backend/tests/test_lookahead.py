"""前视偏差动态单测：篡改未来、检查历史。

核心不变式：为某天 T 计算的特征，只能依赖 ≤T 的数据。
做法：把 T 之后的数据全部篡改，重算，断言 T 当天的特征逐字节不变。
并附"诱饵"：一个故意泄漏未来的特征，单测必须能抓到它（证明探测器会咬人）。

这是"诚实机器"的测试侧孪生——成绩单对外证明不改历史，本测对内证明不偷看未来。
"""
import numpy as np
import pandas as pd
import pytest

from app.ml.panel import _base_features, BASE_FEAT
from app.ml.fundamental import pit_quarter_ends


def _synth():
    idx = pd.bdate_range("2020-01-01", periods=900)
    rng = np.random.default_rng(7)
    close = pd.Series(100 * np.cumprod(1 + rng.normal(0.0004, 0.015, len(idx))), index=idx)
    spy = pd.Series(100 * np.cumprod(1 + rng.normal(0.0003, 0.010, len(idx))), index=idx)
    return close, spy


def _corrupt_after(s, T):
    """把 T 之后的值全部篡改成乱码（×100 + 巨噪声），T 及之前保持不变。"""
    s2 = s.copy()
    mask = s2.index > T
    rng = np.random.default_rng(99)
    s2.loc[mask] = s2.loc[mask] * 100 + rng.normal(0, 50, mask.sum())
    return s2


def test_base_features_have_no_lookahead():
    """篡改未来后，T 当天的全部特征必须一字不变。"""
    close, spy = _synth()
    T = close.index[-200]  # 留足未来窗口可被篡改
    full = _base_features(close, spy).loc[T, BASE_FEAT]
    corrupt = _base_features(_corrupt_after(close, T), _corrupt_after(spy, T)).loc[T, BASE_FEAT]
    assert np.allclose(full.to_numpy(dtype=float), corrupt.to_numpy(dtype=float),
                       rtol=1e-9, atol=1e-9, equal_nan=True), \
        "前视泄漏！某特征在 T 之后数据变化时改变了 T 当天的值"


def test_canary_leaky_feature_IS_caught():
    """诱饵：全样本归一化(用了全历史均值)是经典泄漏，探测器必须抓到。"""
    close, _ = _synth()
    T = close.index[-200]
    leaky_full = (close / close.mean()).loc[T]                      # 全样本均值=偷看未来
    leaky_corrupt = (_corrupt_after(close, T) / _corrupt_after(close, T).mean()).loc[T]
    assert not np.isclose(leaky_full, leaky_corrupt), \
        "探测器失灵：连全样本归一化这种泄漏都没抓到"


def test_future_shift_label_IS_caught():
    """诱饵2：用 shift(-5) 偷看未来收益，探测器必须抓到。"""
    close, _ = _synth()
    T = close.index[-200]
    peek_full = close.shift(-5).loc[T]
    peek_corrupt = _corrupt_after(close, T).shift(-5).loc[T]
    assert not np.isclose(peek_full, peek_corrupt)


def test_pit_quarter_ends_respects_filing_lag():
    """财报点位：财年末当天不可用（未披露），过滞后期后才可用；未来财报永不泄漏。"""
    ends = pd.to_datetime(["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"])
    # as-of 2024-07-01：Q1(3-31)已过75天披露，Q2(6-30)刚结束未披露
    avail = pit_quarter_ends(ends, "2024-07-01")
    assert pd.Timestamp("2024-03-31") in avail
    assert pd.Timestamp("2024-06-30") not in avail   # 6-30 财季 7-1 还没出报告
    assert pd.Timestamp("2024-12-31") not in avail   # 未来财季绝不能用


def test_pit_adding_future_statement_changes_nothing():
    """加入一个未来财报，过去某 as-of 的可用集合必须不变。"""
    ends = pd.to_datetime(["2024-03-31", "2024-06-30"])
    before = pit_quarter_ends(ends, "2024-09-15")
    ends_with_future = ends.append(pd.DatetimeIndex(["2025-03-31"]))
    after = pit_quarter_ends(ends_with_future, "2024-09-15")
    assert list(before) == list(after)
