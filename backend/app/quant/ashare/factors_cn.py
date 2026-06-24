"""A股价量因子（时点正确：t 日因子值只用 t 日及之前的信息，全部 shift 实现）。

为什么是这几个因子——尊重 A 股实证特性，而非照搬美股：
- 短期反转：A 股散户主导、追涨杀跌，短期涨多了倾向回调，是 A 股最稳的因子之一。
- 低换手（低关注）：换手率高 = 投机情绪重，历史上低换手票风险调整后更优。
- 低波动：低波动异象在 A 股同样成立。
- 12-1 动量：美股的王牌因子，但在 A 股历史上偏弱甚至为负——保留它，让 IC 诚实地说话。
- 非流动性(Amihud)：单位成交额对应的价格冲击，承担流动性风险换取溢价。
"""
import numpy as np
import pandas as pd

from data_cn import zscore

FACTOR_DOC = {
    "reversal_1m": ("1月反转", "最近一个月涨幅取负——A股散户追涨杀跌，短期涨多易回调"),
    "reversal_3m": ("3月反转", "最近一季涨幅取负——中期超买回归"),
    "low_turnover": ("低换手", "最近一月日均换手率取负——低关注/低投机的票更稳"),
    "low_vol": ("低波动", "最近半年日收益波动率取负——低波动异象"),
    "mom_12_1": ("12-1动量", "过去一年涨幅(剔除最近一月)——美股王牌，A股历史偏弱，留作对照"),
    "illiq": ("非流动性", "Amihud=|日收益|/成交额 的均值——承担流动性风险的溢价"),
}


def factor_panels(close: pd.DataFrame, turn: pd.DataFrame,
                  amount: pd.DataFrame) -> dict[str, pd.DataFrame]:
    rets = close.pct_change()
    illiq = (rets.abs() / amount.replace(0, np.nan)).rolling(21).mean()
    return {
        "reversal_1m": -(close / close.shift(21) - 1),
        "reversal_3m": -(close / close.shift(63) - 1),
        "low_turnover": -turn.rolling(21).mean(),
        "low_vol": -rets.rolling(126).std(),
        "mom_12_1": close.shift(21) / close.shift(252) - 1,
        "illiq": illiq,   # 已是「越大越非流动→预期收益越高」，方向为正
    }


def composite_at(panels: dict[str, pd.DataFrame], date, keys: list[str],
                 eligible: pd.Index) -> pd.Series:
    """某调仓日的综合得分：选定因子在「可交易票」上横截面 z-score 等权平均。"""
    parts = []
    for k in keys:
        s = panels[k].loc[date].reindex(eligible)
        parts.append(zscore(s))
    return sum(parts) / len(parts)
