"""生成「当前交易日」的策略持仓（纸面跟踪用）。

与回测彻底分开：每月只需抓一次当前成分股的最近行情，实时算因子→选前30→落账本。
诚实点：这是真·向前的样本外检验——记录此刻的持仓，让未知的未来去验证它。
"""
import json
import os
import socket
import sys
from datetime import datetime

import baostock as bs
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from factors_cn import factor_panels
from data_cn import zscore

socket.setdefaulttimeout(30)
HERE = os.path.dirname(os.path.abspath(__file__))

# 「低波蓝筹」= 纯低换手+低波动两因子：样本外最强、匹配品牌、不被高动量劫持。
# （动量虽抬高全样本数字，但那是2019-21样本内的牛市虚高，且会拉进高波动票，故剔除。）
SELECTED = {
    "hs300": ["low_turnover", "low_vol"],
    "zz800": ["low_turnover", "low_vol"],
    "zz500": ["low_turnover", "low_vol"],
}
Z_CLIP = 3.0  # 单因子 z 值封顶，防极端值劫持组合
QUERY = {"hs300": "query_hs300_stocks", "zz500": "query_zz500_stocks"}
UNAME = {"hs300": "沪深300", "zz500": "中证500", "zz800": "中证800"}
TOP_N = 30


def current_constituents(universe, asof):
    if universe == "zz800":
        codes = {}
        for u in ("hs300", "zz500"):
            rs = getattr(bs, QUERY[u])(date=asof)
            while (rs.error_code == "0") & rs.next():
                r = rs.get_row_data()
                codes[r[1]] = r[2]
        return codes
    rs = getattr(bs, QUERY[universe])(date=asof)
    codes = {}
    while (rs.error_code == "0") & rs.next():
        r = rs.get_row_data()
        codes[r[1]] = r[2]
    return codes


def fetch_recent(code, start, end):
    rs = bs.query_history_k_data_plus(
        code, "date,close,turn,amount", start_date=start, end_date=end,
        frequency="d", adjustflag="2")
    rows = []
    while (rs.error_code == "0") & rs.next():
        rows.append(rs.get_row_data())
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["date", "close", "turn", "amount"])
    df["date"] = pd.to_datetime(df["date"])
    for c in ("close", "turn", "amount"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.set_index("date")


def compute_holdings(universe="hs300", asof="2026-06-12", start="2024-06-01") -> dict:
    """抓当前成分最近行情 → 实时算因子 → 选前 TOP_N。需已 bs.login()。"""
    names = current_constituents(universe, asof)
    print(f"{UNAME[universe]} 当前成分 {len(names)} 只，抓最近行情 ...", flush=True)
    closes, turns, amts = {}, {}, {}
    for i, code in enumerate(names, 1):
        df = fetch_recent(code, start, asof)
        if df is None or df["close"].dropna().empty:
            continue
        closes[code] = df["close"]; turns[code] = df["turn"]; amts[code] = df["amount"]
        if i % 50 == 0:
            print(f"  {i}/{len(names)}", flush=True)
    close = pd.DataFrame(closes).sort_index()
    turn = pd.DataFrame(turns).reindex_like(close)
    amount = pd.DataFrame(amts).reindex_like(close)

    fp = factor_panels(close, turn, amount)
    t = close.index[-1]   # 最新交易日
    keys = SELECTED[universe]
    px = close.loc[t]
    elig = px.index[px.notna() & (px > 0)]
    allz = {k: zscore(fp[k].loc[t].reindex(elig)).clip(-Z_CLIP, Z_CLIP) for k in fp}
    score = sum(allz[k] for k in keys) / len(keys)
    score = score.dropna().sort_values(ascending=False)

    def row(code, all_factors=False):
        zk = list(fp) if all_factors else keys
        return {"code": code, "name": names.get(code, code),
                "close": round(float(close.loc[t, code]), 3),
                "score": round(float(score[code]), 3),
                "z": {k: round(float(allz[k].get(code, 0)), 2) for k in zk}}

    picks = [row(c) for c in score.index[:TOP_N]]
    all_scored = [row(c, all_factors=True) for c in score.index]  # 全表全因子，离线可复算任意组合
    return {
        "all_scored": all_scored,
        "universe": universe, "universe_cn": UNAME[universe],
        "inception_date": t.strftime("%Y-%m-%d"),
        "asof_query": asof, "factors_used": keys, "top_n": TOP_N,
        "weight_each": round(1 / TOP_N, 4),
        "n_constituents": len(names), "n_scored": int(len(score)),
        "holdings": picks,
    }


def main(universe="hs300", asof="2026-06-12", start="2024-06-01"):
    bs.login()
    try:
        entry = compute_holdings(universe, asof, start)
        tag = f"{universe}_{entry['inception_date'].replace('-','')}"
        all_scored = entry.pop("all_scored", [])
        with open(os.path.join(HERE, f"live_{tag}_full.json"), "w") as f:
            json.dump({"date": entry["inception_date"], "factors_used": entry["factors_used"],
                       "all_scored": all_scored}, f, ensure_ascii=False)
        out = os.path.join(HERE, f"live_{tag}.json")
        with open(out, "w") as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)
        print(f"建仓日 {entry['inception_date']}  选出 {len(entry['holdings'])} 只")
        print("前5:", [(p["name"], p["score"]) for p in entry["holdings"][:5]])
        print("写出", out)
    finally:
        bs.logout()


if __name__ == "__main__":
    uni = sys.argv[1] if len(sys.argv) > 1 else "hs300"
    main(universe=uni)
