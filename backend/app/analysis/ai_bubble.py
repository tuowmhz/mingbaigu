"""AI 泡沫指数（AI Bubble Index）——Fear&Greed 式的"AI 泡沫体温计"。

诚实版（v1）：只用免费价格数据(yfinance)把算得实的信号做出来；订单backlog、期权流、
资金流、内部人交易、评级修正等免费拿不到的，明确标"数据待接入"，绝不编数凑分。
不构成投资建议：只描述"当前 AI 市场处于什么阶段、为什么"，不给买卖/仓位动作。

核心思路（泡沫后期最可靠的免费信号 = "质量下沉"）：
健康的牛市里资金追逐有真实收入/利润的龙头；泡沫后期资金转向无盈利、强叙事的小盘故事股，
龙头滞涨、故事股暴涨——这种"龙头 vs 故事股"的相对强弱，纯价格数据就能量出来，且最难造假。

指数 0-100：越高越像泡沫后期。
  0-25  绿 · 基本面驱动（龙头领涨，健康）
  25-50 黄 · 早期泡沫化（估值抬升，仍龙头主导）
  50-75 橙 · 泡沫中后期（质量下沉，故事股跑赢龙头）
  75-100 红 · 高风险泡沫（龙头转弱、无盈利小票疯涨）
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from ..cache import cached, disk_cache_load, disk_cache_save

ARTIFACT = Path(__file__).resolve().parent.parent.parent / "data" / "ai_bubble.json"

# 高质量龙头：大市值、有真实 AI 收入/利润
LEADERS = ["NVDA", "AVGO", "MSFT", "GOOGL", "AMZN", "META", "TSM", "AMD", "MU", "ASML"]
# 高弹性"故事股"：低收入/无盈利、强叙事（AI算力小盘、量子、光通信、矿转AI、AI软件小盘）
STORY = ["ALAB", "CRDO", "NBIS", "POET", "IREN", "CORZ", "WULF",
         "RGTI", "IONQ", "QBTS", "SOUN", "BBAI"]


def _basket_returns(close: pd.DataFrame, tickers: list[str], days: int) -> tuple[list, float]:
    """每只票最近 days 个交易日的收益率（等权），返回(逐票, 均值%)。"""
    rets = []
    for t in tickers:
        if t not in close:
            continue
        s = close[t].dropna()
        if len(s) < days + 5:
            continue
        rets.append(float(s.iloc[-1] / s.iloc[-days - 1] - 1) * 100)
    return rets, (float(np.mean(rets)) if rets else 0.0)


def _above_50dma_frac(close: pd.DataFrame, tickers: list[str]) -> float:
    cnt = tot = 0
    for t in tickers:
        if t not in close:
            continue
        s = close[t].dropna()
        if len(s) < 55:
            continue
        tot += 1
        if s.iloc[-1] > s.tail(50).mean():
            cnt += 1
    return (cnt / tot) if tot else 0.5


def _norm(x: float, lo: float, hi: float) -> float:
    """把 x 从 [lo,hi] 线性映射到 [0,100] 并夹紧。"""
    if hi == lo:
        return 50.0
    return float(max(0.0, min(100.0, (x - lo) / (hi - lo) * 100)))


def _zone(v: float) -> tuple[str, str]:
    if v < 25:
        return "green", "绿"
    if v < 50:
        return "yellow", "黄"
    if v < 75:
        return "orange", "橙"
    return "red", "红"


@cached(3600)
def get_ai_bubble() -> dict | None:
    cached_result = disk_cache_load(ARTIFACT, max_age_seconds=3600)
    if cached_result is not None:
        return cached_result

    try:
        raw = yf.download(LEADERS + STORY, period="1y", auto_adjust=True, progress=False)["Close"]
    except Exception:
        return None
    if raw is None or raw.empty:
        return None

    lead_3m_list, lead_3m = _basket_returns(raw, LEADERS, 63)
    story_3m_list, story_3m = _basket_returns(raw, STORY, 63)
    _, lead_1m = _basket_returns(raw, LEADERS, 21)
    _, story_1m = _basket_returns(raw, STORY, 21)
    lead_brd = _above_50dma_frac(raw, LEADERS)
    story_brd = _above_50dma_frac(raw, STORY)
    story_med_3m = float(np.median(story_3m_list)) if story_3m_list else 0.0
    spread_3m = story_3m - lead_3m

    # 三个可量化子信号（0-100，越高越泡沫）
    quality_sink = _norm(spread_3m, -15, 35)           # 故事股相对龙头跑赢幅度
    froth = _norm(story_med_3m, 0, 70)                 # 故事股绝对涨幅（投机热度）
    divergence = _norm(story_brd - lead_brd, -0.4, 0.4)  # 故事股站上均线比例 − 龙头
    lead_weak = _norm(-lead_3m, -25, 15) * 0.5 + (1 - lead_brd) * 100 * 0.5  # 龙头转弱

    index = round(0.35 * quality_sink + 0.25 * froth + 0.20 * divergence + 0.20 * lead_weak)
    index = int(max(0, min(100, index)))
    key, cn = _zone(index)

    components = [
        {"key": "quality_sink", "name": "质量下沉", "value": round(quality_sink),
         "status": _zone(quality_sink)[0],
         "note": f"故事股 3 月 {story_3m:+.0f}% vs 龙头 {lead_3m:+.0f}%（差 {spread_3m:+.0f}pp）",
         "desc": "看资金在追龙头还是追故事股。故事股(无盈利小盘)大幅跑赢龙头，说明市场从『买公司』变成『买叙事』——泡沫后期的头号特征。"},
        {"key": "froth", "name": "故事股投机热度", "value": round(froth),
         "status": _zone(froth)[0],
         "note": f"故事股 3 月中位涨幅 {story_med_3m:+.0f}%，{round(story_brd*100)}% 站上 50 日线",
         "desc": "无盈利概念股(量子/光通信/矿转AI/AI软件小盘)整体涨多猛、有多少在均线上。涨得越疯越拥挤，回撤时也越剧烈。"},
        {"key": "leaders_weak", "name": "龙头转弱", "value": round(lead_weak),
         "status": _zone(lead_weak)[0],
         "note": f"龙头 3 月 {lead_3m:+.0f}%，{round(lead_brd*100)}% 站上 50 日线",
         "desc": "高质量龙头(NVDA/AVGO/微软/台积电等)是否还在领涨。龙头滞涨甚至回落、而小票疯涨，往往是真正的好资金在悄悄撤离。"},
    ]

    # 免费数据拿不到、诚实标注待接入的信号
    pending = [
        "好消息不涨/坏消息大跌（财报后股价反应）",
        "Capex 增长 vs AI 变现（hyperscaler 资本开支与回报）",
        "供应链远期故事 vs 当前订单（backlog/RPO）",
        "融资潮与内部人卖出（增发/可转债/insider selling）",
        "流动性驱动（期权流/ETF 资金流/杠杆）",
    ]

    # 龙头状态：让解读与"龙头转弱"子信号一致，避免在龙头其实仍强时硬说它转弱
    lead_state = ("而且龙头本身已明显转弱、资金像在撤离" if lead_weak >= 50
                  else "目前龙头自身仍强——属『普涨式狂热』而非龙头撤离，但故事股的极端跑赢已是后段特征")
    hints = {
        "green": "当前更像基本面驱动：资金集中在有真实收入的龙头，故事股没有系统性跑赢。这是相对健康的结构（描述现状，不预测走势）。",
        "yellow": "出现早期泡沫化迹象：估值与情绪抬升，但仍主要由龙头主导。需要留意故事股是否开始接棒。",
        "orange": f"质量在下沉：无盈利故事股明显跑赢龙头，资金从『买公司』转向『买叙事』——历史上这是泡沫由中期转向后期的典型结构。{lead_state}。这是对当前市场结构的描述，不是顶部预测。",
        "red": f"高风险泡沫结构：无盈利故事股极端跑赢龙头、投机热度很高，市场质量明显恶化。{lead_state}。历史上这种分化常出现在泡沫后段——但泡沫可以持续更久，本指数不预测拐点。",
    }

    # 近 ~6 个月的"质量下沉"走势（故事股−龙头 的 21 日相对强弱，给前端画 sparkline）
    hist = []
    try:
        common = [t for t in LEADERS + STORY if t in raw]
        px = raw[common].dropna(how="all")
        lead_idx = px[[t for t in LEADERS if t in px]].pct_change(21).mean(axis=1)
        story_idx = px[[t for t in STORY if t in px]].pct_change(21).mean(axis=1)
        rs = (story_idx - lead_idx).dropna().tail(126)
        hist = [round(_norm(float(v) * 100, -15, 35)) for v in rs]
    except Exception:
        hist = []

    return disk_cache_save(ARTIFACT, {
        "index": index,
        "level": key,
        "level_cn": cn,
        "stage_cn": {"green": "基本面驱动", "yellow": "早期泡沫化",
                     "orange": "泡沫中后期", "red": "高风险泡沫"}[key],
        "components": components,
        "pending": pending,
        "history": hist,
        "as_of": str(raw.index[-1].date()),
        "hint": hints[key],
        "leaders": LEADERS,
        "story": STORY,
        "methodology": "基于免费价格数据：龙头篮子 vs 故事股篮子的相对强弱、故事股投机热度、龙头是否转弱，三个可量化子信号加权成 0-100。订单/期权流/资金流/内部人/评级等需付费数据，标记为待接入，未计入评分。",
        "disclaimer": "教育性市场结构观察，描述当前 AI 板块『龙头 vs 故事股』的资金结构，不预测顶部、不构成投资建议。",
    })
