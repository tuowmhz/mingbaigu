"""tushare 增量补数：把成分股 + 前复权日线补到今天（baostock 网关宕机后的替代源）。

为什么这么写：
- 成分股：index_weight 的历史月度截面（沪深300=000300.SH / 中证500=000905.SH），
  带 trade_date，能还原「时点成分」，避免幸存者/前视偏差。
- 日线：daily(收盘/成交额/涨跌幅) + daily_basic(换手率)。
- 前复权：用 daily 的 pct_chg（已对除权除息）链式还原，接续既有缓存的最后一根 qfq 收盘，
  保证单只票序列内部连续（收益类因子对复权基准不敏感）。新票走 adj_factor 还原整段。
- 单位对齐：tushare amount 单位「千元」→ ×1000 变「元」(与 baostock 一致)；
  vol「手」→ ×100 变「股」；turnover_rate / pct_chg 均为 %。

token 从环境变量 TS_TOKEN 读，不写入任何文件。可重复运行（断点续抓，按最后日期增量）。
"""
import json
import os
import sys
import time

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
BARS = os.path.join(CACHE, "bars")
os.makedirs(BARS, exist_ok=True)

TOKEN = os.environ["TS_TOKEN"]
TODAY = os.environ.get("TS_TODAY", "20260617")
SINCE_MEMBER = os.environ.get("TS_SINCE", "2024-06-01")  # 只补「该日起进过池」的票（含 warmup）
LIMIT = int(os.environ.get("TS_LIMIT", "0"))             # >0 时只处理前 N 只，用于 dry-run
COLS = ["date", "code", "close", "volume", "amount", "turn", "pctChg"]
S = requests.Session()


def api(name, params, fields=""):
    for t in range(5):
        try:
            r = S.post("http://api.tushare.pro",
                       json={"api_name": name, "token": TOKEN,
                             "params": params, "fields": fields}, timeout=30)
            j = r.json()
            if j.get("code") == 0:
                d = j["data"]
                return pd.DataFrame(d["items"], columns=d["fields"])
            if t == 4:
                print(f"  ERR {name} code={j.get('code')} {str(j.get('msg'))[:50]}", flush=True)
        except Exception as e:
            if t == 4:
                print(f"  EXC {name} {repr(e)[:70]}", flush=True)
        time.sleep(0.5 * (t + 1))
    return None


def ts2bs(con):   # '600000.SH' -> 'sh.600000'
    code, ex = con.split(".")
    return ex.lower() + "." + code


def bs2ts(code):  # 'sh.000300' -> '000300.SH'
    ex, num = code.split(".")
    return num + "." + ex.upper()


def fmt(yyyymmdd):
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


def nextday(date_str):  # 'YYYY-MM-DD' -> 'YYYYMMDD'(次日)
    return (pd.Timestamp(date_str) + pd.Timedelta(days=1)).strftime("%Y%m%d")


def update_constituents():
    with open(os.path.join(CACHE, "constituents.json")) as f:
        cons = json.load(f)
    for key, idx in [("hs300", "000300.SH"), ("zz500", "000905.SH")]:
        df = api("index_weight", {"index_code": idx, "start_date": "20250601",
                                  "end_date": TODAY}, "con_code,trade_date")
        if df is None or df.empty:
            print(f"  成分 {key} 无返回", flush=True)
            continue
        for d, g in df.groupby("trade_date"):
            cons[key][fmt(d)] = sorted(ts2bs(c) for c in g["con_code"])
        print(f"  {key}: 快照{len(cons[key])}个 最新 {max(cons[key])}", flush=True)
    cons["end"] = fmt(TODAY)
    with open(os.path.join(CACHE, "constituents.json"), "w") as f:
        json.dump(cons, f)
    return cons


def recent_union(cons):
    u = set()
    for key in ("hs300", "zz500"):
        for k, v in cons[key].items():
            if k >= SINCE_MEMBER:
                u |= set(v)
    return sorted(u)


def read_cached(code):
    path = os.path.join(BARS, code.replace(".", "_") + ".csv")
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    df = pd.read_csv(path)
    return df if not df.empty else None


def write_csv(code, df):
    df.to_csv(os.path.join(BARS, code.replace(".", "_") + ".csv"), index=False)


def fetch_tail(con, start_ymd):
    d = api("daily", {"ts_code": con, "start_date": start_ymd, "end_date": TODAY},
            "trade_date,close,vol,amount,pct_chg")
    if d is None or d.empty:
        return None
    d = d.sort_values("trade_date")
    b = api("daily_basic", {"ts_code": con, "start_date": start_ymd, "end_date": TODAY},
            "trade_date,turnover_rate")
    if b is not None and not b.empty:
        d = d.merge(b, on="trade_date", how="left")
    else:
        d["turnover_rate"] = float("nan")
    return d


def tail_to_rows(code, tail, last_close):
    """用 pct_chg 链式还原 qfq 收盘，接在 last_close 之后。"""
    closes, c = [], float(last_close)
    for p in tail["pct_chg"].astype(float):
        c = c * (1 + p / 100.0)
        closes.append(round(c, 4))
    return pd.DataFrame({
        "date": [fmt(x) for x in tail["trade_date"]],
        "code": code,
        "close": closes,
        "volume": tail["vol"].astype(float) * 100,
        "amount": tail["amount"].astype(float) * 1000,
        "turn": tail["turnover_rate"].astype(float),
        "pctChg": tail["pct_chg"].astype(float),
    })[COLS]


def fetch_full(code, con):
    """新票：整段 daily + adj_factor 还原 qfq。"""
    d = api("daily", {"ts_code": con, "start_date": "20150601", "end_date": TODAY},
            "trade_date,close,vol,amount,pct_chg")
    if d is None or d.empty:
        return None
    af = api("adj_factor", {"ts_code": con, "start_date": "20150601", "end_date": TODAY},
             "trade_date,adj_factor")
    b = api("daily_basic", {"ts_code": con, "start_date": "20150601", "end_date": TODAY},
            "trade_date,turnover_rate")
    d = d.sort_values("trade_date")
    if af is not None and not af.empty:
        d = d.merge(af, on="trade_date", how="left")
        d["adj_factor"] = d["adj_factor"].astype(float).ffill().bfill()
        latest = d["adj_factor"].iloc[-1]
        qfq = d["close"].astype(float) * d["adj_factor"] / latest
    else:
        qfq = d["close"].astype(float)
    if b is not None and not b.empty:
        d = d.merge(b, on="trade_date", how="left")
    else:
        d["turnover_rate"] = float("nan")
    return pd.DataFrame({
        "date": [fmt(x) for x in d["trade_date"]],
        "code": code,
        "close": qfq.round(4).values,
        "volume": d["vol"].astype(float).values * 100,
        "amount": d["amount"].astype(float).values * 1000,
        "turn": d["turnover_rate"].astype(float).values,
        "pctChg": d["pct_chg"].astype(float).values,
    })[COLS]


def update_bench():
    for bs, ts in [("sh.000300", "000300.SH"), ("sh.000905", "000905.SH")]:
        cached = read_cached(bs)
        start = nextday(cached["date"].iloc[-1]) if cached is not None else "20150601"
        if start > TODAY:
            continue
        idx = api("index_daily", {"ts_code": ts, "start_date": start, "end_date": TODAY},
                  "trade_date,close,vol,amount,pct_chg")
        if idx is None or idx.empty:
            print(f"  基准 {bs} 无新数据", flush=True)
            continue
        idx = idx.sort_values("trade_date")
        new = pd.DataFrame({
            "date": [fmt(x) for x in idx["trade_date"]], "code": bs,
            "close": idx["close"].astype(float), "volume": idx["vol"].astype(float),
            "amount": idx["amount"].astype(float) * 1000, "turn": float("nan"),
            "pctChg": idx["pct_chg"].astype(float)})[COLS]
        out = pd.concat([cached, new], ignore_index=True) if cached is not None else new
        write_csv(bs, out)
        print(f"  基准 {bs}: +{len(new)} 行 -> 末 {out['date'].iloc[-1]}", flush=True)


def main():
    print("[1/3] 更新成分股 ...", flush=True)
    cons = update_constituents()
    print("[2/3] 更新基准指数 ...", flush=True)
    update_bench()
    codes = recent_union(cons)
    if LIMIT:
        codes = codes[:LIMIT]
    print(f"[3/3] 补 {len(codes)} 只成分股日线（SINCE {SINCE_MEMBER}）...", flush=True)
    t0 = time.time()
    stat = {"tail": 0, "full": 0, "skip": 0, "fail": 0}
    for i, code in enumerate(codes, 1):
        con = bs2ts(code)
        cached = read_cached(code)
        try:
            if cached is None:
                rows = fetch_full(code, con)
                if rows is None:
                    stat["fail"] += 1
                else:
                    write_csv(code, rows)
                    stat["full"] += 1
            else:
                start = nextday(cached["date"].iloc[-1])
                if start > TODAY:
                    stat["skip"] += 1
                else:
                    tail = fetch_tail(con, start)
                    if tail is None or tail.empty:
                        stat["skip"] += 1
                    else:
                        new = tail_to_rows(code, tail, cached["close"].iloc[-1])
                        write_csv(code, pd.concat([cached, new], ignore_index=True))
                        stat["tail"] += 1
        except Exception as e:
            stat["fail"] += 1
            print(f"  !! {code}: {repr(e)[:70]}", flush=True)
        if i % 100 == 0 or i == len(codes):
            print(f"  {i}/{len(codes)} {stat} {time.time()-t0:.0f}s", flush=True)
    print(f"完成 {stat}", flush=True)


if __name__ == "__main__":
    main()
