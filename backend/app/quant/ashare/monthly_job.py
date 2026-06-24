"""每月调仓任务（本地/定时跑一次）：
   1) 把上一期持仓按当期收盘价对账，算出这一个月的 realized 收益；
   2) 生成本期新持仓；
   3) 写一份新账本快照（含上期 realized + 本期持仓），随后 commit 进 git 公证。

用法： python monthly_job.py [hs300|zz500|zz800] [asof=YYYY-MM-DD]
建仓首期请改用： python live_holdings.py <uni> 再 python ledger.py ingest <文件>
"""
import sys

import baostock as bs

import ledger
from live_holdings import compute_holdings, fetch_recent
from ledger import _now


def _close_at(code: str, asof: str, start: str) -> float | None:
    df = fetch_recent(code, start, asof)
    if df is None or df["close"].dropna().empty:
        return None
    return float(df["close"].dropna().iloc[-1])


def mark_prev(prev: dict, asof: str) -> dict:
    """上一期持仓按 asof 收盘价对账：等权组合收益 + 基准收益。"""
    start = (prev["rebalance_date"][:4] + "-01-01")
    rets = []
    exits = {}
    for h in prev["holdings"]:
        px = _close_at(h["code"], asof, start)
        if px is None or not h.get("close"):
            continue
        exits[h["code"]] = round(px, 3)
        rets.append(px / h["close"] - 1)
    strat = sum(rets) / len(rets) if rets else 0.0
    b0 = _close_at(prev["benchmark"], prev["rebalance_date"], start)
    b1 = _close_at(prev["benchmark"], asof, start)
    bench = (b1 / b0 - 1) if (b0 and b1) else 0.0
    return {"prev_date": prev["rebalance_date"], "n_marked": len(rets),
            "strategy_ret": round(strat, 4), "bench_ret": round(bench, 4),
            "exit_prices": exits}


def run(universe: str, asof: str):
    bs.login()
    try:
        prev = ledger.latest_entry()
        prev_result = None
        if prev is not None:
            if prev["rebalance_date"] >= asof:
                print(f"账本已有 {prev['rebalance_date']} >= {asof}，跳过。"); return
            print(f"对账上期 {prev['rebalance_date']} 的 {len(prev['holdings'])} 只 ...")
            prev_result = mark_prev(prev, asof)
            print(f"  上期 strategy {prev_result['strategy_ret']:+.2%}  "
                  f"bench {prev_result['bench_ret']:+.2%}")
        h = compute_holdings(universe, asof)
        bench = "sh.000300" if universe in ("hs300", "zz800") else "sh.000905"
        entry = {
            "rebalance_date": h["inception_date"],
            "universe": universe, "universe_cn": h["universe_cn"],
            "benchmark": bench, "benchmark_cn": ledger.BENCH_CN[bench],
            "factors_used": h["factors_used"], "top_n": h["top_n"],
            "weight_each": h["weight_each"], "n_constituents": h["n_constituents"],
            "holdings": h["holdings"], "prev_result": prev_result,
            "generated_at": _now(), "note": "月度调仓快照（纸面跟踪）。",
        }
        path = ledger.save_entry(entry)
        print("写出账本:", path)
        print("记得 git add/commit 这份快照以完成公证。")
    finally:
        bs.logout()


if __name__ == "__main__":
    uni = sys.argv[1] if len(sys.argv) > 1 else "hs300"
    asof = sys.argv[2] if len(sys.argv) > 2 else None
    if not asof:
        print("请给 asof 日期，如 python monthly_job.py hs300 2026-07-31"); sys.exit(1)
    run(uni, asof)