"""因子提取。

价格因子（时点正确，可无偏回测）：全部用 shift 实现，t 日因子只含 t 日及之前信息。
财报因子（当前快照）：只参与当前选股打分，不进回测——免费数据没有历史时点财报，
强行回测会引入前视偏差，宁可少算也不自欺。
"""
import pandas as pd

from .data import zscore

# —— 价格因子（输入: 日线收盘价矩阵 dates × tickers）——

PRICE_FACTORS = {
    "mom_12_1": ("12-1月动量", "过去一年涨幅(剔除最近一个月)，追有持续性的强者"),
    "mom_6m": ("6月动量", "过去半年涨幅(剔除最近一个月)，中期趋势"),
    "low_vol": ("低波动", "过去半年日收益波动率取负——历史上稳的股票风险调整后回报更好"),
    "reversal_1m": ("1月反转", "最近一个月涨幅取负——短期涨多了倾向回调"),
}


def price_factor_panel(closes: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """计算所有价格因子的全历史面板（逐日值，时点正确）。"""
    rets = closes.pct_change()
    return {
        "mom_12_1": closes.shift(21) / closes.shift(252) - 1,
        "mom_6m": closes.shift(21) / closes.shift(126) - 1,
        "low_vol": -rets.rolling(126).std(),
        "reversal_1m": -(closes / closes.shift(21) - 1),
    }


def composite_at(panel: dict[str, pd.DataFrame], date) -> pd.Series:
    """某个调仓日的综合得分：各因子横截面 z-score 等权平均。"""
    zs = [zscore(df.loc[date]) for df in panel.values()]
    return sum(zs) / len(zs)


# —— 财报因子（当前快照）——

FUNDAMENTAL_FACTORS = {
    "value": ("价值", "盈利收益率+账面市值比+自由现金流收益率：买得便宜"),
    "quality": ("质量", "ROE+利润率+低杠杆：生意好、财务稳"),
    "growth": ("成长", "营收与盈利增速：业务在变大"),
}


def fundamental_scores(fund: pd.DataFrame) -> pd.DataFrame:
    """财报快照 → 价值/质量/成长三个标准化因子。"""
    out = pd.DataFrame(index=fund.index)
    earnings_yield = 1 / fund["trailing_pe"]
    book_yield = 1 / fund["price_to_book"]
    out["value"] = (zscore(earnings_yield) + zscore(book_yield)
                    + zscore(fund["fcf_yield"])) / 3
    out["quality"] = (zscore(fund["return_on_equity"]) + zscore(fund["profit_margin"])
                      + zscore(-fund["debt_to_equity"])) / 3
    out["growth"] = (zscore(fund["revenue_growth"]) + zscore(fund["earnings_growth"])) / 2
    return out
