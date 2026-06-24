"""财报页技术面人话块：位置/趋势/冷热 + 财报×股价合成。"""
import numpy as np
import pandas as pd
import pytest

from app.analysis import earnings


def _hist(prices):
    idx = pd.date_range("2025-01-01", periods=len(prices), freq="D")
    return pd.DataFrame({"Close": prices}, index=idx)


def test_returns_none_for_thin_history():
    assert earnings._technical_block(_hist([1, 2, 3]), "USD", 1, 0) is None
    assert earnings._technical_block(None, "USD", 1, 0) is None


def test_position_and_currency_symbol():
    # 300 天，末值接近最高 → 高位
    prices = list(np.linspace(100, 200, 300))
    lines = earnings._technical_block(_hist(prices), "CNY", 2, 0)
    assert lines is not None
    assert "¥" in lines[0]
    assert "高位" in lines[0] or "最高点" in lines[0]


def test_good_fundamentals_near_high_warns_priced_in():
    prices = list(np.linspace(100, 200, 300))  # 上升到高位
    lines = earnings._technical_block(_hist(prices), "USD", 3, 0)
    syn = next(l for l in lines if l.startswith("💡"))
    assert "反映在价格" in syn or "接盘" in syn


def test_weak_fundamentals_near_low():
    prices = list(np.linspace(200, 100, 300))  # 一路下跌到低位
    lines = earnings._technical_block(_hist(prices), "USD", 0, 3)
    syn = next(l for l in lines if l.startswith("💡"))
    assert "低位" in syn


def test_disclaimer_always_present():
    prices = list(np.linspace(100, 130, 300))
    lines = earnings._technical_block(_hist(prices), "USD", 1, 1)
    assert any("不预测涨跌" in l for l in lines)
