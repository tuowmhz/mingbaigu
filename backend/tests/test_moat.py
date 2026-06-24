"""定价权评分：合成单调、年报解析、诚实标注。"""
import numpy as np
import pandas as pd

from app.ml import moat


def test_score_monotonic_in_quality():
    """更高毛利/稳定度/ROE/增长 → 更高分。"""
    low = moat._score_from(0.20, 0.3, 0.05, 0.00, 0.10)
    mid = moat._score_from(0.45, 0.6, 0.20, 0.15, 0.25)
    high = moat._score_from(0.75, 0.95, 0.40, 0.40, 0.55)
    assert 0 <= low < mid < high <= 100


def test_score_handles_missing():
    s = moat._score_from(None, None, None, None, None)
    assert 0 <= s <= 100  # 不崩，给保守低分


def test_annual_margins_parsing():
    cols = pd.to_datetime(["2025-09-30", "2024-09-30", "2023-09-30"])
    inc = pd.DataFrame(
        {cols[0]: [1000, 600, 300], cols[1]: [900, 540, 260], cols[2]: [800, 470, 220]},
        index=["Total Revenue", "Gross Profit", "Operating Income"],
    )

    class _T:
        income_stmt = inc

    rows = moat._annual_margins(_T())
    assert len(rows) == 3
    assert abs(rows[0]["gross_margin"] - 0.60) < 1e-9   # 600/1000
    assert abs(rows[0]["op_margin"] - 0.30) < 1e-9


def test_annual_margins_empty_safe():
    class _T:
        income_stmt = pd.DataFrame()

    assert moat._annual_margins(_T()) == []
