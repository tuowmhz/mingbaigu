"""行情与基本面数据：基于 yfinance（Yahoo Finance 公开数据）。"""
import pandas as pd
import yfinance as yf

from ..cache import cached
from ..config import CACHE_TTL_FUNDAMENTALS, CACHE_TTL_PRICES


@cached(CACHE_TTL_PRICES)
def get_history(ticker: str, period: str = "2y") -> pd.DataFrame | None:
    """日线历史行情（开高低收量），失败返回 None。"""
    try:
        df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        if df is None or df.empty:
            return None
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df
    except Exception:
        return None


def history_to_series(df: pd.DataFrame, max_points: int = 500) -> list[dict]:
    """转成前端画图用的轻量序列，并附 20/50 日均线。"""
    out = df.copy()
    out["sma20"] = out["Close"].rolling(20).mean()
    out["sma50"] = out["Close"].rolling(50).mean()
    out = out.tail(max_points)
    return [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "close": round(float(r["Close"]), 2),
            "volume": int(r["Volume"]),
            "sma20": None if pd.isna(r["sma20"]) else round(float(r["sma20"]), 2),
            "sma50": None if pd.isna(r["sma50"]) else round(float(r["sma50"]), 2),
        }
        for idx, r in out.iterrows()
    ]


@cached(CACHE_TTL_FUNDAMENTALS)
def get_fundamentals(ticker: str) -> dict | None:
    """估值与盈利能力指标（来自 Yahoo Finance 公开口径）。"""
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return None
    if not info.get("regularMarketPrice") and not info.get("currentPrice"):
        return None

    def pick(*keys):
        for k in keys:
            v = info.get(k)
            if v is not None:
                return v
        return None

    return {
        "name": pick("shortName", "longName"),
        "sector": info.get("sector"),
        "market_cap": info.get("marketCap"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "price_to_book": info.get("priceToBook"),
        "dividend_yield": info.get("dividendYield"),
        "beta": info.get("beta"),
        "profit_margin": info.get("profitMargins"),
        "return_on_equity": info.get("returnOnEquity"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": pick("earningsGrowth", "earningsQuarterlyGrowth"),
        "analyst_target": info.get("targetMeanPrice"),
        "analyst_rating": info.get("recommendationKey"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
    }


def latest_quote(df: pd.DataFrame) -> dict:
    """从历史行情提取最新报价与涨跌幅。"""
    close = df["Close"]
    last = float(close.iloc[-1])
    prev = float(close.iloc[-2]) if len(close) > 1 else last
    return {
        "price": round(last, 2),
        "change": round(last - prev, 2),
        "change_pct": round((last / prev - 1) * 100, 2) if prev else 0.0,
        "as_of": df.index[-1].strftime("%Y-%m-%d"),
    }
