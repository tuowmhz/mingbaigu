"""读 results.json，画净值曲线 PNG（策略 vs 基准，IS/OOS 分界）。"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = {"zz500": "中证500", "hs300": "沪深300", "zz800": "中证800"}


def main():
    with open(os.path.join(HERE, "results.json")) as f:
        res = json.load(f)
    try:
        plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS", "Heiti TC"]
        plt.rcParams["axes.unicode_minus"] = False
    except Exception:
        pass

    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=False)
    for ax, uni in zip(axes, ["zz500", "hs300", "zz800"]):
        r = res["universes"][uni]
        cur = pd.DataFrame(r["curve"])
        cur["date"] = pd.to_datetime(cur["date"])
        ax.plot(cur["date"], cur["strategy"], lw=1.8, color="#D85A30", label="策略(多因子)")
        ax.plot(cur["date"], cur["bench"], lw=1.4, color="#888780", label=f"基准{NAME[uni]}")
        ax.axvline(pd.Timestamp(r["config"]["is_end"]), color="#185FA5", ls="--", lw=1,
                   alpha=.7)
        ax.text(pd.Timestamp(r["config"]["is_end"]), ax.get_ylim()[1],
                " 样本外→", color="#185FA5", fontsize=9, va="top")
        s = r["stats"]["full"]
        ax.set_title(f"{NAME[uni]}池  全样本CAGR {s['cagr']*100:.1f}%  "
                     f"夏普{s['sharpe']}  回撤{s['max_drawdown']*100:.0f}%", fontsize=11)
        ax.legend(fontsize=9, loc="upper left")
        ax.grid(alpha=.25)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle("A股低频多因子策略 净值回测（前复权·时点成分股·扣30bps成本）", fontsize=13)
    fig.tight_layout()
    out = os.path.join(HERE, "equity_curves.png")
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print("saved", out)


if __name__ == "__main__":
    main()
