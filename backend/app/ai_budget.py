"""AI 调用的电表与保险丝：按官方 usage 实计费用，超过每日预算直接拒绝调用。

设计原则（诚实优先的另一面是花钱透明）：
- 计费依据 API 响应里的真实 token 用量，不靠估算；
- 状态落盘（backend/data/ai_spend.json），进程重启不清零；
- 预算用 AI_DAILY_BUDGET_USD 控制，默认 $1/天，按 UTC 自然日滚动；
- 所有 Claude 调用必须走 call_claude()，没有旁路。
"""
import json
import os
import threading
import time
from pathlib import Path

import requests

API_URL = "https://api.anthropic.com/v1/messages"
STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "ai_spend.json"

# $/百万 token（输入, 输出），子串匹配模型名
PRICES = [
    ("haiku", (1.0, 5.0)),
    ("sonnet", (3.0, 15.0)),
    ("opus", (15.0, 75.0)),
]
_FALLBACK = (15.0, 75.0)  # 不认识的模型按最贵算，宁可少花不可超支

_lock = threading.Lock()


def daily_budget() -> float:
    try:
        return float(os.environ.get("AI_DAILY_BUDGET_USD", "1.0"))
    except ValueError:
        return 1.0


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _load() -> dict:
    try:
        d = json.loads(STATE_PATH.read_text())
        if d.get("date") == _today():
            return d
    except Exception:
        pass
    return {"date": _today(), "spent_usd": 0.0, "calls": 0}


def _save(state: dict):
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state))
    except Exception:
        pass


def _price(model: str) -> tuple[float, float]:
    m = (model or "").lower()
    for name, p in PRICES:
        if name in m:
            return p
    return _FALLBACK


def cost_of(model: str, input_tokens: int, output_tokens: int) -> float:
    pi, po = _price(model)
    return (input_tokens * pi + output_tokens * po) / 1e6


def status() -> dict:
    with _lock:
        s = _load()
    budget = daily_budget()
    return {
        "enabled": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "date_utc": s["date"],
        "budget_usd": budget,
        "spent_usd": round(s["spent_usd"], 4),
        "remaining_usd": round(max(0.0, budget - s["spent_usd"]), 4),
        "calls_today": s["calls"],
    }


def _allow() -> bool:
    with _lock:
        return _load()["spent_usd"] < daily_budget()


def _record(model: str, usage: dict):
    cost = cost_of(model, usage.get("input_tokens", 0), usage.get("output_tokens", 0))
    with _lock:
        s = _load()
        s["spent_usd"] += cost
        s["calls"] += 1
        _save(s)


def call_claude(model: str, system: str, user_content: str,
                max_tokens: int = 1200, timeout: int = 60) -> dict:
    """统一的 Claude 调用入口。返回 {"text": ...} 或 {"error": ...}。

    预算用尽时不发请求，返回 budget_exhausted——调用方降级到规则版输出。
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return {"error": "no_api_key"}
    if not _allow():
        return {"error": "budget_exhausted",
                "detail": f"今日 AI 预算（${daily_budget():.2f}）已用完，UTC 零点自动恢复。"}
    try:
        r = requests.post(API_URL, headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }, json={
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user_content}],
        }, timeout=timeout)
        if r.status_code != 200:
            return {"error": f"Claude API {r.status_code}: {r.text[:120]}"}
        body = r.json()
        _record(model, body.get("usage", {}))
        return {"text": "".join(b.get("text", "") for b in body.get("content", [])),
                "model": model}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
