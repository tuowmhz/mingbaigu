"""消息面研判引擎：金融事件抽取 + 金融词典情绪 + 时间衰减 → 未来大致涨跌信号。

为什么不只用通用情绪模型：VADER 是社交媒体词典，分不清
"JPMorgan cuts price target on rival"（利空别人）和財经语境的褒贬强度。
这里叠加三层信号：
  1. 金融事件抽取：评级/业绩/指引/并购/诉讼等 20+ 类事件，各带经验方向权重；
  2. 金融词典：Loughran-McDonald 风格的财经正负词表；
  3. 时间衰减：72 小时半衰期，越新的消息权重越大。
输出综合信号分（约 -3 ~ +3）与五档方向研判，并列出关键驱动新闻。
"""
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# (正则, 事件标签, 方向权重)。权重为经验值：业绩/指引 > 评级 > 其他。
_EVENT_DEFS = [
    (r"upgrad\w*|raises? (?:price )?target|raised to (?:buy|overweight|outperform)|initiat\w+ .{0,30}(?:buy|outperform|overweight)", "评级上调", 2.0),
    (r"downgrad\w*|(?:cuts?|lowers?|slashes) (?:price )?target|lowered to (?:sell|underweight|underperform)", "评级下调", -2.0),
    (r"beats? (?:wall street )?estimat\w*|tops? (?:estimat|expectation)\w*|exceeds? expectation\w*|earnings beat|record (?:quarterly )?(?:revenue|profit|earnings)", "业绩超预期", 2.5),
    (r"miss(?:es)? estimat\w*|falls? short of|earnings miss|disappoint\w*", "业绩不及预期", -2.5),
    (r"(?:raises?|lifts?|boosts?) (?:full.year |annual )?(?:guidance|outlook|forecast)", "上调指引", 2.5),
    (r"(?:cuts?|lowers?|slashes|trims) (?:full.year |annual )?(?:guidance|outlook|forecast)|withdraws guidance", "下调指引", -2.5),
    (r"to be acquired|acquisition target|takeover (?:bid|offer|target)|buyout offer", "被收购", 2.5),
    (r"acquir\w+|merger|agrees to buy", "并购", 1.0),
    (r"lawsuit|sues?\b|probe\w*|investigat\w*|sec charges|antitrust|fined?\b|penalty", "诉讼/监管", -1.8),
    (r"layoffs?|job cuts|cutting .{0,20}jobs", "裁员", -1.0),
    (r"buyback|share repurchase", "回购", 1.5),
    (r"(?:raises?|hikes?|boosts?) .{0,20}dividend|dividend (?:increase|hike)", "上调分红", 1.5),
    (r"(?:cuts?|suspends?) .{0,20}dividend", "削减分红", -2.5),
    (r"insider (?:buying|purchases)", "内部人增持", 1.0),
    (r"(?:wins?|awarded|lands?|secures?) .{0,30}(?:contract|deal|order)|partnership|teams up with", "合同/合作", 1.2),
    (r"short.?sell\w*|hindenburg|muddy waters", "做空报告", -2.0),
    (r"(?:ceo|cfo|chief executive) .{0,30}(?:steps down|resigns|departs|exits|fired)", "高管离职", -1.2),
    (r"data breach|hacked|cyberattack|outage", "安全事故", -1.5),
    (r"recall\w*", "产品召回", -1.5),
    (r"stock split", "拆股", 0.8),
    (r"tariffs?|trade war|sanctions", "宏观/关税", -0.4),
    (r"launch\w*|unveil\w*|debuts?", "新品发布", 0.8),
]
_EVENTS = [(re.compile(p, re.I), tag, w) for p, tag, w in _EVENT_DEFS]

# 精简版财经正负词表（Loughran-McDonald 风格）
_POS = frozenset("""beat beats tops exceeds surge surges soar soars jump jumps rally rallies
record strong strength growth grows profit profits profitable upgrade upgraded raise raised
boost boosts bullish outperform gain gains win wins winner approval approve approved expand
expands expansion optimistic upbeat momentum constructive robust resilient breakthrough
accelerate accelerates upside""".split())
_NEG = frozenset("""miss misses fall falls drop drops plunge plunges sink sinks slump slumps
tumble tumbles decline declines weak weakness loss losses downgrade downgraded cut cuts
lower lowers bearish underperform lawsuit probe investigation fine fines recall warning
warns fear fears concern concerns risk risks layoff layoffs fraud default bankruptcy crash
selloff pressure headwind headwinds slowdown disappointing struggling""".split())

_WORD_RX = re.compile(r"[a-z']+")
_HALF_LIFE_HOURS = 72.0

# —— 中文层（A股新闻）：VADER 不懂中文，用中文金融事件库 + 词典 ——
_ZH_EVENT_DEFS = [
    (r"业绩预增|净利(?:润)?(?:大增|增长|翻倍)|超(?:市场)?预期", "业绩预增", 2.5),
    (r"业绩预亏|净利(?:润)?(?:大降|下滑|亏损)|不及预期", "业绩预亏", -2.5),
    (r"回购", "回购", 1.5),
    (r"(?:股东|高管|实控人).{0,6}增持|拟增持", "增持", 1.2),
    (r"(?:股东|高管|实控人).{0,6}减持|拟减持|清仓", "减持", -1.2),
    (r"立案|调查|处罚|警示函|违规", "监管处罚", -2.0),
    (r"中标|签(?:订|署).{0,10}(?:合同|协议|订单)", "中标/订单", 1.5),
    (r"涨停", "涨停", 1.0),
    (r"跌停", "跌停", -1.5),
    (r"解禁", "解禁", -1.0),
    (r"分红|派息", "分红", 1.0),
    (r"重组|并购|收购", "并购重组", 1.0),
    (r"退市|ST", "退市风险", -2.5),
]
_ZH_EVENTS = [(re.compile(p), tag, w) for p, tag, w in _ZH_EVENT_DEFS]
_ZH_POS = ["利好", "大涨", "上涨", "突破", "新高", "增长", "盈利", "向好", "受益", "强劲", "提价"]
_ZH_NEG = ["利空", "大跌", "下跌", "跳水", "新低", "下滑", "亏损", "承压", "风险", "疲软", "降价", "暴雷"]
_CJK_RX = re.compile(r"[一-鿿]")

# —— 分析师角色识别 ——
# "JPMorgan Upgrades Tesla" 对 JPM 来说不是利好（它是分析师，不是被评级方）。
# 公司名后紧跟评级动词、且宾语不是自家事务（分红/指引/回购）时，判定为分析师角色。
_RATING_TAGS = {"评级上调", "评级下调"}
_ANALYST_VERBS = r"(?:upgrades?|downgrades?|raises?|lifts?|cuts?|slashes|initiates?|reiterates?|maintains?|resumes?)"
_NOT_SELF_BUSINESS = r"(?!\s+(?:its|their)\b)(?!\s+(?:dividend|guidance|outlook|forecast|buyback|payout|prices|wages))"

_ALIASES = {
    "JPM": ["jpmorgan", "jp morgan", "j.p. morgan"],
    "BAC": ["bank of america", "bofa"],
    "WFC": ["wells fargo"],
    "C": ["citigroup", "citibank", "citi"],
    "GS": ["goldman sachs", "goldman"],
    "MS": ["morgan stanley"],
    "AAPL": ["apple"],
    "MSFT": ["microsoft"],
    "NVDA": ["nvidia"],
    "GOOGL": ["google", "alphabet"],
    "AMZN": ["amazon"],
    "META": ["meta"],
    "TSLA": ["tesla"],
}


def _is_analyst_role(title: str, aliases: list[str]) -> bool:
    for a in aliases:
        if re.search(rf"\b{re.escape(a)}(?:'s)?\s+(?:analysts?\s+)?{_ANALYST_VERBS}\b{_NOT_SELF_BUSINESS}",
                     title, re.I):
            return True
    return False


def _parse_time(s: str):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(s)
    except Exception:
        return None


def _clip(v, lo, hi):
    return max(lo, min(hi, v))


def _analyze_zh_item(item: dict, text_override: float | None = None) -> dict:
    """中文新闻：中文事件库 + 情绪分。FinBERT2 在跑时用其打分，否则中文词典兜底。"""
    title = item.get("title", "")
    events, event_score = [], 0.0
    for rx, tag, w in _ZH_EVENTS:
        if rx.search(title):
            events.append(tag)
            event_score += w
    event_score = _clip(event_score, -2.5, 2.5)

    if text_override is not None:
        text_score = _clip(text_override, -1, 1)
    else:
        pos = sum(1 for w in _ZH_POS if w in title)
        neg = sum(1 for w in _ZH_NEG if w in title)
        text_score = _clip((pos - neg) / max(pos + neg, 1), -1, 1)
    impact = round(_clip(text_score + event_score, -3, 3), 2)

    dt = _parse_time(item.get("published", ""))
    if dt and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    out = dict(item)
    out["events"] = events
    out["impact"] = impact
    out["impact_label"] = "利好" if impact >= 0.5 else ("利空" if impact <= -0.5 else "中性")
    out["_dt"] = dt
    return out


def _analyze_item(item: dict, aliases: list[str],
                  text_override: float | None = None) -> dict:
    title = item.get("title", "")
    if _CJK_RX.search(title):
        return _analyze_zh_item(item, text_override)
    analyst_role = _is_analyst_role(title, aliases)

    events, event_score = [], 0.0
    for rx, tag, w in _EVENTS:
        if rx.search(title):
            if analyst_role and tag in _RATING_TAGS:
                continue  # 它是评级方而非被评级方，事件不算在它头上
            events.append(tag)
            event_score += w
    event_score = _clip(event_score, -2.5, 2.5)

    words = _WORD_RX.findall(title.lower())
    pos = sum(1 for w in words if w in _POS)
    neg = sum(1 for w in words if w in _NEG)
    lex = (pos - neg) / max(pos + neg, 1)

    # 文本情绪：FinGPT 本地模型优先（若服务在跑），否则 VADER+财经词典各占一半
    if text_override is not None:
        text_score = _clip(text_override, -1, 1)
    else:
        text_score = _clip(0.5 * item.get("sentiment", 0.0) + 0.5 * lex, -1, 1)
    if analyst_role:
        text_score *= 0.3  # 标题里的褒贬属于被评级的别家公司，大幅降权
        events.append("对他股评级")
    impact = round(_clip(text_score + event_score, -3, 3), 2)

    dt = _parse_time(item.get("published", ""))
    if dt and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    out = dict(item)
    out["events"] = events
    out["impact"] = impact
    out["impact_label"] = "利好" if impact >= 0.5 else ("利空" if impact <= -0.5 else "中性")
    out["_dt"] = dt
    return out


def _direction(score: float) -> tuple[str, str, str]:
    """信号分 → (方向key, 方向中文, 未来大致涨跌提示)。"""
    if score >= 1.2:
        return ("strong_bullish", "强利好",
                "未来几个交易日上行概率明显偏高，但重大利好常在发布当日已被部分定价")
    if score >= 0.4:
        return ("bullish", "偏暖", "短线略偏上行")
    if score > -0.4:
        return ("neutral", "不明朗", "消息面没有明确方向，涨跌更多取决于技术面与大盘")
    if score > -1.2:
        return ("bearish", "偏冷", "短线略偏下行")
    return ("strong_bearish", "强利空", "未来几个交易日下行风险明显偏高，注意控制仓位")


def analyze_news(news: dict | None, ticker: str | None = None) -> dict | None:
    """输入 get_news 的结果，输出条目（带事件标签/影响分）+ 综合信号。"""
    if not news or not news.get("items"):
        return None
    aliases = _ALIASES.get(ticker or "", [])

    # 情感微服务在跑时：英文交给 FinBERT、中文交给 FinBERT2 批量打分（各按语言路由）
    from ..data.sentiment_client import score_batch
    en_titles = [it.get("title", "") for it in news["items"]
                 if it.get("title") and not _CJK_RX.search(it["title"])]
    zh_titles = [it.get("title", "") for it in news["items"]
                 if it.get("title") and _CJK_RX.search(it["title"])]
    en_ov = score_batch(en_titles, "en") or {}
    zh_ov = score_batch(zh_titles, "zh") or {}
    overrides = {**en_ov, **zh_ov}
    parts = []
    if en_ov:
        parts.append("FinBERT(英文)")
    if zh_ov:
        parts.append("FinBERT2(中文)")
    engine = " + ".join(parts) if parts else "VADER+财经词典"

    items = [_analyze_item(it, aliases, overrides.get(it.get("title", "")))
             for it in news["items"]]

    now = datetime.now(timezone.utc)
    total, total_w = 0.0, 0.0
    for it in items:
        dt = it.pop("_dt", None)
        if dt is not None:
            age_h = max(0.0, (now - dt).total_seconds() / 3600)
            recency = 0.5 ** (age_h / _HALF_LIFE_HOURS)
        else:
            recency = 0.3  # 没有时间戳的按"较旧"处理
        # 显著性加权：带实质事件的新闻话语权大，中性闲聊只占小权重，
        # 避免 20 条无关报道把 1 条重磅财报稀释成"不明朗"
        significance = max(0.25, min(1.5, abs(it["impact"])))
        w = recency * significance
        it["recency_weight"] = round(recency, 3)
        it["published_ts"] = dt.timestamp() if dt is not None else None
        total += it["impact"] * w
        total_w += w
    score = round(total / total_w, 2) if total_w else 0.0

    key, cn, hint = _direction(score)
    by_impact = sorted(items, key=lambda i: -i["impact"])

    def driver(it):
        return {"title": it["title"], "link": it.get("link", ""),
                "events": it["events"], "impact": it["impact"]}

    signal = {
        "score": score,
        "direction": key,
        "direction_cn": cn,
        "trend_hint": hint,
        "sentiment_engine": engine,
        "n_items": len(items),
        "positive": sum(1 for i in items if i["impact_label"] == "利好"),
        "negative": sum(1 for i in items if i["impact_label"] == "利空"),
        "neutral": sum(1 for i in items if i["impact_label"] == "中性"),
        "drivers_positive": [driver(i) for i in by_impact[:3] if i["impact"] >= 0.5],
        "drivers_negative": [driver(i) for i in reversed(by_impact[-3:]) if i["impact"] <= -0.5],
    }
    return {**news, "items": items, "signal": signal}
