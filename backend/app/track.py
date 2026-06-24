"""轻量自建埋点：隐私友好、零第三方、数据归自己。

设计原则（符合产品宪法）：
- 不存任何个人信息：访客标识 = sha256(IP+UA+当日盐) 截断 16 位，每天自动轮换，
  无法跨天追踪任何人；
- 记录：哪天、看了哪个板块、多少独立访客、来自哪个渠道(UTM)、关键转化事件；
- 数据落在自己的卷上（/app/data/traffic.json），不发给任何第三方。

UTM 归因：渠道来源(source)是"首触"——访客在小红书等渠道第一次进来时记下，
存浏览器本地，回访仍带同一来源。这样能回答"哪条渠道带来的人会留下来"，
但因为访客哈希每天轮换，跨天的"独立访客"实为"访客人日"，报告里如实标注。
"""
import hashlib
import json
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

TRAFFIC_FILE = Path(__file__).resolve().parent.parent / "data" / "traffic.json"
_lock = threading.Lock()
MAX_DAILY_VISITORS = 100_000  # 集合上限保护
MAX_SOURCE_VISITORS = 50_000

VALID_VIEWS = {"stocks", "portfolio", "chain", "quant", "earnings", "academy",
               "daily", "record", "detail", "landing"}
VALID_EVENTS = {"quiz_done", "signup", "share", "deep_analysis"}


def _today() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")


def _load() -> dict:
    try:
        return json.loads(TRAFFIC_FILE.read_text()) if TRAFFIC_FILE.exists() else {}
    except Exception:
        return {}


def visitor_hash(ip: str, ua: str) -> str:
    salt = _today()  # 当日盐：跨天不可关联
    return hashlib.sha256(f"{ip}|{ua}|{salt}".encode()).hexdigest()[:16]


def _clean(s: str | None, maxlen: int = 40) -> str | None:
    if not s:
        return None
    s = str(s).strip().lower()[:maxlen]
    # 只留安全字符，挡住脏数据/注入
    s = "".join(c for c in s if c.isalnum() or c in "-_.+ ")
    return s or None


def record(view: str, ip: str, ua: str,
           source: str | None = None, campaign: str | None = None,
           event: str | None = None):
    view = view if view in VALID_VIEWS else "other"
    source = _clean(source) or "direct"
    campaign = _clean(campaign)
    event = event if event in VALID_EVENTS else None
    vh = visitor_hash(ip, ua)
    with _lock:
        data = _load()
        day = data.setdefault(_today(), {"views": {}, "visitors": []})
        day["views"][view] = day["views"].get(view, 0) + 1
        if vh not in day["visitors"] and len(day["visitors"]) < MAX_DAILY_VISITORS:
            day["visitors"].append(vh)

        # 按渠道归因
        sources = day.setdefault("sources", {})
        s = sources.setdefault(source, {"visitors": [], "events": {}, "campaigns": {}})
        if vh not in s["visitors"] and len(s["visitors"]) < MAX_SOURCE_VISITORS:
            s["visitors"].append(vh)
        if campaign:
            s["campaigns"][campaign] = s["campaigns"].get(campaign, 0) + 1
        if event:
            s["events"][event] = s["events"].get(event, 0) + 1

        # 只保留 180 天
        for k in sorted(data.keys())[:-180]:
            del data[k]
        TRAFFIC_FILE.parent.mkdir(parents=True, exist_ok=True)
        TRAFFIC_FILE.write_text(json.dumps(data))


def report(days: int = 30) -> dict:
    data = _load()
    rows = []
    for date in sorted(data.keys())[-days:]:
        d = data[date]
        rows.append({
            "date": date,
            "unique_visitors": len(d.get("visitors", [])),
            "total_views": sum(d.get("views", {}).values()),
            "by_view": d.get("views", {}),
        })
    total_v = sum(r["unique_visitors"] for r in rows)
    hot = {}
    for r in rows:
        for k, v in r["by_view"].items():
            hot[k] = hot.get(k, 0) + v

    # 按渠道聚合漏斗：访客人日 → 测试完成 → 注册
    src_agg: dict[str, dict] = {}
    for date in sorted(data.keys())[-days:]:
        for source, s in data[date].get("sources", {}).items():
            a = src_agg.setdefault(source, {"visitor_days": 0, "quiz_done": 0,
                                            "signup": 0, "share": 0})
            a["visitor_days"] += len(s.get("visitors", []))
            for evt, n in s.get("events", {}).items():
                if evt in a:
                    a[evt] += n
    by_source = []
    for source, a in src_agg.items():
        vd = a["visitor_days"]
        by_source.append({
            "source": source,
            **a,
            "quiz_rate": round(a["quiz_done"] / vd, 3) if vd else None,
            "signup_rate": round(a["signup"] / vd, 3) if vd else None,
        })
    by_source.sort(key=lambda x: -x["visitor_days"])

    return {
        "days": rows,
        "summary": {
            "period_days": len(rows),
            "total_unique_visitors": total_v,
            "total_views": sum(r["total_views"] for r in rows),
            "hottest_views": sorted(hot.items(), key=lambda kv: -kv[1]),
        },
        "by_source": by_source,
        "privacy_note": "访客标识为当日盐哈希，无法跨天追踪个人；'访客人日'为每日独立访客之和"
                        "（同一人多日来访会被多次计入），数据不出本服务器。",
    }
