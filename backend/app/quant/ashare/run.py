"""跑全套 A 股低频多因子回测，产出 results.json + 控制台诚实小结。"""
import json
import os

import backtest_cn as bt

HERE = os.path.dirname(os.path.abspath(__file__))


def pct(x):
    return f"{x*100:.1f}%" if isinstance(x, (int, float)) else "—"


def main():
    out = {"universes": {}, "cost_sensitivity": {}}

    # 1) 三个股票池，基准成本 30bps 往返
    for uni in ["zz500", "hs300", "zz800"]:
        print(f"\n==== {uni} 回测中 ...", flush=True)
        try:
            r = bt.run_backtest(universe=uni, top_n=30, cost_roundtrip=0.003)
        except Exception as e:
            import traceback
            print(f"  !! {uni} 回测失败: {e}")
            traceback.print_exc()
            continue
        out["universes"][uni] = r
        s, b = r["stats"]["full"], r["stats"]["bench_full"]
        oos, boos = r["stats"]["oos"], r["stats"]["bench_oos"]
        print(f"  选用因子: {r['config']['selected_factors']}")
        print(f"  全样本   策略CAGR {pct(s['cagr'])}  基准 {pct(b['cagr'])}  "
              f"超额 {pct(s['cagr']-b['cagr'])}  夏普 {s['sharpe']}  回撤 {pct(s['max_drawdown'])}")
        print(f"  样本外   策略CAGR {pct(oos['cagr'])}  基准 {pct(boos['cagr'])}  "
              f"超额 {pct(oos['cagr']-boos['cagr'])}  夏普 {oos['sharpe']}")
        print(f"  月胜率(对基准) {pct(r['monthly_win_rate_vs_bench'])}  年换手~ {r['avg_turnover']*12:.1f}x")

    # 2) 成本敏感性（用中证500主池）
    print("\n==== 成本敏感性 (zz500) ...", flush=True)
    for c in [0.0015, 0.003, 0.005, 0.008]:
        r = bt.run_backtest(universe="zz500", top_n=30, cost_roundtrip=c)
        out["cost_sensitivity"][f"{int(c*1e4)}bps"] = {
            "full_cagr": r["stats"]["full"]["cagr"],
            "oos_cagr": r["stats"]["oos"]["cagr"],
            "bench_oos_cagr": r["stats"]["bench_oos"]["cagr"]}
        print(f"  {int(c*1e4):>2}bps往返: 全样本CAGR {pct(r['stats']['full']['cagr'])}  "
              f"样本外CAGR {pct(r['stats']['oos']['cagr'])}")

    with open(os.path.join(HERE, "results.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n已写出 {os.path.join(HERE, 'results.json')}")


if __name__ == "__main__":
    main()
