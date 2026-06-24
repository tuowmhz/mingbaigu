"""基本面动量：修正动能/广度计算、合成单调、诚实降级。"""
import numpy as np
import pandas as pd

from app.ml import fundamental as fm


def _eps_trend(cur_0y, old_0y, cur_1y, old_1y):
    return pd.DataFrame(
        {"current": [cur_0y, cur_1y], "90daysAgo": [old_0y, old_1y]},
        index=["0y", "+1y"],
    )


def test_revision_momentum_positive_when_upgraded():
    et = _eps_trend(11.0, 10.0, 13.2, 12.0)  # 0y +10%, +1y +10%
    assert abs(fm._revision_momentum(et) - 0.10) < 1e-9


def test_revision_momentum_negative_when_cut():
    et = _eps_trend(9.0, 10.0, 9.0, 10.0)
    assert fm._revision_momentum(et) < 0


def test_revision_breadth():
    er = pd.DataFrame({"upLast30days": [30], "downLast30days": [10]}, index=["0y"])
    assert abs(fm._revision_breadth(er) - 0.5) < 1e-9   # (30-10)/40


def test_score_monotonic():
    lo = fm._score(-0.10, -0.5)
    mid = fm._score(0.02, 0.1)
    hi = fm._score(0.15, 0.8)
    assert 0 <= lo < mid < hi <= 100


def test_score_handles_missing():
    assert 0 <= fm._score(None, None) <= 100
