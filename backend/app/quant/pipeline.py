"""量化管线总调度：数据 → 清洗 → 因子 → 回测 → 选股 → 组合优化 → JSON 落盘。

运行方式：
  .venv/bin/python -m app.quant.pipeline     # 命令行全量重算（约 2-4 分钟）
也可通过 API POST /api/quant/refresh 在后台线程重算。
"""
import json
import math
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .backtest import run_backtest
from .data import fetch_fundamentals, fetch_prices
from .factors import (FUNDAMENTAL_FACTORS, PRICE_FACTORS, composite_at,
                      fundamental_scores, price_factor_panel)
from .optimize import optimize_portfolio
from .universe import TOP100

ARTIFACT = Path(__file__).resolve().parents[2] / "data" / "quant_results.json"

DISCLAIMERS = [
    "回测只含价格因子：免费数据没有历史时点财报，财报因子强行回测会引入前视偏差，故只参与当前选股打分。",
    "股票池为今天的 SPY 前 100 权重股，回测历史存在幸存者偏差，结果系统性偏乐观。",
    "回测窗口仅约两年，统计意义有限；过去的因子表现不保证未来。",
    "本结果不构成投资建议。",
]

_lock = threading.Lock()
_status = {"running": False, "error": None}


def _json_clean(o):
    """NaN/Inf → None：json.dumps 写得进 NaN，但 FastAPI/浏览器都不认。"""
    if isinstance(o, dict):
        return {k: _json_clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_json_clean(v) for v in o]
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    return o


def build(progress=print) -> dict:
    t0 = time.time()
    progress("1/5 拉取 100 只股票 3 年日线 + SPY 基准…")
    closes, bench, dropped = fetch_prices()

    progress(f"2/5 数据清洗完成（剔除 {len(dropped)} 只: {dropped or '无'}），开始回测价格因子…")
    bt = run_backtest(closes, bench)

    progress("3/5 抓取 100 家公司财报关键指标…")
    fund = fetch_fundamentals(list(closes.columns))

    progress("4/5 计算综合得分与选股排名…")
    panel = price_factor_panel(closes)
    last_date = closes.index[-1]
    price_score = composite_at(panel, last_date)
    fscores = fundamental_scores(fund).reindex(price_score.index).fillna(0.0)
    # 当前综合分 = 价格因子(可回测的那部分) 50% + 财报因子 50%
    total = 0.5 * price_score + 0.5 * fscores.mean(axis=1)

    ranking = []
    for t in total.nlargest(20).index:
        f = fund.loc[t] if t in fund.index else pd.Series(dtype=object)
        ranking.append({
            "ticker": t,
            "name": str(f.get("name", t)),
            "sector": f.get("sector"),
            "score": round(float(total[t]), 3),
            "price_score": round(float(price_score[t]), 3),
            "value": round(float(fscores.loc[t, "value"]), 3),
            "quality": round(float(fscores.loc[t, "quality"]), 3),
            "growth": round(float(fscores.loc[t, "growth"]), 3),
            "price": round(float(closes[t].iloc[-1]), 2),
        })

    progress("5/5 对 Top 15 做最大夏普组合优化…")
    portfolio = optimize_portfolio(closes, [r["ticker"] for r in ranking[:15]])

    artifact = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "universe": "SPY 前 100 权重股",
            "n_universe": len(TOP100),
            "n_used": int(closes.shape[1]),
            "dropped": dropped,
            "price_start": closes.index[0].strftime("%Y-%m-%d"),
            "price_end": last_date.strftime("%Y-%m-%d"),
            "build_seconds": round(time.time() - t0, 1),
            "disclaimers": DISCLAIMERS,
        },
        "factor_glossary": {
            **{k: {"name_cn": v[0], "desc_cn": v[1], "backtestable": True}
               for k, v in PRICE_FACTORS.items()},
            **{k: {"name_cn": v[0], "desc_cn": v[1], "backtestable": False}
               for k, v in FUNDAMENTAL_FACTORS.items()},
        },
        "backtest": bt,
        "ranking": ranking,
        "portfolio": portfolio,
    }
    artifact = _json_clean(artifact)
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(artifact, ensure_ascii=False, indent=1, allow_nan=False))
    progress(f"完成，用时 {artifact['meta']['build_seconds']}s → {ARTIFACT}")
    return artifact


def load_artifact() -> dict | None:
    if ARTIFACT.exists():
        return json.loads(ARTIFACT.read_text())
    return None


def refresh_async() -> bool:
    """后台线程重算；已在跑则返回 False。"""
    if _status["running"]:
        return False

    def _run():
        with _lock:
            _status.update(running=True, error=None)
            try:
                build(progress=lambda *_: None)
            except Exception as e:  # noqa: BLE001
                _status["error"] = str(e)
            finally:
                _status["running"] = False

    threading.Thread(target=_run, daemon=True).start()
    return True


def build_status() -> dict:
    return dict(_status)


if __name__ == "__main__":
    build()
