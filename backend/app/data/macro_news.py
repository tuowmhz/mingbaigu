"""重大消息面聚合：CNBC + MarketWatch + CNN + Google News 多源实时抓取。

- CNBC / MarketWatch：官方 RSS（免费、稳定）
- CNN：官方 RSS 已停更，走 Google News 的 site 过滤拿实时 CNN 内容
- Google News：商业头条 topic feed + AI 产业链定向查询
每条新闻复用 news_signal 的事件抽取与情绪引擎打分。
"""
import feedparser
import requests

from ..analysis.news_signal import _analyze_item, _direction
from ..cache import cached
from .news import _dedupe_key, _make_item

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

MARKET_FEEDS = [
    ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines"),
    ("CNN", "https://news.google.com/rss/search?q=site:cnn.com+(business+OR+stock+OR+economy+OR+fed)+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"),
    # 散户情绪：Reddit 热帖标题（meme 浓度高，但这就是真实的散户在想什么）
    ("Reddit", "https://www.reddit.com/r/wallstreetbets/hot/.rss?limit=15"),
    ("Reddit", "https://www.reddit.com/r/stocks/hot/.rss?limit=15"),
]

# 东方财富 7×24 快讯：A股的实时新闻线（fastColumn=102 为证券快讯）
EASTMONEY_FAST = ("https://np-listapi.eastmoney.com/comm/web/getFastNewsList"
                  "?client=web&biz=web_724&fastColumn=102&sortEnd=&pageSize=30&req_trace=1")

AI_FEEDS = [
    ("CNBC Tech", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910"),
    ("Google News", "https://news.google.com/rss/search?q=(Nvidia+OR+TSMC+OR+%22AI+chip%22+OR+%22data+center%22+OR+hyperscaler+OR+HBM+OR+semiconductor)+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News", "https://news.google.com/rss/search?q=(%22capital+expenditure%22+OR+capex+OR+%22AI+infrastructure%22)+(Microsoft+OR+Google+OR+Amazon+OR+Meta)+when:3d&hl=en-US&gl=US&ceid=US:en"),
    ("CNN", "https://news.google.com/rss/search?q=site:cnn.com+(AI+OR+Nvidia+OR+chips)+when:2d&hl=en-US&gl=US&ceid=US:en"),
]


def _fetch_feed(source: str, url: str, limit: int = 25) -> list[dict]:
    try:
        r = requests.get(url, headers=_HEADERS, timeout=12)
        if r.status_code != 200:
            return []
        feed = feedparser.parse(r.content)
    except Exception:
        return []
    items = []
    for e in feed.entries[:limit]:
        title = getattr(e, "title", "") or ""
        if not title:
            continue
        # Google 代理的标题带 " - 源站" 后缀，保留（可辨识真实来源）
        item = _make_item(title, getattr(e, "summary", "") or "",
                          getattr(e, "link", ""), getattr(e, "published", ""), source)
        items.append(item)
    return items


def _aggregate(feeds: list[tuple[str, str]], limit: int) -> dict | None:
    items, seen = [], set()
    for source, url in feeds:
        for it in _fetch_feed(source, url):
            key = _dedupe_key(it["title"])
            if key and key not in seen:
                seen.add(key)
                items.append(it)
    if not items:
        return None
    # 事件抽取 + 影响分（无公司视角，aliases 为空）
    items = [_analyze_item(it, []) for it in items]
    # 按时间排序（没时间戳的沉底），并保留相对时间用的时间戳
    for it in items:
        dt = it.pop("_dt", None)
        it["published_ts"] = dt.timestamp() if dt else None
    items.sort(key=lambda i: -(i["published_ts"] or 0))
    items = items[:limit]

    score = sum(i["impact"] for i in items) / len(items)
    key, cn, hint = _direction(round(score, 2))
    return {
        "items": items,
        "n_items": len(items),
        "sources": sorted({i["source"] for i in items}),
        "score": round(score, 2),
        "direction_cn": cn,
        "trend_hint": hint,
        "positive": sum(1 for i in items if i["impact_label"] == "利好"),
        "negative": sum(1 for i in items if i["impact_label"] == "利空"),
        "neutral": sum(1 for i in items if i["impact_label"] == "中性"),
    }


@cached(300)
def get_market_news(limit: int = 40) -> dict | None:
    """宏观市场要闻：CNBC/MarketWatch/CNN/Google 聚合。"""
    return _aggregate(MARKET_FEEDS, limit)


@cached(300)
def get_ai_news(limit: int = 40) -> dict | None:
    """AI 产业链专题要闻：芯片/数据中心/云厂资本开支。"""
    return _aggregate(AI_FEEDS, limit)


def _fetch_eastmoney(limit: int = 30) -> list[dict]:
    """东方财富 7×24 快讯：A股实时新闻线（北京时间，转 ISO+08:00）。"""
    try:
        r = requests.get(EASTMONEY_FAST, headers=_HEADERS, timeout=12)
        rows = r.json()["data"]["fastNewsList"]
    except Exception:
        return []
    items = []
    for row in rows[:limit]:
        title = (row.get("title") or "").strip()
        if not title:
            continue
        published = (row.get("showTime") or "").replace(" ", "T") + "+08:00" if row.get("showTime") else ""
        code = row.get("code") or ""
        items.append(_make_item(title, row.get("summary") or "",
                                f"https://finance.eastmoney.com/a/{code}.html" if code else "",
                                published, "东方财富快讯"))
    return items


@cached(180)  # 快讯 3 分钟刷新
def get_cn_news(limit: int = 40) -> dict | None:
    """A股实时要闻：东方财富 7×24 快讯 + Google 中文财经。"""
    items, seen = [], set()
    for it in _fetch_eastmoney():
        key = _dedupe_key(it["title"])
        if key and key not in seen:
            seen.add(key)
            items.append(it)
    for it in _fetch_feed("Google 财经",
                          "https://news.google.com/rss/search?q=A股+OR+沪指+OR+央行+when:1d&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"):
        key = _dedupe_key(it["title"])
        if key and key not in seen:
            seen.add(key)
            items.append(it)
    if not items:
        return None
    items = [_analyze_item(it, []) for it in items]
    for it in items:
        dt = it.pop("_dt", None)
        it["published_ts"] = dt.timestamp() if dt else None
    items.sort(key=lambda i: -(i["published_ts"] or 0))
    items = items[:limit]
    score = sum(i["impact"] for i in items) / len(items)
    key, cn, hint = _direction(round(score, 2))
    return {
        "items": items, "n_items": len(items),
        "sources": sorted({i["source"] for i in items}),
        "score": round(score, 2), "direction_cn": cn, "trend_hint": hint,
        "positive": sum(1 for i in items if i["impact_label"] == "利好"),
        "negative": sum(1 for i in items if i["impact_label"] == "利空"),
        "neutral": sum(1 for i in items if i["impact_label"] == "中性"),
    }
