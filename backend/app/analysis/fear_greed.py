"""恐惧贪婪指数（自研，CNN Fear & Greed 同源方法论）。

为什么自己算而不爬 CNN：接口反爬、方法黑箱。我们用同样的思想、
免费数据和完全透明的五个成分，每个成分换算成"在过去三年里的分位数"(0-100)：

  1. 市场动量：标普500 相对其 125 日均线的偏离——涨势越强越贪婪；
  2. 市场波动：VIX 相对其 50 日均线（取反）——恐慌时 VIX 飙升；
  3. 避险需求：近 20 日股票(SPY)与长债(TLT)的收益差——资金逃向债券=恐惧；
  4. 垃圾债需求：近 20 日高收益债(HYG)与投资级债(LQD)的收益差——
     愿意买垃圾债=风险胃口大=贪婪；
  5. 市场广度：股票池中站上 50 日均线的比例——只有少数股票撑指数=外强中干。

五者平均 → 0-100：≤25 极度恐惧，≤45 恐惧，≤55 中性，≤75 贪婪，>75 极度贪婪。

第一性原理（为什么极度恐惧时买大盘往往不错）：
价格 = 未来现金流 ÷ 要求回报率。恐慌不怎么改变大盘的长期现金流，
但会急剧抬高"要求回报率"（人人都要更高补偿才肯持有风险资产）——
分母变大、价格被砸低，于是"未来的预期回报"被机械地抬高了。
另外，极度恐惧意味着想卖的人大多已经卖了（卖压枯竭），边际买家定价。
注意：这是几个月维度的统计倾向，不是抄底按钮——恐惧可以更恐惧（2008）。
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from ..cache import cached, disk_cache_load, disk_cache_save
from ..quant.universe import TOP100

ARTIFACT = Path(__file__).resolve().parent.parent.parent / "data" / "fear_greed.json"


def _pctile_now(series: pd.Series, window: int = 756) -> float:
    """当前值在过去 ~3 年里的分位数（0-100）。"""
    s = series.dropna().tail(window)
    if len(s) < 60:
        return 50.0
    return float((s < s.iloc[-1]).mean() * 100)


def _label(v: float) -> tuple[str, str]:
    if v <= 25:
        return "extreme_fear", "极度恐惧"
    if v <= 45:
        return "fear", "恐惧"
    if v <= 55:
        return "neutral", "中性"
    if v <= 75:
        return "greed", "贪婪"
    return "extreme_greed", "极度贪婪"


@cached(3600)
def get_fear_greed() -> dict | None:
    cached_result = disk_cache_load(ARTIFACT, max_age_seconds=3600)
    if cached_result is not None:
        return cached_result

    try:
        raw = yf.download(["SPY", "^VIX", "TLT", "HYG", "LQD"], period="4y",
                          auto_adjust=True, progress=False)["Close"]
        spy, vix = raw["SPY"].dropna(), raw["^VIX"].dropna()
        tlt, hyg, lqd = raw["TLT"].dropna(), raw["HYG"].dropna(), raw["LQD"].dropna()
        breadth_raw = yf.download(TOP100, period="2y", auto_adjust=True,
                                  progress=False)["Close"]
    except Exception:
        return None

    # 广度（先算）：只对当日真正有收盘价的成分计算"站上 50 日均线的比例"，
    # 并丢弃覆盖率不足的交易日。yfinance 在当天未收盘时，最新一根 bar 多数成分
    # 为 NaN；若按 NaN>均线=False 处理，会让广度瞬间塌成 0（假极度恐惧）——
    # 这是指数此前系统性偏低、与 CNN 拉开差距的根因。
    _ma50 = breadth_raw.rolling(50).mean()
    _valid = breadth_raw.notna() & _ma50.notna()
    _coverage = _valid.mean(axis=1)
    above = (breadth_raw > _ma50).where(_valid).mean(axis=1)
    above = above[_coverage >= 0.9].dropna()

    # 把宏观序列对齐到最后一根"完整"交易日，避免未收盘 bar 污染动量/波动等成分
    if len(above):
        _last = above.index[-1]
        spy, vix, tlt, hyg, lqd = (s[s.index <= _last] for s in (spy, vix, tlt, hyg, lqd))

    # 1. 动量：SPY 相对 125 日均线
    momentum_series = spy / spy.rolling(125).mean() - 1
    momentum = _pctile_now(momentum_series)

    # 2. 波动：VIX 相对 50 日均线（取反——VIX 高于均线=恐惧）
    vol_series = -(vix - vix.rolling(50).mean())
    volatility = _pctile_now(vol_series)

    # 3. 避险需求：股债 20 日收益差
    safe_series = spy.pct_change(20) - tlt.pct_change(20)
    safe_haven = _pctile_now(safe_series)

    # 4. 垃圾债需求：HYG vs LQD 20 日收益差
    junk_series = hyg.pct_change(20) - lqd.pct_change(20)
    junk = _pctile_now(junk_series)

    # 5. 广度：分位数（above 已在上方按覆盖率清洗，剔除了未收盘的不完整 bar）
    breadth = _pctile_now(above, window=378)

    components = [
        {"key": "momentum", "name": "市场动量", "value": round(momentum),
         "note": "标普500 vs 125日均线",
         "desc": "标普500 离它 125 日均线越远、涨得越凶，市场越亢奋。高分=贪婪，跌破均线偏恐惧。"},
        {"key": "volatility", "name": "市场波动", "value": round(volatility),
         "note": "VIX vs 50日均线（反向）",
         "desc": "VIX 是『恐慌指数』，越高说明大家越害怕。这里取反：VIX 低=平静=高分（贪婪），VIX 飙升=低分（恐惧）。"},
        {"key": "safe_haven", "name": "避险需求", "value": round(safe_haven),
         "note": "股票 vs 长债 20日收益差",
         "desc": "比近 20 天股票和长期国债谁涨得多。钱涌向债券避险=低分（恐惧），敢追股票=高分（贪婪）。"},
        {"key": "junk", "name": "垃圾债胃口", "value": round(junk),
         "note": "高收益债 vs 投资级债",
         "desc": "比『垃圾债（高收益债）』和安全的投资级债。愿意买垃圾债博收益=风险胃口大=高分（贪婪），躲回安全债=恐惧。"},
        {"key": "breadth", "name": "市场广度", "value": round(breadth),
         "note": "股票池站上50日线比例",
         "desc": "多少只股票站上了 50 日均线。多数都涨=健康的贪婪（高分）；只剩少数权重股撑指数=外强中干、偏恐惧。"},
    ]
    index = round(float(np.mean([c["value"] for c in components])))
    key, cn = _label(index)

    # 指数的近一年走势（按同样方法逐日回算，给前端画 sparkline）
    hist = pd.DataFrame({
        "momentum": momentum_series, "vol": vol_series,
        "safe": safe_series, "junk": junk_series,
    }).dropna()
    ranks = hist.rolling(756, min_periods=60).rank(pct=True) * 100
    idx_series = ranks.mean(axis=1).dropna().tail(252)

    hints = {
        "extreme_fear": "历史上极度恐惧区间往往是布局大盘的较好时点（风险溢价被恐慌抬高、卖压趋于枯竭），但'极度恐惧'可以持续数月并继续恶化——分批、买大盘或优质资产，别一把梭。",
        "fear": "市场偏谨慎。逆向者开始关注，但单靠情绪指标不构成买入理由。",
        "neutral": "情绪不提供方向信息，看基本面和技术面。",
        "greed": "市场偏乐观，注意仓位纪律——贪婪阶段的利润是借来的，回撤时要还。",
        "extreme_greed": "历史上极度贪婪区间之后的中期回报显著偏低：人人都已上车，边际买家枯竭。不必清仓，但此时加杠杆/追高是统计上最差的决策。",
    }

    return disk_cache_save(ARTIFACT, {
        "index": index,
        "label": key,
        "label_cn": cn,
        "components": components,
        "history": [round(float(v)) for v in idx_series],
        "as_of": str(idx_series.index[-1].date()),
        "hint": hints[key],
        "methodology": "CNN Fear & Greed 同源方法论的五成分自研版，每个成分为其指标在过去三年中的分位数（0-100），等权平均。",
    })
