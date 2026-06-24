"""Finnhub 新闻适配器（可选付费/免费注册渠道的"插槽"）。

Finnhub 免费档：60 次/分钟，公司新闻 + 全市场新闻，比 RSS 快且结构化。
启用方式：到 finnhub.io 免费注册拿 API key，然后
    export FINNHUB_KEY=你的key
重启后端即自动生效——个股新闻会优先走 Finnhub，RSS 退为兜底。
不配置 key 时本模块完全静默，零影响。
"""
import os
from datetime import datetime, timedelta, timezone

import requests

from ..cache import cached

API = "https://finnhub.io/api/v1"


def enabled() -> bool:
    return bool(os.environ.get("FINNHUB_KEY"))


@cached(300)
def company_news(ticker: str, days: int = 7, limit: int = 25) -> list[dict] | None:
    """个股新闻（仅美股）。失败/未配置返回 None，调用方退回 RSS。"""
    key = os.environ.get("FINNHUB_KEY")
    if not key or ticker.endswith((".SS", ".SZ")):
        return None
    now = datetime.now(timezone.utc)
    try:
        r = requests.get(f"{API}/company-news", params={
            "symbol": ticker,
            "from": (now - timedelta(days=days)).strftime("%Y-%m-%d"),
            "to": now.strftime("%Y-%m-%d"),
            "token": key,
        }, timeout=12)
        if r.status_code != 200:
            return None
        rows = r.json()
    except Exception:
        return None
    if not isinstance(rows, list) or not rows:
        return None
    out = []
    for row in rows[:limit]:
        title = (row.get("headline") or "").strip()
        if not title:
            continue
        ts = row.get("datetime")
        published = (datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else "")
        out.append({
            "title": title,
            "summary": row.get("summary") or "",
            "link": row.get("url") or "",
            "published": published,
            "source": f"Finnhub·{row.get('source', '')}".rstrip("·"),
        })
    return out or None
