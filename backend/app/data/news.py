"""消息面原始数据：双源合并抓取（Yahoo Finance + Google News），VADER 基础情绪分。

事件抽取与综合研判在 analysis/news_signal.py。
"""
import re

import feedparser
import requests
import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from ..cache import cached
from ..config import CACHE_TTL_NEWS

_analyzer = SentimentIntensityAnalyzer()

GOOGLE_RSS = ("https://news.google.com/rss/search?"
              "q={query}+stock+when:7d&hl=en-US&gl=US&ceid=US:en")
GOOGLE_RSS_ZH = ("https://news.google.com/rss/search?"
                 "q={query}+股票+when:7d&hl=zh-CN&gl=CN&ceid=CN:zh-Hans")

# Google News 用公司名搜索，避免单字母代码（如 C）搜出噪音
GOOGLE_QUERY = {
    "JPM": "JPMorgan", "BAC": "Bank of America", "WFC": "Wells Fargo",
    "C": "Citigroup", "GS": "Goldman Sachs", "MS": "Morgan Stanley",
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia",
    "GOOGL": "Google", "AMZN": "Amazon", "META": "Meta", "TSLA": "Tesla",
    # A股用中文名搜中文新闻
    "600519.SS": "贵州茅台", "300750.SZ": "宁德时代", "601318.SS": "中国平安",
    "600036.SS": "招商银行", "000858.SZ": "五粮液", "002594.SZ": "比亚迪",
    "688981.SS": "中芯国际", "000333.SZ": "美的集团", "601899.SS": "紫金矿业",
    "600900.SS": "长江电力",
}

YF_LIMIT = 15      # Yahoo 源条数上限
GOOGLE_LIMIT = 25  # Google 源条数上限
TOTAL_LIMIT = 42   # 合并去重后总条数上限（含中文媒体）


def _label(score: float) -> str:
    if score >= 0.25:
        return "利好"
    if score <= -0.25:
        return "利空"
    return "中性"


def _make_item(title: str, summary: str, link: str, published: str, source: str) -> dict:
    text = f"{title}. {summary}"[:500]
    score = _analyzer.polarity_scores(text)["compound"]
    return {
        "title": title,
        "link": link,
        "published": published,
        "source": source,
        "sentiment": round(score, 3),
        "sentiment_label": _label(score),
    }


def _from_yfinance(ticker: str) -> list[dict]:
    try:
        raw = yf.Ticker(ticker).news or []
    except Exception:
        return []
    items = []
    for n in raw[:YF_LIMIT]:
        c = n.get("content") or n  # 新旧两种返回格式
        title = c.get("title") or ""
        if not title:
            continue
        link = ""
        for key in ("canonicalUrl", "clickThroughUrl"):
            u = c.get(key)
            if isinstance(u, dict) and u.get("url"):
                link = u["url"]
                break
        link = link or c.get("link", "")
        summary = c.get("summary") or c.get("description") or ""
        published = c.get("pubDate") or c.get("displayTime") or ""
        items.append(_make_item(title, summary, link, published, "Yahoo Finance"))
    return items


# 美股公司的中文名（中文媒体报道检索用；不在表里的用 "代码+股票" 兜底）
ZH_NAME = {
    "JPM": "摩根大通", "BAC": "美国银行", "WFC": "富国银行", "C": "花旗",
    "GS": "高盛", "MS": "摩根士丹利", "AAPL": "苹果公司", "MSFT": "微软",
    "NVDA": "英伟达", "GOOGL": "谷歌", "AMZN": "亚马逊", "META": "Meta",
    "TSLA": "特斯拉", "AMD": "AMD", "TSM": "台积电", "AVGO": "博通",
    "MU": "美光", "INTC": "英特尔", "COIN": "Coinbase", "BABA": "阿里巴巴",
    "NFLX": "奈飞", "DIS": "迪士尼", "NKE": "耐克", "SMCI": "超微电脑",
}


def _fetch_google_feed(url: str, source: str, limit: int) -> list[dict]:
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return []
        feed = feedparser.parse(r.content)
    except Exception:
        return []
    return [
        _make_item(
            getattr(e, "title", "") or "",
            getattr(e, "summary", "") or "",
            getattr(e, "link", ""),
            getattr(e, "published", ""),
            source,
        )
        for e in feed.entries[:limit]
        if getattr(e, "title", None)
    ]


def _from_google(ticker: str) -> list[dict]:
    query = GOOGLE_QUERY.get(ticker, ticker)
    is_cn = ticker.upper().endswith((".SS", ".SZ"))
    url_tpl = GOOGLE_RSS_ZH if is_cn else GOOGLE_RSS
    return _fetch_google_feed(url_tpl.format(query=query.replace(" ", "+")),
                              "Google News", GOOGLE_LIMIT)


def _from_google_zh_us(ticker: str) -> list[dict]:
    """美股公司的中文媒体报道（新浪财经/华尔街见闻等，经 Google 中文索引）。

    中国散户看英文标题没有体感——中文报道才能 target 到位。
    """
    query = ZH_NAME.get(ticker, f"{ticker}+股票")
    return _fetch_google_feed(GOOGLE_RSS_ZH.format(query=query.replace(" ", "+")),
                              "中文媒体", 15)


def _dedupe_key(title: str) -> str:
    return re.sub(r"\W+", "", title.lower())[:60]


def _from_finnhub(ticker: str) -> list[dict]:
    """可选渠道：配置 FINNHUB_KEY 后启用（结构化、更快），未配置返回空。"""
    from .finnhub_news import company_news
    rows = company_news(ticker) or []
    return [_make_item(r["title"], r["summary"], r["link"], r["published"], r["source"])
            for r in rows]


@cached(CACHE_TTL_NEWS)
def get_news(ticker: str) -> dict | None:
    """多源合并去重的新闻列表（含逐条情绪分）。

    源优先级：Finnhub（如已配置 key）→ Yahoo → Google News；
    美股额外并入中文媒体报道（A股本来就是中文源）。
    """
    is_cn = ticker.upper().endswith((".SS", ".SZ"))
    zh_extra = [] if is_cn else _from_google_zh_us(ticker)
    items, seen = [], set()
    for it in _from_finnhub(ticker) + _from_yfinance(ticker) + _from_google(ticker):
        key = _dedupe_key(it["title"])
        if key and key not in seen:
            seen.add(key)
            items.append(it)
    # 中文媒体有保留配额，避免被英文源挤出上限
    items = items[:TOTAL_LIMIT - (12 if zh_extra else 0)]
    for it in zh_extra[:12]:
        key = _dedupe_key(it["title"])
        if key and key not in seen:
            seen.add(key)
            items.append(it)
    if not items:
        return None  # 不缓存失败，下次重试

    avg = sum(i["sentiment"] for i in items) / len(items)
    return {
        "items": items,
        "sources": sorted({i["source"] for i in items}),
        "avg_sentiment": round(avg, 3),
        "summary_label": _label(avg),
        "positive": sum(1 for i in items if i["sentiment_label"] == "利好"),
        "negative": sum(1 for i in items if i["sentiment_label"] == "利空"),
        "neutral": sum(1 for i in items if i["sentiment_label"] == "中性"),
    }
