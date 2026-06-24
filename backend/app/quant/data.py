"""量化管线的数据层：批量行情、财报快照、清洗工具。"""
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import yfinance as yf

from .universe import BENCHMARK, TOP100

MIN_HISTORY_DAYS = 400  # 不足约一年半历史的标的剔除


def fetch_prices(period: str = "3y") -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """批量拉日线收盘价。返回 (个股价格矩阵, 基准序列, 被剔除的标的)。"""
    raw = yf.download(TOP100 + [BENCHMARK], period=period, auto_adjust=True,
                      progress=False, group_by="column")
    closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    closes.index = pd.to_datetime(closes.index).tz_localize(None)

    bench = closes[BENCHMARK].dropna()
    stocks = closes.drop(columns=[BENCHMARK], errors="ignore")

    # 清洗：剔除历史太短或近期停更的列
    dropped = []
    keep = []
    for col in stocks.columns:
        s = stocks[col].dropna()
        if len(s) < MIN_HISTORY_DAYS or s.index[-1] < stocks.index[-5]:
            dropped.append(col)
        else:
            keep.append(col)
    return stocks[keep], bench, dropped


def _fetch_one_fundamental(ticker: str) -> dict | None:
    """单家公司最新财报关键指标（来自最近的年报/季报口径）。"""
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return None
    if not info.get("marketCap"):
        return None
    mc = info["marketCap"]
    fcf = info.get("freeCashflow")
    return {
        "ticker": ticker,
        "name": info.get("shortName") or ticker,
        "sector": info.get("sector"),
        "market_cap": mc,
        "trailing_pe": info.get("trailingPE"),
        "price_to_book": info.get("priceToBook"),
        "fcf_yield": (fcf / mc) if fcf else None,
        "return_on_equity": info.get("returnOnEquity"),
        "profit_margin": info.get("profitMargins"),
        "debt_to_equity": info.get("debtToEquity"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth") or info.get("earningsQuarterlyGrowth"),
    }


def fetch_fundamentals(tickers: list[str]) -> pd.DataFrame:
    """并发抓取全部公司的财报快照，失败的留 NaN。"""
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = [r for r in ex.map(_fetch_one_fundamental, tickers) if r]
    return pd.DataFrame(rows).set_index("ticker")


# —— 清洗与标准化工具 ——

def winsorize(s: pd.Series, lo: float = 0.01, hi: float = 0.99) -> pd.Series:
    """极值缩尾：把 1%/99% 分位之外的值拉回边界，防止离群值绑架因子。"""
    if s.dropna().empty:
        return s
    return s.clip(s.quantile(lo), s.quantile(hi))


def zscore(s: pd.Series) -> pd.Series:
    """横截面标准化；缺失值按中性(0)处理。"""
    s = winsorize(s)
    std = s.std()
    if not std or np.isnan(std):
        return pd.Series(0.0, index=s.index)
    return ((s - s.mean()) / std).fillna(0.0)
