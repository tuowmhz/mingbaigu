"""技术指标特征工程。所有特征只用 t 日及之前的数据，避免未来函数。"""
import numpy as np
import pandas as pd

HORIZON = 5  # 预测未来 5 个交易日


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def macd_hist(close: pd.Series) -> pd.Series:
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd - signal


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """输入日线 OHLCV，输出特征矩阵 + 标签（未来 5 日收益）。"""
    close, volume = df["Close"], df["Volume"]
    feat = pd.DataFrame(index=df.index)

    feat["ret_1d"] = close.pct_change()
    feat["ret_5d"] = close.pct_change(5)
    feat["ret_20d"] = close.pct_change(20)

    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    feat["close_sma20"] = close / sma20 - 1
    feat["sma20_sma50"] = sma20 / sma50 - 1

    feat["rsi14"] = rsi(close)
    feat["macd_hist"] = macd_hist(close) / close  # 归一化

    feat["vol_20d"] = close.pct_change().rolling(20).std()
    feat["volume_ratio"] = volume / volume.rolling(20).mean()

    std20 = close.rolling(20).std()
    feat["bb_pos"] = (close - sma20) / (2 * std20)  # 布林带位置

    hi52 = close.rolling(252, min_periods=60).max()
    feat["dist_52w_high"] = close / hi52 - 1

    # 标签：未来 HORIZON 日收益（最后 HORIZON 行无标签，用于实时预测）
    feat["fwd_ret"] = close.shift(-HORIZON) / close - 1
    return feat


FEATURE_COLS = [
    "ret_1d", "ret_5d", "ret_20d", "close_sma20", "sma20_sma50",
    "rsi14", "macd_hist", "vol_20d", "volume_ratio", "bb_pos", "dist_52w_high",
]


def tech_snapshot(df: pd.DataFrame) -> dict:
    """给对抗验证用的当前技术面快照。"""
    close = df["Close"]
    sma50 = close.rolling(50).mean()
    hi52 = close.rolling(252, min_periods=60).max()
    r = rsi(close).iloc[-1]
    return {
        "rsi": float(r) if not np.isnan(r) else 50.0,
        "momentum_20d": float(close.iloc[-1] / close.iloc[-21] - 1) if len(close) > 21 else 0.0,
        "close_above_sma50": bool(close.iloc[-1] > sma50.iloc[-1]) if not np.isnan(sma50.iloc[-1]) else True,
        "dist_52w_high": float(close.iloc[-1] / hi52.iloc[-1] - 1) if not np.isnan(hi52.iloc[-1]) else 0.0,
    }
