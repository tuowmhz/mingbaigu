"""A股数据加载层（读 fetch_all.py 缓存），构建时点正确的面板。"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
BARS = os.path.join(CACHE, "bars")

BENCH_OF = {"hs300": "sh.000300", "zz500": "sh.000905", "zz800": "sh.000300"}


def load_constituents() -> dict:
    with open(os.path.join(CACHE, "constituents.json")) as f:
        return json.load(f)


def _read_bar(code: str) -> pd.DataFrame | None:
    path = os.path.join(BARS, code.replace(".", "_") + ".csv")
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    df = pd.read_csv(path)
    if df.empty:
        return None
    df["date"] = pd.to_datetime(df["date"])
    for c in ("close", "volume", "amount", "turn", "pctChg"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.set_index("date")


def build_panels(codes: list[str]) -> dict[str, pd.DataFrame]:
    """把若干只票的日线拼成 dates×codes 的面板（close/turn/amount）。"""
    closes, turns, amts = {}, {}, {}
    for code in codes:
        df = _read_bar(code)
        if df is None or df["close"].dropna().empty:
            continue
        closes[code] = df["close"]
        turns[code] = df["turn"]
        amts[code] = df["amount"]
    close = pd.DataFrame(closes).sort_index()
    turn = pd.DataFrame(turns).reindex_like(close)
    amount = pd.DataFrame(amts).reindex_like(close)
    return {"close": close, "turn": turn, "amount": amount}


def bench_series(name: str) -> pd.Series:
    df = _read_bar(BENCH_OF[name])
    return df["close"].dropna()


def membership_mask(universe: str, dates_index: pd.DatetimeIndex) -> pd.DataFrame:
    """构造时点成分股掩码：mask.loc[t, code]=True 表示 t 日 code 在池内。

    用「不晚于 t 的最近一次月度成分快照」前向填充——避免用未来成分。
    universe='zz800' = 沪深300 ∪ 中证500。
    """
    cons = load_constituents()
    if universe == "zz800":
        snaps = {}
        keys = sorted(set(cons["hs300"]) | set(cons["zz500"]))
        for k in keys:
            snaps[k] = set(cons["hs300"].get(k, [])) | set(cons["zz500"].get(k, []))
    else:
        snaps = {k: set(v) for k, v in cons[universe].items()}
    snap_dates = pd.to_datetime(sorted(snaps.keys()))
    all_codes = sorted({c for s in snaps.values() for c in s})
    mask = pd.DataFrame(False, index=dates_index, columns=all_codes)
    for t in dates_index:
        prior = snap_dates[snap_dates <= t]
        if len(prior) == 0:
            continue
        key = prior[-1].strftime("%Y-%m-%d")
        members = snaps.get(key, set())
        cols = [c for c in members if c in mask.columns]
        mask.loc[t, cols] = True
    return mask


# —— 横截面清洗/标准化（与主项目 data.py 同口径）——

def winsorize(s: pd.Series, lo: float = 0.01, hi: float = 0.99) -> pd.Series:
    if s.dropna().empty:
        return s
    return s.clip(s.quantile(lo), s.quantile(hi))


def zscore(s: pd.Series) -> pd.Series:
    s = winsorize(s)
    std = s.std()
    if not std or np.isnan(std):
        return pd.Series(0.0, index=s.index)
    return ((s - s.mean()) / std).fillna(0.0)
