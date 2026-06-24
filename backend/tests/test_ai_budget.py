"""AI 预算电表：计费准确、超额熔断、按日滚动。"""
import json

import pytest

from app import ai_budget


@pytest.fixture
def fresh_state(tmp_path, monkeypatch):
    """隔离的电表状态文件 + $1 预算。"""
    monkeypatch.setattr(ai_budget, "STATE_PATH", tmp_path / "ai_spend.json")
    monkeypatch.setenv("AI_DAILY_BUDGET_USD", "1.0")
    return tmp_path / "ai_spend.json"


def test_cost_table():
    # Haiku: $1/M 输入 + $5/M 输出
    assert ai_budget.cost_of("claude-haiku-4-5-20251001", 1_000_000, 0) == 1.0
    assert ai_budget.cost_of("claude-haiku-4-5-20251001", 0, 1_000_000) == 5.0
    # Sonnet: $3/M + $15/M
    assert ai_budget.cost_of("claude-sonnet-4-6", 100_000, 10_000) == pytest.approx(0.45)
    # 不认识的模型按最贵（Opus 档）计，宁可少花不可超支
    assert ai_budget.cost_of("mystery-model", 1_000_000, 0) == 15.0


def test_record_and_status(fresh_state):
    ai_budget._record("claude-haiku-4-5-20251001", {"input_tokens": 200_000, "output_tokens": 40_000})
    st = ai_budget.status()
    assert st["spent_usd"] == pytest.approx(0.4)
    assert st["remaining_usd"] == pytest.approx(0.6)
    assert st["calls_today"] == 1
    # 落盘了，新进程能接着算
    assert json.loads(fresh_state.read_text())["calls"] == 1


def test_budget_fuse_blocks_without_http(fresh_state, monkeypatch):
    """预算用尽后 call_claude 直接拒绝，根本不发网络请求。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    def boom(*a, **k):
        raise AssertionError("熔断后不应发起 HTTP 请求")
    monkeypatch.setattr(ai_budget.requests, "post", boom)

    ai_budget._record("claude-sonnet-4-6", {"input_tokens": 0, "output_tokens": 100_000})  # $1.5 > 预算
    out = ai_budget.call_claude("claude-sonnet-4-6", "sys", "hi")
    assert out["error"] == "budget_exhausted"


def test_no_key_is_silent(fresh_state, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = ai_budget.call_claude("claude-haiku-4-5-20251001", "sys", "hi")
    assert out["error"] == "no_api_key"


def test_daily_rollover(fresh_state, monkeypatch):
    ai_budget._record("claude-sonnet-4-6", {"input_tokens": 0, "output_tokens": 100_000})
    assert not ai_budget._allow()
    # 第二天：状态文件日期对不上 → 自动归零
    monkeypatch.setattr(ai_budget, "_today", lambda: "2099-01-01")
    assert ai_budget._allow()
    assert ai_budget.status()["spent_usd"] == 0.0
