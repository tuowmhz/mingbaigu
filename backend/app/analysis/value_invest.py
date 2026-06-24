"""价值投资面板：用格雷厄姆/巴菲特的眼光给股票做体检。

原则：价值投资不是"买便宜的"，是"用合理的价格买好生意"。
检查清单分三层：生意好不好（质量）→ 财务稳不稳（安全）→ 价格贵不贵（估值与安全边际）。
"""
import math

import yfinance as yf

from ..cache import cached
from .earnings import _row, _v, fmt_pct, fmt_usd

CACHE_TTL = 86400


def graham_number(eps: float | None, bvps: float | None) -> float | None:
    """格雷厄姆数：sqrt(22.5 × 每股收益 × 每股净资产)——老爷子认可的'合理价格'上限。"""
    if not eps or not bvps or eps <= 0 or bvps <= 0:
        return None
    return math.sqrt(22.5 * eps * bvps)


def _check(name, status, detail):
    return {"name": name, "status": status, "detail": detail}  # pass / fail / neutral


@cached(CACHE_TTL)
def value_analysis(ticker: str) -> dict | None:
    t = yf.Ticker(ticker)
    try:
        info = t.info or {}
        inc = t.income_stmt
        bs = t.balance_sheet
        cf = t.cashflow
    except Exception:
        return None
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not price or inc is None or inc.empty:
        return None
    is_financial = info.get("sector") == "Financial Services"
    currency = info.get("financialCurrency", "USD")

    checks = []

    # ── 生意质量 ──
    ni = _row(inc, "Net Income", "Net Income Common Stockholders")
    eq = _row(bs, "Stockholders Equity", "Common Stock Equity")
    roes = []
    if ni is not None and eq is not None:
        for i in range(min(len(ni), len(eq), 4)):
            n_, e_ = _v(ni, i), _v(eq, i)
            if n_ is not None and e_ and e_ > 0:
                roes.append(n_ / e_)
    if roes:
        ok = all(r > 0.12 for r in roes)
        avg = sum(roes) / len(roes)
        checks.append(_check(
            "ROE 持续 >12%", "pass" if ok else ("neutral" if avg > 0.08 else "fail"),
            f"近 {len(roes)} 个财年 ROE：{'、'.join(fmt_pct(r, signed=False) for r in roes)}。"
            + ("年年达标——生意有持续的赚钱能力，这是护城河最直接的证据。" if ok
               else "不够稳定——好年景赚钱不稀奇，差年景还能赚才是真本事。"),
        ))

    gp = _row(inc, "Gross Profit")
    rev = _row(inc, "Total Revenue", "Operating Revenue")
    if gp is not None and rev is not None and not is_financial:
        gms = [(_v(gp, i) / _v(rev, i)) for i in range(min(len(gp), len(rev), 4))
               if _v(rev, i)]
        if gms:
            spread = max(gms) - min(gms)
            stable = spread < 0.05 and gms[0] > 0.30
            checks.append(_check(
                "毛利率高且稳定", "pass" if stable else ("neutral" if gms[0] > 0.30 else "fail"),
                f"近 {len(gms)} 年毛利率 {fmt_pct(min(gms), signed=False)} ~ {fmt_pct(max(gms), signed=False)}。"
                + ("高且波动小——说明有定价权，不靠打价格战过日子。" if stable
                   else "毛利率不高或波动大——竞争激烈的信号，巴菲特管这叫'坐过山车的生意'。"),
            ))

    # ── 财务安全 ──
    debt = _v(_row(bs, "Total Debt"))
    cash = _v(_row(bs, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"))
    eq0 = _v(eq)
    if debt is not None and eq0 and eq0 > 0 and not is_financial:
        net_debt = debt - (cash or 0)
        ratio = net_debt / eq0
        checks.append(_check(
            "净负债/权益 <50%", "pass" if ratio < 0.5 else ("neutral" if ratio < 1.0 else "fail"),
            (f"净现金状态（现金多于债务 {fmt_usd(-net_debt, currency)}）——风暴来了它是买家不是卖家。" if net_debt < 0
             else f"净负债是股东权益的 {ratio*100:.0f}%。" + ("可控。" if ratio < 0.5 else "杠杆偏高——好生意不需要借这么多钱。")),
        ))

    ocf = _v(_row(cf, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities"))
    ni0 = _v(ni)
    if ocf is not None and ni0 and ni0 > 0 and not is_financial:
        conv = ocf / ni0
        checks.append(_check(
            "利润变现能力 >80%", "pass" if conv > 0.8 else "fail",
            f"每 1 元账面利润实际收回 {conv:.2f} 元现金。"
            + ("利润是真金白银。" if conv > 0.8 else "纸面利润多、现金少——价值投资者最忌讳的体质。"),
        ))

    # ── 估值与安全边际 ──
    pe = info.get("trailingPE")
    eps = info.get("trailingEps")
    bvps = info.get("bookValue")
    # 无风险锚：美股用美国十年期国债（实时），A股用中国十年期国债（约 2%，定期校准）
    tnx = None
    rf_name = "无风险国债"
    if currency == "CNY":
        tnx, rf_name = 0.020, "中国十年期国债（约 2%）"
    else:
        try:
            tnx_hist = yf.Ticker("^TNX").history(period="5d")
            if not tnx_hist.empty:
                tnx = float(tnx_hist["Close"].iloc[-1]) / 100
        except Exception:
            pass
    if pe and pe > 0 and tnx:
        ey = 1 / pe
        checks.append(_check(
            "盈利收益率 vs 国债", "pass" if ey > tnx * 1.5 else ("neutral" if ey > tnx else "fail"),
            f"买下整家公司相当于年回报 {fmt_pct(ey, signed=False)}，而{rf_name}给 {fmt_pct(tnx, signed=False)}。"
            + ("明显跑赢国债——承担股权风险有补偿。" if ey > tnx * 1.5
               else ("略高于国债——补偿很薄。" if ey > tnx else "还不如买国债——你在为'故事'付钱，不是为利润付钱。")),
        ))

    gn = graham_number(eps, bvps)
    graham = None
    if gn:
        margin = gn / price - 1
        graham = {"number": round(gn, 2), "price": price, "margin": round(margin, 4)}
        checks.append(_check(
            "格雷厄姆数安全边际", "pass" if margin > 0.2 else ("neutral" if margin > -0.2 else "fail"),
            f"格雷厄姆'合理价'≈{gn:.0f}，现价 {price:.0f}，"
            + (f"低估 {margin*100:.0f}%——老爷子会感兴趣。" if margin > 0.2
               else (f"在合理区间附近（{margin*100:+.0f}%）。" if margin > -0.2
                     else f"高出合理价 {-margin*100:.0f}%——按 1934 年的标尺这是危险区。"
                          "注意：成长股几乎都'超标'，格雷厄姆数对科技股偏苛刻。")),
        ))

    div = info.get("dividendYield")
    buyback = _v(_row(cf, "Repurchase Of Capital Stock"))
    mcap = info.get("marketCap")
    if mcap:
        # yfinance 的 dividendYield 是百分数形式（0.37 = 0.37%）；旧版本是小数形式，按量级判别
        div_frac = (div / 100 if div and div > 0.2 else (div or 0))
        total_yield = (abs(buyback) if buyback else 0) / mcap + div_frac
        checks.append(_check(
            "股东回报率（分红+回购）", "pass" if total_yield > 0.04 else ("neutral" if total_yield > 0.015 else "fail"),
            f"每年通过分红+回购返还市值的 {fmt_pct(total_yield, signed=False)}。"
            + ("真金白银对股东大方。" if total_yield > 0.04 else "回报偏低——钱要么在扩张，要么在账上睡觉。"),
        ))

    n_pass = sum(1 for c in checks if c["status"] == "pass")
    n_fail = sum(1 for c in checks if c["status"] == "fail")
    score = round(n_pass / len(checks) * 100) if checks else 0

    if score >= 70:
        verdict = ("符合价值投资体质：生意质量、财务安全和估值大体过关。"
                   "下一步该做的是定性研究——这生意十年后还在吗？护城河在变宽还是变窄？")
    elif score >= 40:
        verdict = ("半个价值股：部分指标达标。价值投资者会把它放进观察列表，"
                   "等价格给出更厚的安全边际，或等不达标的项目改善。")
    else:
        verdict = ("以传统价值投资标尺衡量不合格——但注意：这套标尺会系统性错过高成长公司"
                   "（亚马逊曾常年'不合格'）。它告诉你的不是'别买'，而是'你买的不是价值，是成长预期'。")

    return {
        "ticker": ticker.upper(),
        "score": score,
        "n_pass": n_pass, "n_fail": n_fail, "n_total": len(checks),
        "checks": checks,
        "graham": graham,
        "verdict": verdict,
        "is_financial": is_financial,
        "note": ("金融股已自动跳过现金流/杠杆类检查（口径不适用）。" if is_financial else None),
        "philosophy": "价值投资三问：生意好不好 → 财务稳不稳 → 价格贵不贵。顺序不能反——再便宜的烂生意也是烂生意。",
    }
