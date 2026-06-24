"""对抗验证机制测试：裁判逻辑与置信度校准。"""
from app.analysis.adversarial import judge, run_adversarial

TECH_BULL = {"rsi": 55.0, "momentum_20d": 0.08, "close_above_sma50": True, "dist_52w_high": -0.02}
TECH_BEAR = {"rsi": 75.0, "momentum_20d": -0.10, "close_above_sma50": False, "dist_52w_high": -0.30}
RISK_CALM = {"annual_volatility": 0.22}
RISK_WILD = {"annual_volatility": 0.55}


def _pred(prob_up, edge):
    return {"prob_up": prob_up, "backtest": {"edge": edge}}


class TestJudge:
    def test_model_without_edge_lowers_confidence(self):
        bull = [{"side": "bull", "dimension": "技术面", "text": "x", "weight": 2.0}]
        bear = []
        with_edge = judge(bull, bear, _pred(0.7, 0.05))
        without_edge = judge(bull, bear, _pred(0.7, -0.05))
        assert with_edge["confidence"] > without_edge["confidence"]

    def test_conflicting_evidence_is_neutral(self):
        bull = [{"side": "bull", "dimension": "技术面", "text": "x", "weight": 1.0}]
        bear = [{"side": "bear", "dimension": "消息面", "text": "y", "weight": 1.0}]
        verdict = judge(bull, bear, None)
        assert verdict["verdict"] == "neutral"

    def test_direction_conflict_cuts_confidence(self):
        bull = [{"side": "bull", "dimension": "技术面", "text": "x", "weight": 3.0}]
        agree = judge(bull, [], _pred(0.7, 0.05))     # 模型也看多
        conflict = judge(bull, [], _pred(0.3, 0.05))  # 模型看空但论据看多
        assert conflict["confidence"] < agree["confidence"]


class TestRunAdversarial:
    def test_bull_setup_produces_bullish(self):
        out = run_adversarial(TECH_BULL, None, None, _pred(0.65, 0.04), RISK_CALM)
        assert out["judge"]["verdict"] == "bullish"
        assert len(out["bull_case"]) > len(out["bear_case"])

    def test_bear_setup_produces_bearish(self):
        out = run_adversarial(TECH_BEAR, None, None, _pred(0.35, 0.04), RISK_WILD)
        assert out["judge"]["verdict"] == "bearish"

    def test_news_signal_becomes_evidence(self):
        sig = {"score": 1.5, "direction_cn": "强利好", "positive": 6, "negative": 1,
               "drivers_positive": [{"title": "Big earnings beat", "events": ["业绩超预期"], "impact": 2.5}],
               "drivers_negative": []}
        out = run_adversarial(TECH_BULL, sig, None, None, RISK_CALM)
        assert any(a["dimension"] == "消息面" for a in out["bull_case"])
