"""CogAlpha-mini：把 arXiv:2511.18850 (CogAlpha) 的核心闭环移植成最小可运行原型。

完整闭环：LLM 生成因子代码 → 多重质检 → IC/RankIC 打分 → 变异/杂交 → 优胜劣汰。

诚实声明（与本项目「诚实优先」一脉相承）：
- 这是研究原型，**不接入选股/产线**；它只在 IS 段做 IC 初筛，真正的裁决必须交回
  zoo.py 的 IS/OOS 硬切分 + adversarial.py 对抗验证 + 「OOS 只评一次」。
- LLM 因子挖掘本质是**过拟合制造机**：生成上千个、留最好的，正是制造假 alpha 的标准姿势。
  唯一解药就是本项目既有的样本外纪律，本脚本绝不单独下结论。
- exec LLM 代码有安全风险。这里只做了 builtins 白名单的**弱沙箱**，产线必须换真沙箱
  （子进程 + 资源限制 + 网络隔离）。
- 默认 --selftest 用合成数据离线跑，零依赖零花费；--online 才会经 ai_budget 电表调 Claude。

运行：
    cd backend && .venv/bin/python -m app.quant.cogalpha                 # 合成数据自测
    cd backend && .venv/bin/python -m app.quant.cogalpha --online \
        --tickers AAPL,MSFT,NVDA,...                                     # 真数据 + Claude
"""
from __future__ import annotations

import argparse
import re

import numpy as np
import pandas as pd

EPS = 1e-9


# ============ 市场数据容器（dates × tickers 的 OHLCV）============

class Market:
    """因子的唯一输入。每个字段是一张 index=日期、columns=股票 的 DataFrame。"""

    FIELDS = ("open", "high", "low", "close", "volume")

    def __init__(self, open, high, low, close, volume):  # noqa: A002
        self.open, self.high, self.low, self.close, self.volume = open, high, low, close, volume

    def corrupt_after(self, cut: int, seed: int = 0) -> "Market":
        """把第 cut 行之后的所有数据随机扰动——用于泄漏检测（见 quality_check）。"""
        rng = np.random.default_rng(seed)

        def c(df):
            d = df.copy()
            idx = d.index[cut + 1:]
            if len(idx):
                noise = rng.uniform(0.5, 1.5, size=(len(idx), d.shape[1]))
                d.loc[idx] = d.loc[idx].to_numpy() * noise
            return d

        return Market(c(self.open), c(self.high), c(self.low), c(self.close), c(self.volume))


# ============ 适应度评估：IC / RankIC / ICIR（CogAlpha 的 5-M 简化版）============

def forward_returns(close: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """前向 horizon 日收益——这是预测标签（用未来，天经地义），不是因子输入。"""
    return close.shift(-horizon) / close - 1.0


def ic_metrics(factor: pd.DataFrame, fwd: pd.DataFrame, min_names: int = 5) -> dict:
    """逐日横截面相关，再对时间聚合。返回 IC / RankIC / ICIR / RankICIR / 覆盖度。"""
    common = factor.index.intersection(fwd.index)
    ics, rics, covs = [], [], []
    for t in common:
        a, b = factor.loc[t], fwd.loc[t]
        m = a.notna() & b.notna()
        if int(m.sum()) < min_names:
            continue
        av, bv = a[m], b[m]
        if av.std() == 0 or bv.std() == 0:
            continue
        ics.append(float(av.corr(bv)))                       # Pearson IC（线性）
        rics.append(float(av.corr(bv, method="spearman")))   # RankIC（单调/抗离群）
        covs.append(float(m.mean()))
    if len(ics) < 6:
        return {"valid": False, "n_days": len(ics)}
    ic, ric = np.array(ics), np.array(rics)
    return {
        "valid": True,
        "ic": round(float(ic.mean()), 4),
        "rank_ic": round(float(ric.mean()), 4),
        "icir": round(float(ic.mean() / (ic.std() + EPS)), 3),       # IC 的「夏普」：稳不稳
        "rank_icir": round(float(ric.mean() / (ric.std() + EPS)), 3),
        "n_days": len(ics),
        "coverage": round(float(np.mean(covs)), 2),
    }


# ============ 多智能体质检官的最小版（编译 + 安全执行 + 数值/泄漏检测）============

_SAFE_BUILTINS = {  # 弱沙箱：只放行无害内置；屏蔽 __import__/open/eval/exec
    "abs": abs, "min": min, "max": max, "range": range, "len": len, "float": float,
    "int": int, "round": round, "sum": sum, "sorted": sorted, "enumerate": enumerate,
    "zip": zip, "map": map, "list": list, "dict": dict, "tuple": tuple, "set": set,
    "True": True, "False": False, "None": None,
}


def compile_factor(code: str):
    """把 LLM 给的 `def factor(mkt): ...` 代码字符串编译成可调用对象。"""
    if re.search(r"shift\(\s*-", code) or "iloc[-1]" in code:
        # 静态预筛：负向 shift / 取最后一行 = 几乎肯定有前视偏差，直接挡掉（动态检测会再兜底）
        raise ValueError("疑似未来函数（负 shift 或 iloc[-1]）")
    ns = {"pd": pd, "np": np, "__builtins__": _SAFE_BUILTINS}
    exec(code, ns)  # noqa: S102 — 弱沙箱，产线需替换为真沙箱
    fn = ns.get("factor")
    if not callable(fn):
        raise ValueError("代码里没有 factor(mkt) 函数")
    return fn


def quality_check(fn, mkt: Market) -> tuple[bool, str]:
    """跑通 + NaN 比例 + 每日有效取值 + 前视偏差，全过才算合格因子。"""
    try:
        out = fn(mkt)
    except Exception as e:  # noqa: BLE001
        return False, f"运行报错: {type(e).__name__}: {e}"
    if not isinstance(out, pd.DataFrame) or out.shape != mkt.close.shape:
        return False, "返回值不是与 close 同形状的 DataFrame"
    out = out.astype(float)

    nan_ratio = float(out.isna().to_numpy().mean())
    if nan_ratio > 0.30:                       # CogAlpha 同款：NaN>30% 直接丢弃
        return False, f"NaN 比例 {nan_ratio:.0%} 过高"
    distinct = out.iloc[-1].dropna().nunique()
    if distinct < 5:                           # 每天几乎没区分度 → 没法做横截面排序
        return False, f"截面区分度太低（distinct={distinct}）"

    # —— 前视偏差单元测试：扰动「未来」，过去的因子值必须纹丝不动 ——
    cut = int(len(out) * 0.7)
    after = fn(mkt.corrupt_after(cut)).astype(float)
    a = out.iloc[:cut + 1].to_numpy()
    b = after.iloc[:cut + 1].to_numpy()
    mask = ~(np.isnan(a) | np.isnan(b))
    if not np.allclose(a[mask], b[mask], rtol=1e-6, atol=1e-9):
        return False, "前视偏差：篡改未来数据改变了历史因子值（含全样本归一化泄漏）"
    return True, "ok"


# ============ LLM 生成（7 层方向 × 5 种引导，对齐 CogAlpha）============

DIRECTIONS = [  # CogAlpha 七层分工的浓缩版
    "市场结构与周期：长期趋势/市场阶段/周期切换",
    "极端风险与脆弱性：尾部风险/崩盘前兆",
    "价量动态：流动性/价量背离/成交结构",
    "价格-波动行为：趋势持续/短期反转/波动聚集",
    "多尺度复杂度：回撤几何/路径粗糙度",
    "稳定性与状态门控：随市场状态自适应开关信号",
    "几何与融合：K 线形态/多信号合成",
]
PARAPHRASE = ["原样", "自然改写", "研究性深化", "发散到相邻视角", "落成具体公式"]  # 多样化引导

_SYSTEM = (
    "你是量化因子研究员。只输出一个 Python 函数，签名严格为 def factor(mkt):。\n"
    "mkt 有 5 个 pandas DataFrame 字段：mkt.open / mkt.high / mkt.low / mkt.close / mkt.volume，"
    "行是日期、列是股票，已对齐。pd 和 np 已在作用域内，禁止 import。\n"
    "硬性纪律（违反即被判废）：\n"
    "1) 时点正确：t 日因子只能用 t 日及之前的数据。只许用 shift(正数)/rolling/expanding，"
    "严禁 shift(负数)、iloc[-1]、或任何对未来/全样本的引用（含整列 mean/std 做归一化）。\n"
    "2) 返回与 mkt.close 同形状的 DataFrame。\n"
    "3) 第一行写一句 docstring，用一句话讲清这个因子的经济学逻辑（为什么它该能预测收益）。\n"
    "只回代码块，不要解释。"
)


def _extract_code(text: str) -> str:
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.S)
    code = m.group(1) if m else text
    if "def factor" not in code:
        raise ValueError("LLM 未返回 factor() 函数")
    return code.strip()


class ClaudeLLM:
    """在线模式：走项目统一的 ai_budget.call_claude（带 $1/天保险丝）。"""

    def __init__(self, model: str = "claude-sonnet-4-6"):
        from ..ai_budget import call_claude  # 延迟导入，离线自测不触发
        self._call = call_claude
        self.model = model

    def _ask(self, user: str) -> str:
        out = self._call(self.model, _SYSTEM, user, max_tokens=900, timeout=60)
        if not out.get("text"):
            raise RuntimeError(out.get("error", "空响应"))
        return _extract_code(out["text"])

    def generate(self, direction: str, mode: str) -> str:
        return self._ask(f"探索方向：{direction}\n表达方式：{mode}。请据此设计一个全新的因子。")

    def mutate(self, code: str, metrics: dict) -> str:
        return self._ask(
            f"下面这个因子的 RankIC={metrics.get('rank_ic')}、ICIR={metrics.get('icir')}。"
            f"请对它做一处小幅改进（换算子/调窗口/加稳健化），保持经济学逻辑：\n```python\n{code}\n```")

    def crossover(self, code_a: str, code_b: str) -> str:
        return self._ask(
            "把下面两个因子各自最有效的部分杂交成一个新因子：\n"
            f"A:\n```python\n{code_a}\n```\nB:\n```python\n{code_b}\n```")


class OfflineLLM:
    """离线模式：返回一组写死的、时点正确的因子，用于零成本验证整条闭环。"""

    _SEEDS = [
        ('def factor(mkt):\n'
         '    """12-1 月动量：过去一年的强者倾向继续强（剔除最近一月避免反转噪声）。"""\n'
         '    c = mkt.close\n'
         '    return c.shift(21) / c.shift(252) - 1\n'),
        ('def factor(mkt):\n'
         '    """1 月反转：最近一个月涨多了短期倾向回调。"""\n'
         '    c = mkt.close\n'
         '    return -(c / c.shift(21) - 1)\n'),
        ('def factor(mkt):\n'
         '    """低波动：过去 63 日收益波动率取负，稳的股票风险调整后更好。"""\n'
         '    r = mkt.close.pct_change()\n'
         '    return -r.rolling(63).std()\n'),
        ('def factor(mkt):\n'
         '    """流动性冲击（CogAlpha 例式）：单位成交量推动的日内价升，越高越缺流动性。"""\n'
         '    return (mkt.high - mkt.close) / (mkt.volume + 1e-9)\n'),
        ('def factor(mkt):\n'
         '    """价量背离：价格创近月新高但量能未跟上，警示趋势虚弱。"""\n'
         '    c, v = mkt.close, mkt.volume\n'
         '    hi = c / c.rolling(21).max() - 1\n'
         '    vz = v / v.rolling(21).mean() - 1\n'
         '    return hi - vz\n'),
    ]

    def __init__(self):
        self._i = 0

    def generate(self, direction: str, mode: str) -> str:
        code = self._SEEDS[self._i % len(self._SEEDS)]
        self._i += 1
        return code

    def mutate(self, code: str, metrics: dict) -> str:
        # 把代码里第一个回看窗口换个值，模拟「变异」
        def bump(m):
            n = int(m.group(1))
            return str(max(2, int(n * 1.5)))
        return re.sub(r"(?<![\w.])(\d{2,3})(?=\))", bump, code, count=1)

    def crossover(self, code_a: str, code_b: str) -> str:
        return self._SEEDS[(self._i + 2) % len(self._SEEDS)]


# ============ 主循环：生成 → 质检 → 打分 → 变异 → 选择 ============

def _evaluate(code: str, mkt: Market, fwd: pd.DataFrame) -> dict | None:
    try:
        fn = compile_factor(code)
    except Exception as e:  # noqa: BLE001
        return {"code": code, "reason": f"编译挡回: {e}"}
    ok, why = quality_check(fn, mkt)
    if not ok:
        return {"code": code, "reason": f"质检挡回: {why}"}
    m = ic_metrics(fn(mkt), fwd)
    if not m.get("valid"):
        return {"code": code, "reason": "IC 评估天数不足"}
    doc = (re.search(r'"""(.+?)"""', code, re.S) or [None, code[:40]])[1].strip().split("\n")[0]
    return {"code": code, "doc": doc, **m}


def _good(c: dict | None) -> bool:
    return bool(c) and c.get("valid")


def run_loop(llm, mkt: Market, horizon: int = 5, n_init: int = 5,
             generations: int = 2, keep: int = 3, log=print) -> list[dict]:
    fwd = forward_returns(mkt.close, horizon)
    log(f"\n=== 第 0 代：七层方向 × 多样化引导，生成 {n_init} 个初始因子 ===")
    pool: list[dict] = []
    for i in range(n_init):
        d, mode = DIRECTIONS[i % len(DIRECTIONS)], PARAPHRASE[i % len(PARAPHRASE)]
        cand = _evaluate(llm.generate(d, mode), mkt, fwd)
        _report(cand, log)
        if _good(cand):
            pool.append(cand)

    pool.sort(key=lambda c: c["rank_ic"], reverse=True)
    for g in range(1, generations + 1):
        parents = pool[:keep]
        if not parents:
            log("没有合格父代，进化终止。")
            break
        log(f"\n=== 第 {g} 代：对 Top{len(parents)} 做变异 + 杂交（思维进化）===")
        children = [_evaluate(llm.mutate(p["code"], p), mkt, fwd) for p in parents]
        if len(parents) >= 2:
            children.append(_evaluate(llm.crossover(parents[0]["code"], parents[1]["code"]), mkt, fwd))
        for c in children:
            _report(c, log)
        # 选择：父代 + 合格子代，去重后按 RankIC 留强者
        merged, seen = [], set()
        for c in pool + [c for c in children if _good(c)]:
            key = c["code"].strip()
            if key not in seen:
                seen.add(key)
                merged.append(c)
        merged.sort(key=lambda c: c["rank_ic"], reverse=True)
        pool = merged[: keep * 2]
    return pool


def _report(c: dict | None, log):
    if c is None:
        return
    if c.get("valid"):
        log(f"  ✓ RankIC={c['rank_ic']:+.4f} IC={c['ic']:+.4f} ICIR={c['icir']:+.2f} "
            f"覆盖={c['coverage']:.0%}  | {c.get('doc', '')[:46]}")
    else:
        log(f"  ✗ {c.get('reason', '未知')}  | {c['code'].splitlines()[0][:46]}")


# ============ 合成数据自测（含一个故意泄漏的因子，验证护栏）============

def synth_market(n_days: int = 900, n_tickers: int = 40, seed: int = 7) -> Market:
    """带「横截面动量」结构的合成行情：每只股票有持续的 drift → 动量因子应得正 IC。"""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2018-01-01", periods=n_days)
    cols = [f"S{i:02d}" for i in range(n_tickers)]
    drift = rng.normal(0.0004, 0.0006, n_tickers)        # 每股恒定漂移 → 制造截面动量
    eps = rng.normal(0, 0.018, (n_days, n_tickers))
    rets = np.zeros((n_days, n_tickers))
    for t in range(1, n_days):
        rets[t] = drift + 0.06 * rets[t - 1] + eps[t]    # 叠一点 AR(1)
    close = pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=dates, columns=cols)
    high = close * (1 + rng.uniform(0, 0.02, close.shape))
    low = close * (1 - rng.uniform(0, 0.02, close.shape))
    open_ = close.shift(1).bfill()
    volume = pd.DataFrame(rng.lognormal(15, 0.5, close.shape), index=dates, columns=cols)
    return Market(open_, high, low, close, volume)


def _selftest(log=print):
    mkt = synth_market()
    log("【护栏自测】")
    leaky = ('def factor(mkt):\n'
             '    """故意偷看未来：用下一日收益。应当被前视偏差检测拦截。"""\n'
             '    return mkt.close.shift(-1) / mkt.close - 1\n')
    try:
        fn = compile_factor(leaky)
        ok, why = quality_check(fn, mkt)
        log(f"  泄漏因子 → {'未拦截（BUG！）' if ok else '已拦截 ✓ （' + why + '）'}")
    except Exception as e:  # noqa: BLE001
        log(f"  泄漏因子 → 已被静态预筛拦截 ✓ （{e}）")

    clean = ('def factor(mkt):\n'
             '    """干净的动量因子，应通过全部质检。"""\n'
             '    return mkt.close.shift(1) / mkt.close.shift(63) - 1\n')
    ok, why = quality_check(compile_factor(clean), mkt)
    log(f"  干净因子 → {'通过 ✓' if ok else '误杀（BUG！）: ' + why}")

    log("\n【完整闭环（离线 LLM + 合成数据）】")
    pool = run_loop(OfflineLLM(), mkt, horizon=5, n_init=5, generations=2, keep=3, log=log)
    log("\n=== 最终候选池（按 RankIC 排序）===")
    for c in pool:
        log(f"  RankIC={c['rank_ic']:+.4f}  ICIR={c['icir']:+.2f}  {c.get('doc', '')[:50]}")
    log("\n（合成数据自带截面动量，故动量类因子 IC 显著为正、反转为负——符合预期，"
        "证明评估器能区分信号方向。真实数据 IC 会小一个量级。）")


def _fetch_ohlcv(tickers: list[str], period: str = "5y") -> Market:
    import yfinance as yf  # 延迟导入
    raw = yf.download(tickers, period=period, auto_adjust=True, progress=False, group_by="ticker")
    fields = {f: {} for f in Market.FIELDS}
    for tk in tickers:
        try:
            sub = raw[tk]
        except KeyError:
            continue
        for f, col in zip(Market.FIELDS, ("Open", "High", "Low", "Close", "Volume")):
            fields[f][tk] = sub[col]
    dfs = {f: pd.DataFrame(fields[f]).dropna(how="all") for f in Market.FIELDS}
    idx = dfs["close"].index
    return Market(*[dfs[f].reindex(idx) for f in Market.FIELDS])


def main():
    ap = argparse.ArgumentParser(description="CogAlpha-mini：生成→质检→IC→变异 最小闭环")
    ap.add_argument("--online", action="store_true", help="用 Claude 真生成（走 ai_budget 电表）")
    ap.add_argument("--tickers", default="", help="逗号分隔股票代码（--online 真数据）")
    ap.add_argument("--period", default="5y")
    ap.add_argument("--horizon", type=int, default=5, help="预测前向收益的天数")
    ap.add_argument("--generations", type=int, default=2)
    ap.add_argument("--n-init", type=int, default=5)
    args = ap.parse_args()

    if not args.online:
        _selftest()
        return

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    if not tickers:
        raise SystemExit("--online 需要 --tickers AAPL,MSFT,...")
    print(f"拉取 {len(tickers)} 只股票 {args.period} OHLCV…")
    mkt = _fetch_ohlcv(tickers, args.period)
    pool = run_loop(ClaudeLLM(), mkt, horizon=args.horizon,
                    n_init=args.n_init, generations=args.generations)
    print("\n=== 最终候选池 ===")
    for c in pool:
        print(f"\nRankIC={c['rank_ic']:+.4f} ICIR={c['icir']:+.2f}\n{c['code']}")
    print("\n⚠️ 这些只是 IS 端 IC 初筛结果。下一步必须送进 zoo 的 IS/OOS 引擎做样本外裁决，"
          "再过 adversarial 对抗验证，OOS 只评一次。别用 IS 的 IC 排行榜挑因子。")


if __name__ == "__main__":
    main()
