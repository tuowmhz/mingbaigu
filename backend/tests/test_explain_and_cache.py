"""人话解释格式化与缓存测试。"""
import time

from app.analysis.earnings import _yoy, fmt_pct, fmt_usd
from app.analysis.explain import explain_risk
from app.analysis.value_invest import graham_number
from app.cache import TTLCache, cached


class TestGrahamNumber:
    def test_classic_case(self):
        # EPS=5, BVPS=20 → sqrt(22.5*5*20) = sqrt(2250) ≈ 47.4
        assert abs(graham_number(5, 20) - 47.43) < 0.01

    def test_negative_eps_returns_none(self):
        assert graham_number(-2, 20) is None
        assert graham_number(None, 20) is None


class TestFormat:
    def test_fmt_usd_scales(self):
        assert fmt_usd(4.02e12) == "4.02 万亿美元"
        assert "亿美元" in fmt_usd(3.5e10)
        assert "万美元" in fmt_usd(5e5)
        assert fmt_usd(None) == "-"

    def test_fmt_pct(self):
        assert fmt_pct(0.155) == "+15.5%"
        assert fmt_pct(-0.08) == "-8.0%"
        assert fmt_pct(None) == "-"

    def test_yoy_negative_base_is_none(self):
        import pandas as pd
        s = pd.Series([10.0, -5.0])  # 上期为负，同比无意义
        assert _yoy(s) is None


class TestExplainRisk:
    RISK = {"annual_volatility": 0.45, "annual_return_1y": 0.1, "sharpe_ratio": 0.5,
            "max_drawdown": -0.35, "var_95_daily": -0.04, "beta_vs_spy": 1.6,
            "best_day": 0.1, "worst_day": -0.09}

    def test_mentions_key_numbers(self):
        lines = "\n".join(explain_risk(self.RISK, "测试股"))
        assert "45%" in lines       # 波动率
        assert "35%" in lines       # 最大回撤
        assert "1.6" in lines       # beta

    def test_high_vol_gets_warning_tone(self):
        lines = "\n".join(explain_risk(self.RISK, "测试股"))
        assert "剧烈" in lines


class TestCache:
    def test_ttl_expiry(self):
        c = TTLCache()
        c.set("k", "v", ttl=0.2)
        assert c.get("k") == "v"
        time.sleep(0.25)
        assert c.get("k") is None

    def test_cached_decorator_memoizes(self):
        calls = []

        @cached(60)
        def fn(x):
            calls.append(x)
            return x * 2

        assert fn(3) == 6
        assert fn(3) == 6
        assert calls == [3]  # 第二次走缓存

    def test_none_results_not_cached(self):
        calls = []

        @cached(60)
        def fn():
            calls.append(1)
            return None

        fn()
        fn()
        assert len(calls) == 2  # None 不缓存，重试
