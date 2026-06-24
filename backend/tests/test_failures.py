"""跌倒地图：情境路标匹配逻辑测试。"""
from datetime import datetime, timedelta

from app.failures import (FAILURES, get_failures, match_portfolio_pitfalls,
                          match_stock_pitfalls)


class TestContent:
    def test_all_entries_complete(self):
        """每条死法必须五脏俱全：钩子/机制/代价/路标/逆向。"""
        for f in FAILURES:
            for field in ("hook", "mechanism", "cost", "signs", "inversion"):
                assert f.get(field), f"{f['id']} 缺 {field}"
            assert len(f["signs"]) >= 2, f"{f['id']} 路标太少"
            assert f["category"] in ("消息面", "行为")

    def test_munger_quote_present(self):
        assert "芒格" in get_failures()["quote"]


class TestStockMatch:
    CALM = {"momentum_20d": 0.03, "dist_52w_high": -0.05, "rsi": 50, "close_above_sma50": True}
    RISK_OK = {"annual_volatility": 0.25}

    def test_calm_stock_no_pitfalls(self):
        """平静的股票不该有路标——克制是这个功能的灵魂。"""
        assert match_stock_pitfalls(self.CALM, self.RISK_OK, {"score": 0.1}) == []

    def test_hot_chase_detected(self):
        tech = {**self.CALM, "momentum_20d": 0.35}
        out = match_stock_pitfalls(tech, self.RISK_OK, {"score": 1.0})
        assert any(p["id"] == "chase_hot" for p in out)

    def test_falling_knife_detected(self):
        tech = {**self.CALM, "dist_52w_high": -0.60}
        out = match_stock_pitfalls(tech, self.RISK_OK, None)
        assert any(p["id"] == "falling_knife" for p in out)

    def test_max_two_signposts(self):
        tech = {"momentum_20d": 0.40, "dist_52w_high": -0.50, "rsi": 80, "close_above_sma50": False}
        out = match_stock_pitfalls(tech, {"annual_volatility": 0.9}, {"score": 1.5})
        assert len(out) <= 2


class TestPortfolioMatch:
    def test_overtrading_detected(self):
        today = datetime.now().strftime("%Y-%m-%d")
        txs = [{"date": today}] * 7
        out = match_portfolio_pitfalls(txs, [])
        assert any(p["id"] == "overtrade" for p in out)

    def test_deep_loser_triggers_avg_down(self):
        positions = [{"ticker": "XYZ", "pnl_pct": -0.40, "weight": 0.1}]
        out = match_portfolio_pitfalls([], positions)
        assert any(p["id"] == "avg_down" for p in out)

    def test_healthy_portfolio_silent(self):
        old = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        positions = [{"ticker": "AAPL", "pnl_pct": 0.12, "weight": 0.15}]
        assert match_portfolio_pitfalls([{"date": old}], positions) == []
