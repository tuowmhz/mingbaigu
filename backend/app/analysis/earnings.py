"""财报拆解引擎：任意美股公司 → 三大报表 → 五个人话问题 → 一句话总结。

回答你真正关心的五个问题：
  1. 生意做多大了（收入规模与增速）
  2. 真能赚钱吗（每100块收入最后落袋几块）
  3. 利润是真是假（经营现金流 vs 账面利润）
  4. 会不会暴雷（现金 vs 债务）
  5. 对股东大方吗（回购+分红 vs 自由现金流）
银行等特殊行业缺少毛利等科目时自动跳过对应段落，不硬编。
"""
import re

import numpy as np
import yfinance as yf

from ..cache import cached
from ..config import NAME_MAP
from ..ml.features import tech_snapshot

CACHE_TTL = 86400  # 财报一天一变就够了


# —— 格式化工具 ——

def fmt_usd(v, currency="USD"):
    if v is None:
        return "-"
    unit = {"USD": "美元", "CNY": "元", "HKD": "港元"}.get(currency, f" {currency}")
    a = abs(v)
    if a >= 1e12:
        s = f"{v/1e12:.2f} 万亿{unit}"
    elif a >= 1e8:
        s = f"{v/1e8:,.0f} 亿{unit}"
    elif a >= 1e4:
        s = f"{v/1e4:,.0f} 万{unit}"
    else:
        s = f"{v:,.0f}{unit}"
    return s


def fmt_pct(v, signed=True, digits=1):
    if v is None:
        return "-"
    sign = "+" if (signed and v > 0) else ""
    return f"{sign}{v*100:.{digits}f}%"


# —— 报表取数工具 ——

def _row(df, *names):
    """按多个候选科目名取一行（不同公司科目名略有差异）。"""
    if df is None or getattr(df, "empty", True):
        return None
    for n in names:
        if n in df.index:
            s = df.loc[n].dropna()
            if not s.empty:
                return s
    return None


def _v(series, i=0):
    if series is None or len(series) <= i:
        return None
    return float(series.iloc[i])


def _yoy(series, i=0):
    a, b = _v(series, i), _v(series, i + 1)
    if a is None or b is None or b <= 0:
        return None  # 基数缺失或为负，同比无意义
    return a / b - 1


def _quarter_yoy(series):
    """季度同比：找 ~1 年前的同期季度。"""
    if series is None or len(series) < 2:
        return None
    latest_date, latest_val = series.index[0], float(series.iloc[0])
    for d, val in series.items():
        days = (latest_date - d).days
        if 300 <= days <= 430 and val and val > 0:
            return latest_val / float(val) - 1
    return None


# —— 技术面（人话版，只说"现在贵不贵、热不热"，不预测涨跌）——

def _technical_block(hist, ccy: str, n_plus: int, n_minus: int) -> list | None:
    if hist is None or hist.empty or len(hist) < 30:
        return None
    close = hist["Close"].dropna()
    if len(close) < 30:
        return None
    last = float(close.iloc[-1])
    hi, lo = float(close.max()), float(close.min())
    rng = hi - lo
    pos = (last - lo) / rng if rng > 0 else 0.5
    dist_high = last / hi - 1 if hi else 0.0
    sym = {"USD": "$", "CNY": "¥", "HKD": "HK$"}.get(ccy, "")
    snap = tech_snapshot(hist)
    rsi, mom = snap["rsi"], snap["momentum_20d"]
    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else np.nan

    lines = []
    tail = ("已经很接近一年最高点了。" if dist_high > -0.05
            else ("还趴在一年最低点附近。" if pos < 0.2 else ""))
    lines.append(
        f"现在股价 {sym}{last:.2f}，处在过去一年区间的 {pos*100:.0f}% 位置"
        f"（一年最高 {sym}{hi:.2f}、最低 {sym}{lo:.2f}）。{tail}")

    if not np.isnan(sma200):
        if last > sma50 and last > sma200:
            lines.append("股价站在 50 日和 200 日均线之上，中长期是上升趋势（俗称多头排列）。")
        elif last < sma50 and last < sma200:
            lines.append("股价跌破 50 日和 200 日均线，中长期是下降趋势（空头排列）——想抄底要小心接飞刀。")
        else:
            lines.append("股价在 50 日和 200 日均线之间来回，方向还不明朗（震荡整理）。")
    elif not np.isnan(sma50):
        up = last > sma50
        lines.append(f"股价{'站上' if up else '跌破'} 50 日均线，近期偏{'强' if up else '弱'}。")

    move = f"近一个月{'涨' if mom >= 0 else '跌'}了 {abs(mom)*100:.0f}%"
    if rsi >= 70:
        lines.append(f"{move}，短期有点过热（RSI {rsi:.0f}，超过 70 通常意味着买盘一拥而上、容易回调）。")
    elif rsi <= 30:
        lines.append(f"{move}，短期偏超卖（RSI {rsi:.0f}，低于 30 常是恐慌抛售、有时会有反弹）。")
    else:
        lines.append(f"{move}，冷热适中（RSI {rsi:.0f}，没有明显过热或超卖）。")

    good, weak = n_plus > n_minus, n_minus > n_plus
    near_high, near_low = dist_high > -0.05, pos < 0.25
    if good and near_high:
        syn = "💡 财报不错，但股价也已接近一年高位——好消息很可能已经反映在价格里。追高前先问自己：现在买，赌的是基本面，还是赌有人接盘？"
    elif good and near_low:
        syn = "💡 财报不错，股价却还在低位——要么市场没反应过来，要么有财报没体现的担忧（行业、官司、前景）。先想清楚'它为什么这么便宜'。"
    elif weak and near_high:
        syn = "💡 财报平淡甚至转弱，股价却在高位——这种价格靠的是'期待'不是'当下业绩'，一旦期待落空，回调会很快。"
    elif weak and near_low:
        syn = "💡 财报和股价都在低位——坏消息大概率已被市场定价；能不能反弹，取决于基本面会不会继续恶化。"
    elif near_high:
        syn = "💡 财报亮点隐忧参半，但股价已在一年高位——市场对它的期待并不低，好消息得够猛才撑得住现在的价格。"
    elif near_low:
        syn = "💡 财报亮点隐忧参半，股价却趴在一年低位——可能被错杀，也可能是市场先嗅到了风险。便宜不等于值得，先弄清是哪一种。"
    else:
        syn = "💡 把'财报好不好'和'股价贵不贵'分开看：好公司也可能买在贵的时候，差公司也可能已经跌过头。"
    lines.append(syn)
    lines.append("（技术面只说明'现在贵不贵、热不热'，不预测涨跌；和财报一起看，是为了别在好消息出尽时高位接盘。）")
    return lines


# —— 主引擎 ——

@cached(CACHE_TTL)
def deconstruct(ticker: str) -> dict | None:
    t = yf.Ticker(ticker)
    try:
        inc_a = t.income_stmt
        if inc_a is None or inc_a.empty:
            return None
        inc_q = t.quarterly_income_stmt
        bs = t.balance_sheet
        cf = t.cashflow
        info = t.info or {}
    except Exception:
        return None

    currency = info.get("financialCurrency", "USD")
    name = info.get("shortName") or info.get("longName") or ticker
    # 银行/金融机构的现金流量表受存贷款变动主导，OCF/FCF 指标不适用
    is_financial = info.get("sector") == "Financial Services"

    rev = _row(inc_a, "Total Revenue", "Operating Revenue")
    ni = _row(inc_a, "Net Income", "Net Income Common Stockholders")
    gp = _row(inc_a, "Gross Profit")
    op = _row(inc_a, "Operating Income", "Total Operating Income As Reported", "EBIT")
    rnd = _row(inc_a, "Research And Development")
    if rev is None or ni is None:
        return None

    # —— 年度表格（最多 4 年）——
    annual = []
    for i in range(min(4, len(rev))):
        r, n_ = _v(rev, i), _v(ni, i)
        annual.append({
            "year": str(rev.index[i].year),
            "revenue": r,
            "net_income": n_,
            "gross_margin": round(_v(gp, i) / r, 4) if (gp is not None and _v(gp, i) is not None and r) else None,
            "net_margin": round(n_ / r, 4) if (r and n_ is not None) else None,
        })

    sections = []
    pluses, minuses = [], []

    # 1. 生意做多大了
    growth = []
    r0, yoy0, yoy1 = _v(rev), _yoy(rev, 0), _yoy(rev, 1)
    fy = rev.index[0].year
    growth.append(f"最近一个财年（FY{fy}）收入 {fmt_usd(r0, currency)}，平均每天进账 {fmt_usd(r0/365, currency)}。")
    if yoy0 is not None:
        trend = ""
        if yoy1 is not None:
            if yoy0 < 0 <= yoy1:
                trend = f"，增长由正转负（上一年还是 {fmt_pct(yoy1)}）"
            elif yoy0 >= 0 > yoy1:
                trend = f"，成功扭转了上一年（{fmt_pct(yoy1)}）的下滑"
            elif yoy0 > yoy1 + 0.02:
                trend = f"，而且增速比上一年（{fmt_pct(yoy1)}）在加快"
            elif yoy0 < yoy1 - 0.02:
                trend = f"，但增速比上一年（{fmt_pct(yoy1)}）放缓了"
        growth.append(f"收入同比{'增长' if yoy0 >= 0 else '下滑'} {fmt_pct(abs(yoy0), signed=False)}{trend}。")
        if yoy0 > 0.10:
            pluses.append(f"收入增长 {fmt_pct(yoy0)}，生意在明显变大")
        elif yoy0 < -0.03:
            minuses.append(f"收入下滑 {fmt_pct(yoy0)}，生意在收缩")
    ni_yoy = _yoy(ni)
    if ni_yoy is not None:
        growth.append(f"净利润 {fmt_usd(_v(ni), currency)}，同比{'增长' if ni_yoy >= 0 else '下滑'} {fmt_pct(abs(ni_yoy), signed=False)}。")

    rev_q = _row(inc_q, "Total Revenue", "Operating Revenue")
    ni_q = _row(inc_q, "Net Income", "Net Income Common Stockholders")
    q_yoy = _quarter_yoy(rev_q)
    if rev_q is not None and q_yoy is not None:
        qd = rev_q.index[0].strftime("%Y-%m")
        line = f"最新季度（{qd}）收入 {fmt_usd(_v(rev_q), currency)}，同比 {fmt_pct(q_yoy)}"
        nq_yoy = _quarter_yoy(ni_q)
        if nq_yoy is not None:
            line += f"；净利润同比 {fmt_pct(nq_yoy)}"
        growth.append(line + "——季度数据比年报更能反映当下的方向。")
    sections.append({"key": "growth", "title": "📈 生意做多大了", "narrative": growth})

    # 2. 真能赚钱吗
    profit = []
    nm0 = annual[0]["net_margin"]
    gm0 = annual[0]["gross_margin"]
    if gm0 is not None and nm0 is not None:
        profit.append(
            f"每收 100 块钱：成本拿走 {100-gm0*100:.0f} 块，剩 {gm0*100:.0f} 块毛利；"
            f"再扣掉研发、销售、管理和税，最终落袋 {nm0*100:.0f} 块（净利率 {fmt_pct(nm0, signed=False)}）。"
        )
    elif nm0 is not None:
        profit.append(f"净利率 {fmt_pct(nm0, signed=False)}：每收 100 块最终落袋 {nm0*100:.0f} 块。")
    if len(annual) > 1 and nm0 is not None and annual[1]["net_margin"] is not None:
        diff = (nm0 - annual[1]["net_margin"]) * 100
        if abs(diff) >= 0.5:
            word = "扩张" if diff > 0 else "收窄"
            profit.append(f"净利率比上一年{word}了 {abs(diff):.1f} 个百分点——{'越来越赚钱' if diff > 0 else '赚钱越来越辛苦'}。")
            (pluses if diff > 0 else minuses).append(f"利润率在{word}（{diff:+.1f}pp）")
    roe = info.get("returnOnEquity")
    if roe:
        roe_txt = "很能打" if roe > 0.20 else ("中规中矩" if roe > 0.10 else "偏弱")
        profit.append(f"股东每投 100 块本钱，一年赚回 {roe*100:.0f} 块（ROE {fmt_pct(roe, signed=False)}）——{roe_txt}。")
    if rnd is not None and r0:
        profit.append(f"研发投入 {fmt_usd(_v(rnd), currency)}，占收入 {fmt_pct(_v(rnd)/r0, signed=False)}。")
    sections.append({"key": "profitability", "title": "💰 真能赚钱吗", "narrative": profit})

    # 3. 利润是真是假
    cashq = []
    ocf = _row(cf, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities")
    fcf = _row(cf, "Free Cash Flow")
    ocf0, ni0 = _v(ocf), _v(ni)
    fcf0 = _v(fcf)
    if is_financial:
        cashq.append(
            "银行/金融机构的现金流量表被存贷款和交易头寸的变动主导，"
            "「经营现金流 vs 利润」「自由现金流」这类指标对它们不适用——"
            "判断银行利润质量应看 ROE、净息差和监管资本充足率（见银行体检板块）。"
        )
    elif ocf0 is not None and ni0 and ni0 > 0:
        ratio = ocf0 / ni0
        if ratio >= 1.1:
            judge = "利润成色很足——赚到的是真金白银，不是纸面富贵"
            pluses.append("经营现金流超过账面利润，利润含金量高")
        elif ratio >= 0.8:
            judge = "现金流与利润基本匹配，正常水平"
        else:
            judge = "现金回款明显跟不上账面利润（可能压了应收账款/存货），这种利润要打个问号"
            minuses.append(f"经营现金流只有账面利润的 {ratio*100:.0f}%，利润含水分")
        cashq.append(f"账面每赚 1 块钱，实际收回现金 {ratio:.2f} 块。{judge}。")
    if not is_financial and fcf0 is not None:
        if fcf0 > 0:
            cashq.append(f"自由现金流 {fmt_usd(fcf0, currency)}——付完所有账单、买完设备后真正剩下的钱。")
        else:
            cashq.append(f"自由现金流为负（{fmt_usd(fcf0, currency)}）——花的比挣的多，靠融资或家底过日子。")
            minuses.append("自由现金流为负")
    sections.append({"key": "cash_quality", "title": "🔍 利润是真是假", "narrative": cashq})

    # 4. 会不会暴雷
    health = []
    cash = _row(bs, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")
    debt = _row(bs, "Total Debt")
    equity = _row(bs, "Stockholders Equity", "Common Stock Equity")
    cash0, debt0, eq0 = _v(cash), _v(debt), _v(equity)
    if cash0 is not None and debt0 is not None:
        net = cash0 - debt0
        if net >= 0:
            health.append(f"手里现金 {fmt_usd(cash0, currency)}，比总债务（{fmt_usd(debt0, currency)}）还多——净现金状态，财务上几乎没有暴雷风险。")
            pluses.append("净现金状态，财务极稳")
        else:
            line = f"现金 {fmt_usd(cash0, currency)} vs 总债务 {fmt_usd(debt0, currency)}，净负债 {fmt_usd(-net, currency)}"
            if eq0 and eq0 > 0:
                lev = -net / eq0
                if lev > 1.5:
                    line += f"，是股东权益的 {lev:.1f} 倍——杠杆相当高，利率环境恶化时要小心"
                    minuses.append(f"净负债是权益的 {lev:.1f} 倍，杠杆偏高")
                elif lev > 0.7:
                    line += f"，约为股东权益的 {lev:.1f} 倍——杠杆中等"
                else:
                    line += f"，仅为股东权益的 {lev:.1f} 倍——负债可控"
            health.append(line + "。")
    ca = _row(bs, "Current Assets")
    cl = _row(bs, "Current Liabilities")
    if _v(ca) and _v(cl):
        cr = _v(ca) / _v(cl)
        health.append(f"流动比率 {cr:.2f}：一年内要还的钱，手头短期资产能覆盖 {cr*100:.0f}%。")
    if not health:
        health.append("该公司资产负债表科目特殊（如金融机构），常规偿债指标不适用，请参考监管口径数据。")
    sections.append({"key": "balance_health", "title": "🛡️ 会不会暴雷", "narrative": health})

    # 5. 对股东大方吗
    reward = []
    buyback = _row(cf, "Repurchase Of Capital Stock")
    dividends = _row(cf, "Cash Dividends Paid", "Common Stock Dividend Paid")
    bb0 = abs(_v(buyback)) if _v(buyback) is not None else 0.0
    dv0 = abs(_v(dividends)) if _v(dividends) is not None else 0.0
    total_return = bb0 + dv0
    if total_return > 0:
        parts = []
        if bb0:
            parts.append(f"回购 {fmt_usd(bb0, currency)}")
        if dv0:
            parts.append(f"分红 {fmt_usd(dv0, currency)}")
        line = f"过去一个财年通过{' + '.join(parts)}，共还给股东 {fmt_usd(total_return, currency)}"
        if not is_financial and fcf0 and fcf0 > 0:
            pr = total_return / fcf0
            line += f"，相当于自由现金流的 {pr*100:.0f}%"
            if pr > 0.6:
                pluses.append("把大部分自由现金流还给了股东")
        reward.append(line + "。")
    else:
        reward.append("既不分红也不回购——赚的钱都留在公司里扩张（成长期公司常见做法）。")
    sections.append({"key": "shareholder_return", "title": "🎁 对股东大方吗", "narrative": reward})

    # 6. 股价现在在哪（一点点技术面，把"贵不贵·热不热"和财报放一起看）
    try:
        tech_lines = _technical_block(t.history(period="1y"),
                                      info.get("currency", currency),
                                      len(pluses), len(minuses))
        if tech_lines:
            sections.append({"key": "technical", "title": "🧭 股价现在在哪", "narrative": tech_lines})
    except Exception:
        pass

    # —— 一句话总结 ——
    if len(pluses) >= 3 and len(minuses) <= 1:
        summary = "这份财报整体相当健康：" + "；".join(pluses[:3]) + "。"
    elif len(minuses) >= 3 and len(pluses) <= 1:
        summary = "这份财报问题不少：" + "；".join(minuses[:3]) + "。买入前请三思。"
    elif pluses or minuses:
        summary = "亮点与隐忧并存——" + (f"亮点：{'；'.join(pluses[:2])}。" if pluses else "") + (f"隐忧：{'；'.join(minuses[:2])}。" if minuses else "")
    else:
        summary = "财报数据中性，没有特别突出的亮点或风险信号。"

    return {
        "ticker": ticker.upper(),
        "name": name,
        "name_cn": NAME_MAP.get(ticker.upper()),
        "sector": info.get("sector"),
        "market_cap": info.get("marketCap"),
        "currency": currency,
        # 市值/股价的计价货币（ADR 财报是人民币但市值是美元，两者要分开）
        "trade_currency": info.get("currency", currency),
        "fiscal_year": str(fy),
        "annual": annual,
        "sections": sections,
        "verdict": {"summary": summary, "pluses": pluses, "minuses": minuses},
        "source": "Yahoo Finance 财报数据（年报+季报）",
    }


# —— 公司名/代码解析 ——

_TICKER_RX = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_CN_CODE_RX = re.compile(r"^\d{6}(\.(SS|SZ))?$")


def _candidates(query: str) -> list[str]:
    q = query.strip()
    out = []
    # 观察列表中文名反查
    for tk, cn in NAME_MAP.items():
        if q == cn or q == tk:
            out.append(tk)
    qu = q.upper()
    # A股代码：6 位数字自动补市场后缀（6 开头→上海，0/3 开头→深圳）
    if _CN_CODE_RX.match(qu):
        if "." in qu:
            out.append(qu)
        else:
            first = qu + (".SS" if qu.startswith("6") else ".SZ")
            second = qu + (".SZ" if qu.startswith("6") else ".SS")
            out.extend([first, second])
    elif _TICKER_RX.match(qu) and qu not in out:
        out.append(qu)
    # Yahoo 搜索兜底（支持公司英文名等模糊输入）
    try:
        res = yf.Search(q, max_results=8)
        for item in res.quotes:
            sym = item.get("symbol", "")
            if item.get("quoteType") == "EQUITY" and sym and sym not in out:
                out.append(sym)
    except Exception:
        pass
    return out[:4]


def get_earnings(query: str) -> dict | None:
    """输入公司代码/名字，返回财报拆解；逐个候选尝试。"""
    for cand in _candidates(query):
        result = deconstruct(cand)
        if result:
            return result
    return None
