"""市场中性（对冲）回测：多头多因子组合 - 做空对应股指期货。

这才是接近你说的「量化套利」：把大盘涨跌对冲掉，只留纯超额(alpha)。
诚实地把 **股指期货基差成本（贴水）** 算进去——这是散户做对冲最容易忽略的隐性成本：
- IF(沪深300) 基差温和，年化成本约 0~3%；
- IC(中证500) 长期贴水重，年化成本历史上常达 6~12%，会吃掉大半超额。
门槛照说：股指期货 1 手名义市值数十万、需 50 万验资开通，散户多数做不了——
所以这版是「上限演示」，不是「人人可复制」。
"""
import json
import os

import numpy as np
import pandas as pd

import backtest_cn as bt

HERE = os.path.dirname(os.path.abspath(__file__))
# 各池子对冲所用期货的年化基差成本情景（保守—中性—乐观）
BASIS = {"hs300": [0.0, 0.02, 0.04], "zz800": [0.0, 0.03, 0.06],
         "zz500": [0.04, 0.08, 0.12]}


def _stats(rets: pd.Series, rf=0.02) -> dict:
    rets = rets.dropna()
    n_years = len(rets) / 12
    cum = float((1 + rets).prod())
    cagr = cum ** (1 / n_years) - 1 if n_years > 0 else 0
    vol = float(rets.std() * np.sqrt(12))
    curve = (1 + rets).cumprod()
    mdd = float((curve / curve.cummax() - 1).min())
    return {"cagr": round(cagr, 4), "vol": round(vol, 4),
            "sharpe": round((cagr - rf) / vol, 2) if vol > 0 else None,
            "max_drawdown": round(mdd, 4), "total": round(cum - 1, 4),
            "n_months": len(rets)}


def run(universe="hs300"):
    r = bt.run_backtest(universe=universe, top_n=30, cost_roundtrip=0.003)
    m = pd.DataFrame(r["monthly"])
    strat = m["ret"]            # 多头净收益（已扣交易成本）
    bench = m["bench_ret"]
    gross_excess = strat - bench  # 完全对冲后的毛超额（未扣基差）

    out = {"universe": universe, "universe_cn": r["config"].get("universe"),
           "long_only": bt._stats(strat),
           "hedged": {}, "n_months": len(m),
           "selected_factors": r["config"]["selected_factors"]}
    for basis in BASIS[universe]:
        net = gross_excess - basis / 12.0   # 每月摊基差成本
        out["hedged"][f"basis_{int(basis*100)}pct"] = _stats(net)
    return out


def main():
    res = {}
    for uni in ["hs300", "zz800", "zz500"]:
        res[uni] = run(uni)
        lo = res[uni]["long_only"]
        print(f"\n== {uni} ==  纯多头: CAGR {lo['cagr']*100:.1f}%  "
              f"波动 {lo['annual_vol']*100:.1f}%  回撤 {lo['max_drawdown']*100:.0f}%")
        for k, s in res[uni]["hedged"].items():
            print(f"   对冲({k}): CAGR {s['cagr']*100:.1f}%  波动 {s['vol']*100:.1f}%  "
                  f"夏普 {s['sharpe']}  回撤 {s['max_drawdown']*100:.0f}%")
    with open(os.path.join(HERE, "hedge_results.json"), "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("\n写出 hedge_results.json")


if __name__ == "__main__":
    main()
