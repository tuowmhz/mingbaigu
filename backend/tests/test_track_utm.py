"""UTM 渠道归因 + 转化漏斗。"""
import pytest

from app import track


@pytest.fixture
def traffic_file(tmp_path, monkeypatch):
    monkeypatch.setattr(track, "TRAFFIC_FILE", tmp_path / "traffic.json")
    return tmp_path / "traffic.json"


def test_source_funnel_aggregation(traffic_file):
    # 小红书来 3 个人，其中 2 个测了、1 个注册
    track.record("landing", "1.1.1.1", "uaA", source="xiaohongshu")
    track.record("academy", "1.1.1.1", "uaA", source="xiaohongshu", event="quiz_done")
    track.record("landing", "2.2.2.2", "uaB", source="xiaohongshu")
    track.record("academy", "2.2.2.2", "uaB", source="xiaohongshu", event="quiz_done")
    track.record("portfolio", "2.2.2.2", "uaB", source="xiaohongshu", event="signup")
    track.record("landing", "3.3.3.3", "uaC", source="xiaohongshu")
    # 直接访问 1 人
    track.record("landing", "9.9.9.9", "uaZ")

    rep = track.report(30)
    by = {s["source"]: s for s in rep["by_source"]}
    xhs = by["xiaohongshu"]
    assert xhs["visitor_days"] == 3
    assert xhs["quiz_done"] == 2
    assert xhs["signup"] == 1
    assert xhs["quiz_rate"] == round(2 / 3, 3)
    assert by["direct"]["visitor_days"] == 1
    # 来源按访客人日降序
    assert rep["by_source"][0]["source"] == "xiaohongshu"


def test_no_source_defaults_to_direct(traffic_file):
    track.record("landing", "1.1.1.1", "ua")
    rep = track.report(30)
    assert any(s["source"] == "direct" for s in rep["by_source"])


def test_dirty_source_sanitized(traffic_file):
    track.record("landing", "1.1.1.1", "ua", source="  XiaoHongShu<script>  ")
    rep = track.report(30)
    sources = [s["source"] for s in rep["by_source"]]
    assert "xiaohongshuscript" in sources  # 小写化 + 去掉非法字符


def test_unknown_event_ignored(traffic_file):
    track.record("academy", "1.1.1.1", "ua", source="zhihu", event="evil_event")
    rep = track.report(30)
    zhihu = next(s for s in rep["by_source"] if s["source"] == "zhihu")
    assert zhihu["quiz_done"] == 0 and zhihu["signup"] == 0
