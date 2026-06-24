"""A股低频策略 · 纸面跟踪账本。

诚实设计（沿用本项目成绩单哲学：别信我们，查我们）：
- 每月一份组合快照（持仓 + 入场价），存成 backend/data/ashare_strategy/<date>.json，
  commit 进 git——commit 时间戳即第三方公证，事后改不了历史；
- 每月调仓时顺手把上一期持仓按当期价对账，realized 收益写进账本，服务器只读不算；
- 自建仓日起的净值曲线与沪深300并排展示；真金白银未投入，是纸面跟踪。
"""
import calendar
import json
import os
from datetime import datetime, timezone
from pathlib import Path

LEDGER_DIR = Path(__file__).resolve().parents[3] / "data" / "ashare_strategy"
# 镜像内置种子（部署时打进非卷路径，避开 /app/data 持久卷的遮盖）。
# 服务器只读账本：读「卷 ∪ 种子」并集；本地月度任务写 LEDGER_DIR 并 commit。
SEED_DIR = Path(__file__).resolve().parent / "_seed_ledger"
REPO = os.environ.get("TRACK_RECORD_REPO", "tuowmhz/mingbaigu-track-record")
BENCH_CN = {"sh.000300": "沪深300指数", "sh.000905": "中证500指数"}
FACTOR_CN = {"low_turnover": "低换手", "low_vol": "低波动", "mom_12_1": "12-1动量",
             "reversal_1m": "1月反转", "reversal_3m": "3月反转", "illiq": "非流动性"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _next_rebalance(current: str) -> str:
    """下次调仓 = 当前持仓日所在月的下一个月最后一天（月度调仓节奏）。"""
    y, m, _ = (int(x) for x in current.split("-"))
    y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"


def save_entry(entry: dict) -> Path:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    path = LEDGER_DIR / f"{entry['rebalance_date']}.json"
    path.write_text(json.dumps(entry, ensure_ascii=False, indent=2))
    return path


def list_dates() -> list[str]:
    dirs = [d for d in (LEDGER_DIR, SEED_DIR) if d.exists()]
    return sorted({p.stem for d in dirs for p in d.glob("????-??-??.json")})


def load_entry(date: str) -> dict | None:
    for d in (LEDGER_DIR, SEED_DIR):  # 卷优先，种子兜底
        path = d / f"{date}.json"
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                continue
    return None


def latest_entry() -> dict | None:
    ds = list_dates()
    return load_entry(ds[-1]) if ds else None


def ingest_inception(holdings_json_path: str) -> Path:
    """把 live_holdings.py 生成的持仓文件登记为建仓日（第0期）账本。"""
    h = json.loads(Path(holdings_json_path).read_text())
    bench = "sh.000300" if h["universe"] in ("hs300", "zz800") else "sh.000905"
    entry = {
        "rebalance_date": h["inception_date"],
        "universe": h["universe"], "universe_cn": h["universe_cn"],
        "benchmark": bench, "benchmark_cn": BENCH_CN[bench],
        "factors_used": h["factors_used"], "top_n": h["top_n"],
        "weight_each": h["weight_each"], "n_constituents": h["n_constituents"],
        "holdings": h["holdings"], "prev_result": None,
        "generated_at": _now(),
        "note": "建仓日（纸面跟踪起点，未投入真金白银）。",
    }
    return save_entry(entry)


def build_track_record() -> dict:
    dates = list_dates()
    if not dates:
        return {"status": "empty", "message": "实验尚未建仓。"}
    entries = [load_entry(d) for d in dates]
    head = entries[0]
    last = entries[-1]

    # 净值链：每期 prev_result 给出上一持仓的 realized 收益
    curve = [{"date": head["rebalance_date"], "strategy": 1.0, "bench": 1.0}]
    monthly = []
    s, b = 1.0, 1.0
    for e in entries[1:]:
        pr = e.get("prev_result") or {}
        sr = pr.get("strategy_ret"); br = pr.get("bench_ret")
        if sr is None:
            continue
        s *= (1 + sr); b *= (1 + br)
        curve.append({"date": e["rebalance_date"], "strategy": round(s, 4),
                      "bench": round(b, 4)})
        monthly.append({"date": e["rebalance_date"], "strategy_ret": round(sr, 4),
                        "bench_ret": round(br, 4), "excess": round(sr - br, 4)})

    n = len(monthly)
    total_s = s - 1
    total_b = b - 1
    stats = {"n_months_live": n, "total_strategy": round(total_s, 4),
             "total_bench": round(total_b, 4), "total_excess": round(total_s - total_b, 4),
             "annualized": None, "max_drawdown": None, "monthly_win_rate": None}
    if n >= 1:
        wins = sum(1 for m in monthly if m["strategy_ret"] > m["bench_ret"])
        stats["monthly_win_rate"] = round(wins / n, 3)
        peak, mdd = 1.0, 0.0
        for c in curve:
            peak = max(peak, c["strategy"])
            mdd = min(mdd, c["strategy"] / peak - 1)
        stats["max_drawdown"] = round(mdd, 4)
    if n >= 6:  # 不足半年不年化，免得用小样本骗自己
        stats["annualized"] = round((1 + total_s) ** (12 / n) - 1, 4)

    return {
        "status": "live",
        "strategy_name": "低波蓝筹 · A股低频多因子",
        "universe_cn": head["universe_cn"], "benchmark_cn": head["benchmark_cn"],
        "inception_date": head["rebalance_date"],
        "rebalance": "每月", "is_paper": True,
        "factors_used_cn": [FACTOR_CN.get(k, k) for k in head["factors_used"]],
        "current_holdings": last["holdings"],
        "current_as_of": last["rebalance_date"],
        "next_rebalance": _next_rebalance(last["rebalance_date"]),
        "curve": curve, "monthly": monthly, "stats": stats,
        "repo_url": f"https://github.com/{REPO}",
        "promise": "每月持仓快照先 git 公证、后对账——纸面跟踪，未投真金。别信我们，查我们。",
        "disclaimer": ("历史回测(低换手+低波动两因子)：2016年以来全样本年化约7%、近三年样本外约14%；"
                       "均不代表未来，实盘还要打折。年化20%是目标不是承诺。"
                       "本页为纸面跟踪记录，由公开数据自动生成，不构成投资建议。"),
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "ingest" and len(sys.argv) > 2:
        print("登记建仓:", ingest_inception(sys.argv[2]))
    else:
        print(json.dumps(build_track_record(), ensure_ascii=False, indent=2))
