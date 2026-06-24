"""公开成绩单：预测落盘 → GitHub 时间戳公证 → 到期自动对账。

信任设计的核心："别信我们，查我们。"
- 每天把观察列表的全部模型预测+裁判裁决写成快照（同一天内容固定，先写先赢）；
- 公开仓库的 GitHub Action 定时拉取快照并 commit——commit 时间戳是
  第三方公证，谁都能验证我们没有事后改历史；
- 满约半年（126 交易日）后自动对账：以"是否跑赢大盘(SPY)"为准，错的不删、亏的置顶；
- 永远和"随机猜（跑赢大盘的自然比例≈50%）"基准并排展示——模型没赢基准，页面自己会说。
"""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from .analysis.adversarial import run_adversarial
from .analysis.fear_greed import get_fear_greed
from .analysis.news_signal import analyze_news
from .analysis.risk import compute_risk
from .cache import cached
from .config import WATCHLIST
from .data.market import get_history, latest_quote
from .data.news import get_news
from .ml.features import tech_snapshot
from .ml.model import predict

SNAP_DIR = Path(__file__).resolve().parent.parent / "data" / "predictions"
HORIZON = 126  # 交易日 ≈ 半年，与新量化模型（预测6个月超额收益）口径一致
REPO = os.environ.get("TRACK_RECORD_REPO", "tuowmhz/mingbaigu-track-record")


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _snapshot_item(ticker: str, name: str) -> dict | None:
    df = get_history(ticker, period="2y")
    if df is None:
        return None
    as_of = df.index[-1].strftime("%Y-%m-%d")
    q = latest_quote(df)
    prediction = predict(ticker, as_of)
    tech = tech_snapshot(df)
    risk = compute_risk(df, ticker)
    analyzed = analyze_news(get_news(ticker), ticker)
    signal = analyzed["signal"] if analyzed else None
    adv = run_adversarial(tech, signal, None, prediction, risk, mood=get_fear_greed())
    judge = adv["judge"]
    bt = (prediction or {}).get("backtest") or {}
    return {
        "ticker": ticker,
        "name": name,
        "as_of": as_of,                      # 入场价对应的交易日
        "price": q["price"],
        "prob_up": (prediction or {}).get("prob_up"),
        "model_direction": (prediction or {}).get("direction"),
        "verdict": judge.get("verdict"),     # bullish / bearish / neutral
        "verdict_cn": judge.get("verdict_cn"),
        "confidence": judge.get("confidence"),
        "model_beat_baseline": (bt.get("edge") or 0) > 0,  # 诚实声明也入档
    }


def build_today_snapshot() -> dict:
    """当日快照：先写先赢——同一天不管被调用多少次，对外内容固定。

    优先级：本地档案 → 公证仓库（部署会清掉容器文件，已公证的版本是权威）
    → 都没有才新建。保证一天只存在一个版本。
    """
    date = _today_utc()
    path = SNAP_DIR / f"{date}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    notarized = _load_snapshot(date)  # 公证仓库兜底，命中会顺手回填本地
    if notarized:
        return notarized
    items = []
    for ticker, name, _cat in WATCHLIST:
        try:
            it = _snapshot_item(ticker, name)
            if it:
                items.append(it)
        except Exception:
            continue
    snap = {
        "date": date,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "horizon_days": HORIZON,
        "items": items,
        "methodology": (
            f"观察列表全量存档（无挑选）。裁决为偏多/偏空的预测在 {HORIZON} 个交易日后"
            "按收盘价对账；观望不计入命中率但同样存档。基准为'无脑看多'。"
        ),
        "notarization": f"本文件由 github.com/{REPO} 的定时任务拉取并 commit，"
                        "commit 时间戳即第三方公证，历史不可篡改。",
        "disclaimer": "由公开数据自动生成，不构成投资建议。",
    }
    if items:
        try:
            SNAP_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(snap, ensure_ascii=False))
        except Exception:
            pass
    return snap


# —— 历史档案：本地为主，GitHub 公证仓库兜底（部署会清掉容器内文件）——

def _local_archive_dates() -> list[str]:
    if not SNAP_DIR.exists():
        return []
    return sorted(p.stem for p in SNAP_DIR.glob("????-??-??.json"))


@cached(21600)
def _remote_archive_dates() -> list[str] | None:
    try:
        r = requests.get(
            f"https://api.github.com/repos/{REPO}/contents/predictions",
            timeout=15, headers={"Accept": "application/vnd.github+json"})
        if r.status_code != 200:
            return []
        return sorted(f["name"][:-5] for f in r.json()
                      if f["name"].endswith(".json"))
    except Exception:
        return []


def _load_snapshot(date: str) -> dict | None:
    path = SNAP_DIR / f"{date}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    try:  # 公证仓库兜底，顺手回填本地
        r = requests.get(
            f"https://raw.githubusercontent.com/{REPO}/main/predictions/{date}.json",
            timeout=15)
        if r.status_code == 200:
            snap = r.json()
            SNAP_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(snap, ensure_ascii=False))
            return snap
    except Exception:
        pass
    return None


def _outcome(item: dict) -> dict | None:
    """满 HORIZON 个交易日后对账——以"是否跑赢大盘(SPY)"为准；不足返回 None（待对账）。"""
    df = get_history(item["ticker"], period="2y")
    spy = get_history("SPY", period="2y")
    if df is None or spy is None:
        return None
    dates = [d.strftime("%Y-%m-%d") for d in df.index]
    try:
        pos = dates.index(item["as_of"])
    except ValueError:
        return None
    if pos + HORIZON >= len(dates):
        return None
    exit_date = dates[pos + HORIZON]
    entry = float(df["Close"].iloc[pos]); exit_price = float(df["Close"].iloc[pos + HORIZON])
    ret = exit_price / entry - 1 if entry else 0.0
    # 同期大盘收益（按相同日历日对齐）
    sdates = [d.strftime("%Y-%m-%d") for d in spy.index]
    if item["as_of"] not in sdates or exit_date not in sdates:
        return None
    s0, s1 = sdates.index(item["as_of"]), sdates.index(exit_date)
    mkt = float(spy["Close"].iloc[s1]) / float(spy["Close"].iloc[s0]) - 1
    excess = ret - mkt
    verdict = item.get("verdict")
    hit = None
    if verdict == "bullish":
        hit = excess > 0      # 看多 → 跑赢大盘才算对
    elif verdict == "bearish":
        hit = excess < 0      # 看空 → 跑输大盘才算对
    return {"exit_date": exit_date, "exit_price": round(exit_price, 2),
            "return_pct": round(ret * 100, 2), "market_pct": round(mkt * 100, 2),
            "excess_pct": round(excess * 100, 2), "hit": hit}


@cached(3600)
def build_track_record(days: int = 90) -> dict:
    dates = set(_local_archive_dates()) | set(_remote_archive_dates() or [])
    dates = sorted(dates, reverse=True)[:days]

    scored, pending = [], []
    for date in dates:
        snap = _load_snapshot(date)
        if not snap:
            continue
        for item in snap["items"]:
            row = {**item, "date": date}
            out = _outcome(item)
            if out is None:
                if item.get("verdict") in ("bullish", "bearish"):
                    pending.append(row)
                continue
            scored.append({**row, **out})

    judged = [r for r in scored if r["hit"] is not None]
    hits = sum(1 for r in judged if r["hit"])
    baseline_hits = sum(1 for r in scored if r.get("excess_pct", 0) > 0)  # 跑赢大盘的自然比例≈基准
    # 亏的置顶：按"相对大盘错得多狠"排序
    misses = sorted(
        (r for r in judged if not r["hit"]),
        key=lambda r: abs(r.get("excess_pct", 0)), reverse=True)

    return {
        "as_of": _today_utc(),
        "n_snapshots": len(dates),
        "stats": {
            "n_judged": len(judged),
            "hit_rate": round(hits / len(judged), 4) if judged else None,
            "baseline_hit_rate": round(baseline_hits / len(scored), 4) if scored else None,
            "n_pending": len(pending),
        },
        "worst_misses": misses[:5],
        "entries": sorted(judged, key=lambda r: r["date"], reverse=True)[:120],
        "pending": sorted(pending, key=lambda r: r["date"], reverse=True)[:60],
        "repo_url": f"https://github.com/{REPO}",
        "promise": "错的不删，亏的置顶。每条预测先公证、后对账——别信我们，查我们。",
        "methodology": (
            f"每个交易日把观察列表全部预测存档并由 GitHub commit 时间戳公证；"
            f"偏多/偏空裁决满 {HORIZON} 个交易日（约半年）后对账，以『是否跑赢大盘(SPY)』为准，"
            "观望只存档不计分。基准＝同期跑赢大盘的自然比例（≈50%，纯靠运气）——"
            "我们没赢基准时，这页会自己说。"
        ),
        "disclaimer": "由公开数据自动生成，不构成投资建议。",
    }
