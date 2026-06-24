"""每日财经爆款精选引擎（Newsletter 的内容心脏）。

源（国外为主，国内为辅）：
  Motley Fool / Seeking Alpha / CNBC / MarketWatch / CNN / Google News
  / Reddit 散户热帖 / 东方财富快讯(国内)

排序不是按时间，是按"爆款分"：
  1. 跨源共振（核心信号）：同一个故事被 ≥2 家独立媒体报道 = 真爆款，
     比任何单源的"热度"都可靠——这是我们版本的推荐算法第一性原理；
  2. 事件冲击分：业绩/评级/并购等实质事件（复用消息面引擎）；
  3. 新鲜度：12 小时半衰期。

每条可挂中文导读（配 ANTHROPIC_API_KEY 时由 Claude 生成，否则展示原题+事件标签）。
"""
import re

from ..analysis.news_signal import _analyze_item
from ..cache import cached
from .macro_news import MARKET_FEEDS, _fetch_eastmoney, _fetch_feed

DIGEST_FEEDS = [
    ("Motley Fool", "https://www.fool.com/feeds/index.aspx"),
    ("Seeking Alpha", "https://seekingalpha.com/feed.xml"),
    ("Seeking Alpha", "https://seekingalpha.com/market_currents.xml"),
] + MARKET_FEEDS

_STOP = {"the", "and", "for", "with", "this", "that", "from", "what", "will",
         "your", "into", "after", "more", "than", "have", "has", "are", "its",
         "stock", "stocks", "shares", "market", "markets", "could", "should",
         "here", "why", "how", "says", "见闻", "新闻", "报道"}


def _tokens(title: str) -> set:
    words = re.findall(r"[a-zA-Z]{4,}|[一-鿿]{2,4}", title.lower())
    return {w for w in words if w not in _STOP}


def _same_story(a: set, b: set) -> bool:
    if not a or not b:
        return False
    inter = len(a & b)
    return inter / min(len(a), len(b)) >= 0.5 and inter >= 2


def _recency(ts, now_ts: float) -> float:
    if not ts:
        return 0.3
    age_h = max(0.0, (now_ts - ts) / 3600)
    return 0.5 ** (age_h / 12)  # 12 小时半衰期


@cached(1800)
def build_digest(limit: int = 10) -> dict | None:
    import time
    now_ts = time.time()

    raw, seen = [], set()
    for source, url in DIGEST_FEEDS:
        for it in _fetch_feed(source, url, limit=20):
            key = it["title"].lower()[:70]
            if key not in seen:
                seen.add(key)
                raw.append(it)
    for it in _fetch_eastmoney(limit=15):  # 国内为辅
        raw.append(it)
    if not raw:
        return None

    items = [_analyze_item(it, []) for it in raw]
    for it in items:
        dt = it.pop("_dt", None)
        it["published_ts"] = dt.timestamp() if dt else None
        it["_tok"] = _tokens(it["title"])

    # 跨源聚类：贪心合并同一个故事
    clusters: list[dict] = []
    for it in items:
        placed = False
        for c in clusters:
            if _same_story(it["_tok"], c["_tok"]):
                c["sources"].add(it["source"])
                c["links"].append({"source": it["source"], "title": it["title"],
                                   "link": it["link"]})
                c["_tok"] |= it["_tok"]
                if abs(it["impact"]) > abs(c["impact"]):
                    c.update(title=it["title"], impact=it["impact"],
                             impact_label=it["impact_label"], events=it["events"])
                if (it["published_ts"] or 0) > (c["published_ts"] or 0):
                    c["published_ts"] = it["published_ts"]
                placed = True
                break
        if not placed:
            clusters.append({
                "title": it["title"], "link": it["link"],
                "sources": {it["source"]},
                "links": [{"source": it["source"], "title": it["title"], "link": it["link"]}],
                "impact": it["impact"], "impact_label": it["impact_label"],
                "events": it["events"], "published_ts": it["published_ts"],
                "_tok": set(it["_tok"]),
            })

    for c in clusters:
        n_src = len(c["sources"])
        c["score"] = round(
            (n_src - 1) * 2.5                      # 跨源共振：爆款核心信号
            + abs(c["impact"]) * 1.5               # 实质事件
            + _recency(c["published_ts"], now_ts)  # 新鲜度
            + (0.5 if c["events"] else 0), 2)
        c["cross_source"] = n_src >= 2
        c["sources"] = sorted(c["sources"])
        c.pop("_tok")

    clusters.sort(key=lambda c: -c["score"])
    top = clusters[:limit]

    # 中文导读：Claude 插槽（无 key 时为 None，前端展示原题+标签）
    intro_engine = None
    try:
        from ..analysis.claude_analyst import enabled
        if enabled():
            intro_engine = "claude"
            _add_intros(top)
    except Exception:
        pass

    return {
        "items": top,
        "n_raw": len(items), "n_clusters": len(clusters),
        "n_cross_source": sum(1 for c in clusters if c["cross_source"]),
        "intro_engine": intro_engine,
        "methodology": "爆款分 = 跨源共振×2.5 + 事件冲击×1.5 + 12小时新鲜度衰减。被多家独立媒体同时报道的故事，比任何单源热度都更接近'真爆款'。",
    }


# 导读增量缓存：同一条故事只生成一次，半小时一次的重建不重复付费
_INTRO_CACHE: dict[str, str] = {}


def _add_intros(items: list[dict]):
    """Claude 批量生成中文导读：只为没见过的新故事调用，一次批量调用省成本。

    导读是简单任务，用 Haiku（约为 Sonnet 价格的 1/3）；调用走 ai_budget 电表。
    """
    import json
    import os

    from ..ai_budget import call_claude

    for c in items:
        if c["title"] in _INTRO_CACHE:
            c["intro_cn"] = _INTRO_CACHE[c["title"]]
    fresh = [c for c in items if "intro_cn" not in c]
    if not fresh:
        return
    titles = [{"i": i, "title": c["title"], "events": c["events"]}
              for i, c in enumerate(fresh)]
    out = call_claude(
        os.environ.get("CLAUDE_DIGEST_MODEL", "claude-haiku-4-5-20251001"),
        "你是财经编辑。为每条英文新闻写一句 25 字以内的中文导读：信息密度高、说人话、不耸动。"
        "输出 JSON 数组：[{\"i\":0,\"intro\":\"...\"},...]，只输出 JSON。",
        json.dumps(titles, ensure_ascii=False),
        max_tokens=1200, timeout=45)
    if not out.get("text"):
        return
    try:
        for row in json.loads(re.search(r"\[.*\]", out["text"], re.S).group()):
            c = fresh[row["i"]]
            c["intro_cn"] = row["intro"]
            _INTRO_CACHE[c["title"]] = row["intro"]
        # 缓存只增不减，防慢性泄漏：超 500 条清掉最早的一半
        if len(_INTRO_CACHE) > 500:
            for k in list(_INTRO_CACHE)[:250]:
                _INTRO_CACHE.pop(k, None)
    except Exception:
        pass
