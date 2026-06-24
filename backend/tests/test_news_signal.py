"""消息面引擎测试：事件抽取、分析师角色识别、方向分级。"""
from datetime import datetime, timezone

from app.analysis.news_signal import (_ALIASES, _analyze_item, _direction,
                                      _is_analyst_role, analyze_news)


def _item(title, sent=0.0, published=None):
    return {
        "title": title,
        "link": "",
        "published": published or datetime.now(timezone.utc).isoformat(),
        "source": "test",
        "sentiment": sent,
        "sentiment_label": "中性",
    }


class TestAnalystRole:
    def test_bank_upgrading_other_stock_is_analyst(self):
        title = "JPMorgan Upgrades Tesla With A Major Price Target Hike"
        assert _is_analyst_role(title, _ALIASES["JPM"]) is True

    def test_target_company_is_not_analyst(self):
        title = "JPMorgan Upgrades Tesla With A Major Price Target Hike"
        assert _is_analyst_role(title, _ALIASES["TSLA"]) is False

    def test_own_dividend_not_misjudged(self):
        assert _is_analyst_role("JPMorgan raises dividend by 10%", _ALIASES["JPM"]) is False

    def test_own_guidance_not_misjudged(self):
        assert _is_analyst_role("JPMorgan raises its full-year outlook", _ALIASES["JPM"]) is False

    def test_citi_cuts_target_on_other(self):
        assert _is_analyst_role("Citi cuts price target on Amazon", _ALIASES["C"]) is True


class TestEventExtraction:
    def test_earnings_beat_detected(self):
        out = _analyze_item(_item("Company beats estimates with record revenue", 0.5), [])
        assert "业绩超预期" in out["events"]
        assert out["impact"] > 1.5

    def test_guidance_cut_detected(self):
        out = _analyze_item(_item("Company cuts full-year guidance after weak quarter", -0.5), [])
        assert "下调指引" in out["events"]
        assert out["impact"] < -1.5

    def test_analyst_role_neutralizes_rating_event(self):
        title = "JPMorgan Upgrades Tesla With A Major Price Target Hike"
        jpm_view = _analyze_item(_item(title, 0.6), _ALIASES["JPM"])
        tsla_view = _analyze_item(_item(title, 0.6), _ALIASES["TSLA"])
        assert "评级上调" not in jpm_view["events"]
        assert "对他股评级" in jpm_view["events"]
        assert "评级上调" in tsla_view["events"]
        assert abs(jpm_view["impact"]) < 0.5 < tsla_view["impact"]


class TestDirection:
    def test_five_levels(self):
        assert _direction(2.0)[1] == "强利好"
        assert _direction(0.8)[1] == "偏暖"
        assert _direction(0.0)[1] == "不明朗"
        assert _direction(-0.8)[1] == "偏冷"
        assert _direction(-2.0)[1] == "强利空"


class TestAnalyzeNews:
    def test_bullish_news_day(self):
        news = {"items": [
            _item("Company beats estimates with record revenue", 0.6),
            _item("Company raises full-year guidance", 0.5),
            _item("Analyst upgrades stock, raises price target", 0.4),
        ]}
        sig = analyze_news(news)["signal"]
        assert sig["direction_cn"] in ("强利好", "偏暖")
        assert sig["score"] > 0.4

    def test_empty_news_returns_none(self):
        assert analyze_news(None) is None
        assert analyze_news({"items": []}) is None
