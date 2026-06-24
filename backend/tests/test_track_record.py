"""公开成绩单：半年(126交易日)对账、以"跑赢大盘"为准、先写先赢、亏的置顶。"""
import json

import pandas as pd
import pytest

from app import track_record

HZ = track_record.HORIZON  # 126


def _series(n, total_ret):
    """n 个交易日：前 126 日恒为 100，第 126 日起跳到 100*(1+total_ret)。"""
    idx = pd.bdate_range("2024-01-01", periods=n)
    vals = [100.0 if i < HZ else 100.0 * (1 + total_ret) for i in range(n)]
    return pd.DataFrame({"Close": vals}, index=idx)


@pytest.fixture
def snap_dir(tmp_path, monkeypatch):
    d = tmp_path / "predictions"
    monkeypatch.setattr(track_record, "SNAP_DIR", d)
    return d


def _mock_history(monkeypatch, data):
    monkeypatch.setattr(track_record, "get_history", lambda t, period: data.get(t))
    return data["SPY"].index[0].strftime("%Y-%m-%d")


def test_outcome_bullish_beats_market_is_hit(monkeypatch):
    data = {"X": _series(160, 0.20), "SPY": _series(160, 0.05)}  # 个股+20% vs 大盘+5%
    aof = _mock_history(monkeypatch, data)
    out = track_record._outcome({"ticker": "X", "as_of": aof, "price": 100.0, "verdict": "bullish"})
    assert out["return_pct"] == 20.0 and out["market_pct"] == 5.0
    assert out["excess_pct"] == 15.0 and out["hit"] is True   # 看多且跑赢 → 对


def test_outcome_bullish_but_lags_market_is_miss(monkeypatch):
    data = {"X": _series(160, 0.02), "SPY": _series(160, 0.05)}  # 涨了但没跑赢大盘
    aof = _mock_history(monkeypatch, data)
    out = track_record._outcome({"ticker": "X", "as_of": aof, "price": 100.0, "verdict": "bullish"})
    assert out["excess_pct"] == -3.0 and out["hit"] is False   # 涨了≠对，没跑赢就是错


def test_outcome_neutral_unscored(monkeypatch):
    data = {"X": _series(160, 0.20), "SPY": _series(160, 0.05)}
    aof = _mock_history(monkeypatch, data)
    out = track_record._outcome({"ticker": "X", "as_of": aof, "price": 100.0, "verdict": "neutral"})
    assert out["hit"] is None


def test_outcome_pending_when_horizon_not_reached(monkeypatch):
    data = {"X": _series(60, 0.2), "SPY": _series(60, 0.05)}  # 不足 126 日
    aof = _mock_history(monkeypatch, data)
    out = track_record._outcome({"ticker": "X", "as_of": aof, "price": 100.0, "verdict": "bullish"})
    assert out is None


def test_snapshot_first_write_wins(snap_dir, monkeypatch):
    monkeypatch.setattr(track_record, "_today_utc", lambda: "2026-06-12")
    snap_dir.mkdir(parents=True)
    (snap_dir / "2026-06-12.json").write_text(json.dumps({"date": "2026-06-12", "items": [{"ticker": "FIRST"}]}))
    assert track_record.build_today_snapshot()["items"][0]["ticker"] == "FIRST"


def test_snapshot_notarized_version_wins(snap_dir, monkeypatch):
    monkeypatch.setattr(track_record, "_today_utc", lambda: "2026-06-12")
    monkeypatch.setattr(track_record, "_load_snapshot", lambda d: {"date": "2026-06-12", "items": [{"ticker": "NOTARIZED"}]})
    assert track_record.build_today_snapshot()["items"][0]["ticker"] == "NOTARIZED"


def test_track_record_aggregates_on_excess(snap_dir, monkeypatch):
    """跑赢命中率、随机基准(跑赢占比)、亏的置顶——全部基于相对大盘超额。"""
    snap_dir.mkdir(parents=True)
    data = {"A": _series(160, 0.20), "B": _series(160, 0.02), "SPY": _series(160, 0.05)}
    aof = data["SPY"].index[0].strftime("%Y-%m-%d")
    snap = {"date": aof, "items": [
        {"ticker": "A", "name": "甲", "as_of": aof, "price": 100.0, "verdict": "bullish", "verdict_cn": "偏多", "prob_up": 0.8},
        {"ticker": "B", "name": "乙", "as_of": aof, "price": 100.0, "verdict": "bullish", "verdict_cn": "偏多", "prob_up": 0.7},
    ]}
    (snap_dir / f"{aof}.json").write_text(json.dumps(snap, ensure_ascii=False))
    monkeypatch.setattr(track_record, "get_history", lambda t, period: data.get(t))
    monkeypatch.setattr(track_record, "_remote_archive_dates", lambda: [])
    monkeypatch.setattr(track_record, "_local_archive_dates", lambda: [aof])
    out = track_record.build_track_record.__wrapped__(days=400)
    assert out["stats"]["n_judged"] == 2
    assert out["stats"]["hit_rate"] == 0.5        # A 跑赢(对), B 没跑赢(错)
    assert out["stats"]["baseline_hit_rate"] == 0.5  # 仅 A 跑赢大盘
    assert out["worst_misses"][0]["ticker"] == "B"   # 没跑赢的置顶
