"""A股数据抓取（baostock，免费，无需 token）。

抓取并缓存：
  1) 沪深300 / 中证500 的「历史时点成分股」（按月，每月底查当日成分）—— 抗幸存者偏差的关键
  2) 上述并集每只票的前复权日线（close/volume/amount/turn/pctChg）
  3) 基准指数日线（sh.000300 沪深300、sh.000905 中证500）

缓存：每只票一个 CSV，可断点续抓。成分表存 constituents.json。
诚实说明：使用「历史时点成分股」而非「今日成分股」回测，已显著降低（但未完全消除）
幸存者偏差——退市票的早期数据 baostock 仍可能缺失。
"""
import json
import os
import socket
import sys
import time

import baostock as bs
import pandas as pd

socket.setdefaulttimeout(30)  # 防止单次查询无限期阻塞

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
BARS = os.path.join(CACHE, "bars")
os.makedirs(BARS, exist_ok=True)

START = "2015-06-01"   # 比回测起点早半年，留足因子 warmup
END = "2025-06-13"
BT_START = "2016-01-01"  # 成分股按月采样的起点
FIELDS = "date,code,close,volume,amount,turn,pctChg"
BENCHES = {"sh.000300": "沪深300", "sh.000905": "中证500"}


def month_ends(start, end):
    return [x.strftime("%Y-%m-%d") for x in pd.date_range(start, end, freq="ME")]


def pit_constituents(query, dates, label=""):
    """每个月底的历史时点成分股代码列表。"""
    out = {}
    for j, dt in enumerate(dates, 1):
        rs = query(date=dt)
        codes = []
        while (rs.error_code == "0") & rs.next():
            codes.append(rs.get_row_data()[1])
        if codes:
            out[dt] = codes
        if j % 20 == 0 or j == len(dates):
            print(f"   {label} {j}/{len(dates)} 截面", flush=True)
    return out


def fetch_one(code, start=START, end=END):
    path = os.path.join(BARS, code.replace(".", "_") + ".csv")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return "cached"
    rs = bs.query_history_k_data_plus(code, FIELDS, start_date=start, end_date=end,
                                      frequency="d", adjustflag="2")  # 2=前复权
    rows = []
    while (rs.error_code == "0") & rs.next():
        rows.append(rs.get_row_data())
    if not rows:
        # 写空文件占位，避免反复重试退市/无数据票
        open(path, "w").close()
        return "empty"
    pd.DataFrame(rows, columns=FIELDS.split(",")).to_csv(path, index=False)
    return "ok"


def main():
    bs.login()
    try:
        mes = month_ends(BT_START, END)
        print(f"[1/3] 抓历史时点成分股，按月 {len(mes)} 个截面 ...", flush=True)
        hs300 = pit_constituents(bs.query_hs300_stocks, mes, "沪深300")
        zz500 = pit_constituents(bs.query_zz500_stocks, mes, "中证500")
        with open(os.path.join(CACHE, "constituents.json"), "w") as f:
            json.dump({"hs300": hs300, "zz500": zz500,
                       "bt_start": BT_START, "end": END}, f)
        union = set()
        for d in hs300.values():
            union |= set(d)
        for d in zz500.values():
            union |= set(d)
        union |= set(BENCHES)
        codes = sorted(union)
        print(f"[2/3] 并集 {len(codes)} 只（含基准），开始抓前复权日线 ...", flush=True)

        t0 = time.time()
        stats = {"ok": 0, "cached": 0, "empty": 0}
        for i, code in enumerate(codes, 1):
            try:
                r = fetch_one(code)
            except Exception as e:
                r = "empty"
                print(f"  !! {code}: {e}", flush=True)
            stats[r] = stats.get(r, 0) + 1
            if i % 100 == 0 or i == len(codes):
                el = time.time() - t0
                print(f"  {i}/{len(codes)}  ok={stats['ok']} cached={stats['cached']} "
                      f"empty={stats['empty']}  {el:.0f}s", flush=True)
        print(f"[3/3] 完成。{stats}", flush=True)
    finally:
        bs.logout()


if __name__ == "__main__":
    main()
