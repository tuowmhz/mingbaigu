"""价格提醒引擎：本地规则 + 后台线程轮询（每 5 分钟）。

规则一次性触发后自动失效（避免重复轰炸）；
触发记录由前端轮询展示并经浏览器 Notification 弹出。
"""
import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import CURRENCY_OF, market_of
from .data.market import get_history, latest_quote

ALERTS_FILE = Path(__file__).resolve().parent.parent / "data" / "alerts.json"
CHECK_INTERVAL = 300
_lock = threading.Lock()
_started = False

KINDS = {
    "price_above": "价格高于",
    "price_below": "价格低于",
    "change_below": "单日跌幅超过(%)",
}


def _load() -> dict:
    if ALERTS_FILE.exists():
        try:
            return json.loads(ALERTS_FILE.read_text())
        except Exception:
            pass
    return {"rules": [], "triggered": []}


def _save(data: dict):
    ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ALERTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1))


def list_alerts(uid: str = "local") -> dict:
    with _lock:
        data = _load()
    return {
        "rules": [r for r in data["rules"] if r.get("uid", "local") == uid],
        "triggered": [t for t in data["triggered"] if t.get("uid", "local") == uid],
    }


def add_rule(ticker: str, kind: str, value: float, uid: str = "local") -> dict:
    if kind not in KINDS:
        raise ValueError(f"不支持的提醒类型: {kind}")
    rule = {"id": uuid.uuid4().hex[:10], "ticker": ticker.upper(),
            "kind": kind, "value": float(value), "uid": uid,
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}
    with _lock:
        data = _load()
        data["rules"].append(rule)
        _save(data)
    return rule


def delete_rule(rule_id: str, uid: str = "local") -> bool:
    with _lock:
        data = _load()
        before = len(data["rules"])
        data["rules"] = [r for r in data["rules"]
                         if not (r["id"] == rule_id and r.get("uid", "local") == uid)]
        _save(data)
        return len(data["rules"]) < before


def mark_seen(uid: str = "local"):
    with _lock:
        data = _load()
        for t in data["triggered"]:
            if t.get("uid", "local") == uid:
                t["seen"] = True
        _save(data)


def _evaluate_rule(rule: dict, quote: dict) -> str | None:
    """命中返回提醒文案，未命中返回 None。"""
    sym = CURRENCY_OF[market_of(rule["ticker"])]
    price, chg = quote["price"], quote["change_pct"]
    if rule["kind"] == "price_above" and price >= rule["value"]:
        return f"{rule['ticker']} 现价 {sym}{price}，已升破你设定的 {sym}{rule['value']}"
    if rule["kind"] == "price_below" and price <= rule["value"]:
        return f"{rule['ticker']} 现价 {sym}{price}，已跌破你设定的 {sym}{rule['value']}"
    if rule["kind"] == "change_below" and chg <= -abs(rule["value"]):
        return f"{rule['ticker']} 单日下跌 {abs(chg)}%，超过你设定的 {abs(rule['value'])}% 阈值"
    return None


def check_once() -> int:
    """评估所有规则，返回本轮触发数。"""
    with _lock:
        data = _load()
        rules = list(data["rules"])
    fired = []
    for rule in rules:
        df = get_history(rule["ticker"], period="2y")
        if df is None:
            continue
        msg = _evaluate_rule(rule, latest_quote(df))
        if msg:
            fired.append((rule, msg))
    if fired:
        with _lock:
            data = _load()
            fired_ids = {r["id"] for r, _ in fired}
            data["rules"] = [r for r in data["rules"] if r["id"] not in fired_ids]
            for rule, msg in fired:
                data["triggered"].append({
                    "id": uuid.uuid4().hex[:10], "rule_id": rule["id"],
                    "uid": rule.get("uid", "local"),
                    "ticker": rule["ticker"], "message": msg,
                    "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                    "seen": False,
                })
            data["triggered"] = data["triggered"][-100:]
            _save(data)
    return len(fired)


def _loop():
    while True:
        try:
            check_once()
        except Exception:
            pass  # 单轮失败不杀线程
        time.sleep(CHECK_INTERVAL)


def start_checker():
    """FastAPI 启动时调用，幂等。"""
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, daemon=True, name="alerts-checker").start()
