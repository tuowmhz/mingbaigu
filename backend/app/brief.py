"""每日人话简报生成器（Newsletter 的核心引擎）。

从平台已有的分析引擎组装一份"三分钟看懂今天"的简报：
市场体温 → 今天最重要的事 → 谁在异动 → 散户在看什么 → 一条值得想的线索。
全部来自缓存的引擎产物，生成成本≈0；输出同时给前端面板和 Markdown（发邮件用）。
"""
from datetime import datetime, timezone, timedelta

from .analysis.fear_greed import get_fear_greed
from .config import NAME_MAP, WATCHLIST
from .data.macro_news import get_ai_news, get_market_news
from .data.market import get_history, latest_quote
from .data.retail_heat import get_retail_heat


def _movers() -> list[dict]:
    out = []
    for t, name, _ in WATCHLIST:
        df = get_history(t, period="2y")
        if df is None:
            continue
        q = latest_quote(df)
        out.append({"ticker": t, "name": name, "pct": q["change_pct"],
                    "currency": "¥" if t.endswith((".SS", ".SZ")) else "$",
                    "price": q["price"]})
    out.sort(key=lambda x: -abs(x["pct"]))
    return out[:5]


def build_brief() -> dict:
    now_cn = datetime.now(timezone(timedelta(hours=8)))
    sections = []

    # 1. 市场体温
    fg = get_fear_greed()
    if fg:
        sections.append({
            "title": "🌡️ 市场体温",
            "lines": [f"恐惧贪婪指数 {fg['index']}（{fg['label_cn']}）。{fg['hint']}"],
        })

    # 2. 今天最重要的事（宏观要闻里影响分绝对值最大的 3 条）
    market = get_market_news()
    if market:
        top = sorted(market["items"], key=lambda i: -abs(i.get("impact", 0)))[:3]
        sections.append({
            "title": "📰 今天最重要的事",
            "lines": [f"[{i['impact_label']}] {i['title']}"
                      + (f"（{'/'.join(i['events'])}）" if i.get("events") else "")
                      for i in top],
        })

    # 2.5 全球爆款共振（被多家独立媒体同时报道的故事）
    try:
        from .data.digest import build_digest
        digest = build_digest()
        if digest:
            cross = [c for c in digest["items"] if c["cross_source"]][:4]
            if cross:
                sections.append({
                    "title": "🌐 全球爆款共振",
                    "lines": [
                        (c.get("intro_cn") or c["title"])
                        + f"（{len(c['sources'])} 家媒体同时报道"
                        + (f"：{'、'.join(c['events'])}" if c["events"] else "") + "）"
                        for c in cross],
                })
    except Exception:
        pass

    # 3. 谁在异动（观察列表涨跌幅榜）
    movers = _movers()
    if movers:
        sections.append({
            "title": "📊 谁在异动",
            "lines": [f"{m['name']}（{m['ticker']}）{m['pct']:+.1f}%，报 {m['currency']}{m['price']}"
                      for m in movers],
        })

    # 4. 散户在看什么
    heat = get_retail_heat(limit=6)
    if heat and heat["items"]:
        names = "、".join(f"{i['name']}" + (f"(↑{i['rank_change']})" if (i.get("rank_change") or 0) > 20 else "")
                          for i in heat["items"][:6])
        sections.append({
            "title": "🔥 散户在围观",
            "lines": [f"A股人气榜前排：{names}。", heat["note"]],
        })

    # 5. 一条值得想的线索（AI 专题里最重磅的一条）
    ai = get_ai_news()
    if ai:
        hooked = sorted(ai["items"], key=lambda i: -abs(i.get("impact", 0)))[:1]
        if hooked:
            h = hooked[0]
            sections.append({
                "title": "💡 值得想一想",
                "lines": [f"{h['title']}",
                          "想一层：这条消息沿 AI 产业链会先打到哪一环？（产业链页有传导图）"],
            })

    md_lines = [f"# 三分钟看懂今天 · {now_cn.strftime('%Y-%m-%d')}", ""]
    for s in sections:
        md_lines.append(f"## {s['title']}")
        md_lines.extend(f"- {l}" for l in s["lines"])
        md_lines.append("")
    md_lines.append("> 本简报由公开数据自动生成，不构成投资建议。")

    return {
        "date": now_cn.strftime("%Y-%m-%d"),
        "generated_at": now_cn.strftime("%H:%M") + " (UTC+8)",
        "sections": sections,
        "markdown": "\n".join(md_lines),
        "disclaimer": "由公开数据自动生成，不构成投资建议。",
    }
