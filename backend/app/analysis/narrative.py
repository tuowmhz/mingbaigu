"""叙事验证器：把一条 KOL/博主的荐股叙事，过一遍公开数据，输出一张可被证伪的核验卡。

移植自独立引擎 ThesisChecker，复用明白股现成基建：
  - ai_budget.call_claude（预算电表 + $1/天熔断，所有 AI 调用唯一入口）
  - transmission._MCPClient / _token（Tushare MCP 取真实财报/估值，绕过 10-IP 绑定）
  - sectors.get_sectors（⑦产业链图谱接地）

三段式（把"拆解"和"裁决"分开，是这个产品诚实的关键）：
  A. extract  —— LLM 只拆解+分类(事实/预测/观点)，绝不判真假；
  B. data     —— 代码去 Tushare 拉真实数据(确定性，不经过 LLM)；
  C. assemble —— LLM 在"只能用我给的证据"约束下裁决，拿不到证据只能标"无法验证"；
  D. verify   —— 可选：多个视角各异的"魔鬼代言人"并行投票，过半推翻才降级。

仅 A股。不喊单、不给买卖/仓位/目标价。
"""
import concurrent.futures
import datetime
import json
import os
import re

import pandas as pd

from ..ai_budget import call_claude as _budget_call
from ..cache import cached
from .sectors import get_sectors
from .transmission import _MCPClient, _token

MODEL = os.environ.get("CLAUDE_ANALYST_MODEL", "claude-sonnet-4-6")


def enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _call(system: str, user: str, max_tokens: int, timeout: int) -> dict:
    return _budget_call(MODEL, system, user, max_tokens=max_tokens, timeout=timeout)


def _json(text: str):
    if not text:
        return None
    m = re.search(r"\{.*\}|\[.*\]", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


# ───────────────────────── 宪法（所有阶段共享的诚实铁律）─────────────────────────
CONSTITUTION = """\
你为「股票叙事验证器」工作。用户给你一段 KOL/博主的荐股叙事 + 一个股票代码，
你不是帮他证明这条叙事对，而是逼它接受公开数据的检验，并让读者看清两面、知道怎么验证自己错没错。

铁律（违反任何一条都比不输出更糟，因为这会变成信誉与法律负债）：
1) 事实/预测/观点必须分清：
   - 事实型（如『上季营收增长30%』『毛利率45%』）→ 可被公开数据核对；
   - 预测型（如『还能涨一倍』『需求无止境』）→ 永远不能判定真/假，只能拆出『要让它成立必须满足什么』；
   - 观点型（如『护城河很深』）→ 给反方视角，不站队。
2) 接地优先：任何带『证实/证伪』标签的结论，必须挂一条我提供给你的真实证据（evidence）。
   我没给你证据的事实主张，一律只能标『无法验证』，绝不靠你的记忆替它表态——你的训练数据会过期、会幻觉。
3) ticker / 公司名 / 具体财务数字，只能用我在输入里提供的；没有的绝不编造，宁可留空或写 null。
4) 多空两面都要给。若数据显示这条叙事其实是市场共识/已拥挤/传导方向相反，必须直说，不许顺着用户。
5) 绝不输出买卖建议、仓位、目标价、涨跌幅承诺。涉及『是否 price in』只描述当前估值隐含了什么预期、
   以及『要让这叙事成立估值/盈利得走到哪』，不给点位。
6) 结尾 caveat：基于公开数据的叙事核验，非涨跌预测，不构成投资建议。
7) 措辞精炼、口语化人话，不堆术语。只输出我要求的 JSON，不要任何额外文字、不要 markdown 代码围栏。
"""

# —— A. 拆解：只拆不判 ——
_EXTRACT_SYS = CONSTITUTION + """
任务【拆解】：把这段叙事拆成结构化、可被逐条检验的论点。此步你**只拆解和分类，绝不判断真假**。
对每条 claim 给出『要验证它需要哪个公开数据』(what_to_check)，把真假留给后面的接地裁决。
只输出一个 JSON，schema：
{
 "summary": "中立复述这条观点在讲什么(≤60字，不站队)",
 "core_thesis": "它真正押的那一个核心赌注(一句话)",
 "direction": "看多|看空|中性",
 "horizon": "时间维度(如 1-2年/一个季度/不明确)",
 "claims": [
   {"id":"c1","text":"原叙事里的一个原子主张(≤40字)",
    "type":"事实|预测|观点",
    "checkable": true,
    "what_to_check":"要核验它需要看的公开数据(如『近4季营收同比』『当前PE分位』)；预测/观点写null"}
 ]
}
claims 控制在 4-8 条，抓最承重的，别把每句话都拆。"""

# —— C. 裁决+组卡：只能用提供的证据 ——
_ASSEMBLE_SYS = CONSTITUTION + """
任务【裁决+组卡】：我会给你①拆解结果 ②一份真实证据包(Tushare财报/估值，含截止期) ③可选的产业链图谱。
基于证据给每条 claim 定性，并产出完整核验卡。
证据包可能含多类，按主张类型选对应证据接地：
  - financials：毛利率/ROE/营收同比/净利同比/资产负债率；
  - valuation：PE/PB 及其 5 年历史分位。
裁决铁律：status 只能是 [证实, 部分证实, 证伪, 无法验证, 预测(不可证伪), 观点]。
  - 事实型：证据包里有支持/反驳的数据才可标 证实/部分证实/证伪，并在 evidence 写清用了哪个数(带数值与期)；
    证据包里没有对应数据 → 必须标『无法验证』，basis 写『公开财报/估值数据中无对应项』，不许用记忆补。
  - 预测型 → status『预测(不可证伪)』，basis 写『要让它成立必须满足什么』；
  - 观点型 → status『观点』，basis 给一句反方视角。
只输出一个 JSON，schema：
{
 "headline":"一句话中立结论(≤30字，可上分享图，不喊单)",
 "verdicts":[{"id":"c1","type":"事实|预测|观点","status":"…","basis":"依据/反方/触发条件(≤45字)","evidence":"用到的真实数值与期，无则null"}],
 "sources":["用到的数据来源(从证据包 sources 抄，附截止期)"],
 "financial_check":{"verdict":"财报与叙事是否吻合(一句话)","points":["关键财务事实(必须来自证据包数值)…2-4条"]},
 "valuation_priced_in":{"read":"当前估值隐含了什么预期(用PE/PB分位说，不给点位)","needed":"要让这条叙事成立，盈利/估值大致得走到哪(定性)"},
 "supply_chain":{"note":"若提供了产业链图谱(matched=true)：必须基于它的真实环节/卡点/同环节玩家来写，note 里点明链名与本标的所处环节(上中下游)；未提供或未匹配则明说『未接产业链图谱，以下为粗略说明』","links":["环节→关系(尽量挂图谱里的卡点/玩家)…2-4条"]},
 "bull":["看多证据(尽量挂数据)…3条"],
 "bear":["看空/反方(尽量挂数据，含『其实是共识/已拥挤』之类)…3条"],
 "disconfirmers":["可跟踪的关键反证/领先指标…3条"],
 "falsification":"一条证伪触发：若X没发生/反向就该认错重估",
 "caveat":"基于公开数据的叙事核验，非涨跌预测，不构成投资建议"
}"""

# —— D. 对抗质检视角 ——
_CHECKABLE = {"证实", "部分证实", "证伪"}
_CONS = {"无法验证": 3, "部分证实": 2, "证实": 1, "证伪": 1}
_LENSES = [
    "视角A·数据充分性：证据是否真的足够支撑结论，还是样本太少、拿个别季度当趋势、以偏概全。",
    "视角B·口径与时点：是否用错指标（累计值当单季、毛利率当净利率、TTM当单期）、时点错配（拿旧财报对当下叙事）。",
    "视角C·因果与共识：是否混淆相关与因果、忽略了这其实已是市场共识/已被 price in、把行业beta当公司alpha。",
]
_VERIFY_SYS = CONSTITUTION + """
任务【裁决质检·魔鬼代言人】：下面是若干『对某主张的裁决 + 所用真实证据 + 证据包全文』。
请只从你被指定的视角挑刺。默认怀疑：只要从这个视角看证据不足以稳稳支撑，就判 upheld=false，
并给更稳妥的 suggested_status（证实→部分证实/无法验证；证伪→部分证实/无法验证）。证据确实充分才 upheld=true。
只输出一个 JSON 数组，逐条对应：
[{"id":"c1","upheld":true,"suggested_status":"维持或更稳妥状态","challenge":"≤40字质疑；upheld=true写『证据充分』"}]"""


# ───────────────────────── ticker / 数值 ─────────────────────────
def normalize_ticker(t: str) -> str:
    """600519 → 600519.SH；000001 → 000001.SZ；已带后缀则原样。仅 A 股。"""
    t = (t or "").strip().upper()
    if "." in t:
        return t
    if not t.isdigit() or len(t) != 6:
        return t
    if t[0] == "6":
        return f"{t}.SH"
    if t[0] in "03":
        return f"{t}.SZ"
    if t[0] in "48":
        return f"{t}.BJ"
    return f"{t}.SZ"


def _num(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _pct_rank(series: pd.Series, value) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if value is None or s.empty:
        return None
    return round(float((s <= value).mean()) * 100.0, 1)


# ───────────────────────── B. 取真实证据（Tushare MCP）─────────────────────────
def _bs_code(ts_code: str) -> str | None:
    """600519.SH → sh.600519。北交所(.BJ)/非沪深 baostock 不覆盖，返回 None。"""
    try:
        num, mkt = ts_code.split(".")
    except ValueError:
        return None
    mkt = mkt.lower()
    return f"{mkt}.{num}" if mkt in ("sh", "sz") else None


def _pct(x):
    """baostock 比率多为小数(0.91=91%)，统一转百分数。"""
    v = _num(x)
    return round(v * 100, 2) if v is not None else None


def _with_timeout(fn, seconds, default):
    """守护线程跑 fn，超时放弃返回 default（baostock 无超时、会死等，必须套这个）。"""
    import threading
    box = {}

    def runner():
        try:
            box["v"] = fn()
        except Exception as e:  # noqa: BLE001
            box["e"] = e
    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive() or "e" in box:
        return default
    return box.get("v", default)


def _bs_rows(rs):
    out = []
    while rs.error_code == "0" and rs.next():
        out.append(dict(zip(rs.fields, rs.get_row_data())))
    return out


def _returns(closes, as_of):
    """从收盘价序列算涨跌幅/52周位置/均线乖离，接地『涨多了/在底部/突破』类价格叙事。"""
    c = pd.to_numeric(closes, errors="coerce").dropna().reset_index(drop=True)
    if len(c) < 2:
        return {}
    last = float(c.iloc[-1])

    def ret(n):
        return round((last / float(c.iloc[-1 - n]) - 1) * 100, 1) if len(c) > n else None
    win = c.tail(252)
    hi, lo = float(win.max()), float(win.min())
    out = {"as_of": as_of, "last_close": round(last, 2),
           "ret_1m_pct": ret(21), "ret_3m_pct": ret(63), "ret_6m_pct": ret(126), "ret_1y_pct": ret(252),
           "from_52w_high_pct": round((last / hi - 1) * 100, 1) if hi else None,
           "from_52w_low_pct": round((last / lo - 1) * 100, 1) if lo else None}
    if len(c) >= 50:
        out["vs_ma50_pct"] = round((last / float(c.tail(50).mean()) - 1) * 100, 1)
    if len(c) >= 200:
        out["vs_ma200_pct"] = round((last / float(c.tail(200).mean()) - 1) * 100, 1)
    return out


def _baostock_bundle(ts_code: str) -> dict:
    """默认数据源：baostock（免 token、免费）。覆盖毛利/净利/ROE/净利同比/营收同比/PE/PB/涨跌幅。"""
    import contextlib
    import io
    out = {"ticker": ts_code, "name": None, "industry": None, "as_of": None,
           "financials": [], "valuation": {}, "sources": [], "error": None}
    code = _bs_code(ts_code)
    if not code:
        out["error"] = "baostock_unsupported_code"
        return out
    import baostock as bs
    with contextlib.redirect_stdout(io.StringIO()):
        bs.login()
    try:
        try:
            b = _bs_rows(bs.query_stock_basic(code=code))
            if b:
                out["name"] = b[0].get("code_name")
        except Exception as e:
            out["error"] = f"basic: {type(e).__name__}"
        by_period: dict = {}
        try:
            for year in (2026, 2025, 2024, 2023):
                for q in (4, 3, 2, 1):
                    if len(by_period) >= 6:  # 6 季足够看趋势；每季 2 次接口，控总耗时
                        break
                    pr = _bs_rows(bs.query_profit_data(code=code, year=year, quarter=q))
                    if not pr or not pr[0].get("statDate"):
                        continue
                    p = pr[0]
                    sd = p["statDate"]
                    rec = by_period.setdefault(sd, {"period": sd})
                    rec.update(gross_margin_pct=_pct(p.get("gpMargin")), net_margin_pct=_pct(p.get("npMargin")),
                               roe_pct=_pct(p.get("roeAvg")), eps_ttm=_num(p.get("epsTTM")), _mbrev=_num(p.get("MBRevenue")))
                    gr = _bs_rows(bs.query_growth_data(code=code, year=year, quarter=q))
                    if gr and gr[0].get("statDate"):
                        g = gr[0]
                        rec.update(netprofit_yoy_pct=_pct(g.get("YOYNI")),
                                   netprofit_attr_yoy_pct=_pct(g.get("YOYPNI")), equity_yoy_pct=_pct(g.get("YOYEquity")))
            fins = sorted(by_period.values(), key=lambda r: r["period"])
            rev = {r["period"]: r.get("_mbrev") for r in fins}
            for r in fins:
                y, md = r["period"][:4], r["period"][4:]
                prev = rev.get(f"{int(y)-1}{md}")
                if prev and r.get("_mbrev"):
                    r["revenue_yoy_pct"] = round(100.0 * (r["_mbrev"] / prev - 1), 1)
                r.pop("_mbrev", None)
            for r in fins[-2:]:  # 现金流/杠杆只补最近 2 期，少打接口
                y, m = int(r["period"][:4]), int(r["period"][5:7])
                q = (m + 2) // 3
                cf = _bs_rows(bs.query_cash_flow_data(code=code, year=y, quarter=q))
                if cf and cf[0].get("statDate") == r["period"]:
                    r["cfo_to_np_pct"] = _pct(cf[0].get("CFOToNP"))
                bal = _bs_rows(bs.query_balance_data(code=code, year=y, quarter=q))
                if bal and bal[0].get("statDate") == r["period"]:
                    r["liability_to_asset_pct"] = _pct(bal[0].get("liabilityToAsset"))
                    r["current_ratio"] = _num(bal[0].get("currentRatio"))
            out["financials"] = fins
            if fins:
                out["as_of"] = fins[-1]["period"]
                out["sources"].append(f"baostock 财务（截至 {out['as_of']}）")
        except Exception as e:
            out["error"] = (out["error"] or "") + f" fin: {type(e).__name__}"
        try:
            today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
            kr = _bs_rows(bs.query_history_k_data_plus(
                code, "date,close,peTTM,pbMRQ", start_date="2020-01-01", end_date=today, frequency="d", adjustflag="3"))
            if kr:
                df = pd.DataFrame(kr)
                last = df.iloc[-1]
                pe, pb = _num(last.get("peTTM")), _num(last.get("pbMRQ"))
                out["valuation"] = {"as_of": last.get("date"), "pe_ttm": round(pe, 2) if pe else None,
                                    "pb": round(pb, 2) if pb else None,
                                    "pe_pctile_5y": _pct_rank(df["peTTM"], pe), "pb_pctile_5y": _pct_rank(df["pbMRQ"], pb)}
                out["sources"].append(f"baostock 估值分位（截至 {last.get('date')}）")
                out["price"] = _returns(df["close"], last.get("date"))
                if out["price"]:
                    out["sources"].append(f"baostock 行情涨跌幅（截至 {last.get('date')}）")
        except Exception as e:
            out["error"] = (out["error"] or "") + f" val: {type(e).__name__}"
    finally:
        with contextlib.redirect_stdout(io.StringIO()):
            bs.logout()
    return out


def _yf_fin_rows(df) -> list:
    """yfinance income_stmt/quarterly_income_stmt → [{period,revenue,net_income,gross_profit}] 按期升序。"""
    if df is None or getattr(df, "empty", True):
        return []

    def _row(name):
        try:
            return df.loc[name] if name in df.index else None
        except Exception:
            return None
    rev, ni, gp = _row("Total Revenue"), _row("Net Income"), _row("Gross Profit")
    rows = []
    for col in df.columns:
        try:
            period = col.date().isoformat()
        except Exception:
            period = str(col)
        rows.append({"period": period,
                     "revenue": _num(rev[col]) if rev is not None else None,
                     "net_income": _num(ni[col]) if ni is not None else None,
                     "gross_profit": _num(gp[col]) if gp is not None else None})
    rows.sort(key=lambda r: r["period"])
    return rows


def _yf_evidence(ts_code: str) -> dict:
    """默认源：yfinance(.SS/.SZ)——已在 prod 工作(与财报拆解同源)、免 token、走 HTTP。
    覆盖近几期营收/净利同比 + 毛利/净利率、当前 PE/PB/市值、价格涨跌幅/52周位置。
    yfinance 不提供历史 PE 序列 → 无 5 年估值分位（诚实留空）。"""
    import yfinance as yf
    out = {"ticker": ts_code, "name": None, "industry": None, "as_of": None,
           "financials": [], "valuation": {}, "sources": [], "error": None}
    try:
        num, mkt = ts_code.split(".")
    except ValueError:
        out["error"] = "bad_code"
        return out
    yf_sym = num + (".SS" if mkt.upper() == "SH" else ".SZ")
    t = yf.Ticker(yf_sym)
    try:
        info = t.info or {}
        out["name"] = info.get("longName") or info.get("shortName")
        out["industry"] = info.get("sector") or info.get("industry")
        pe, pb, mv = _num(info.get("trailingPE")), _num(info.get("priceToBook")), _num(info.get("marketCap"))
        if pe or pb:
            out["valuation"] = {"pe_ttm": round(pe, 2) if pe else None, "pb": round(pb, 2) if pb else None,
                                "market_cap": mv, "pe_pctile_5y": None, "pb_pctile_5y": None}
            out["sources"].append("yfinance 估值（当前 PE/PB，无历史分位）")
    except Exception as e:
        out["error"] = f"info: {type(e).__name__}"
    try:
        rows = _yf_fin_rows(getattr(t, "quarterly_income_stmt", None))
        if len(rows) < 4:
            rows = _yf_fin_rows(getattr(t, "income_stmt", None)) or rows
        rev_map = {r["period"]: r.get("revenue") for r in rows}
        ni_map = {r["period"]: r.get("net_income") for r in rows}
        fins = []
        for r in rows:
            rec = {"period": r["period"]}
            if r.get("revenue") and r.get("gross_profit") is not None:
                rec["gross_margin_pct"] = round(100.0 * r["gross_profit"] / r["revenue"], 2)
            if r.get("revenue") and r.get("net_income") is not None:
                rec["net_margin_pct"] = round(100.0 * r["net_income"] / r["revenue"], 2)
            py = f"{int(r['period'][:4]) - 1}{r['period'][4:]}"  # 同期去年
            if rev_map.get(py) and r.get("revenue"):
                rec["revenue_yoy_pct"] = round(100.0 * (r["revenue"] / rev_map[py] - 1), 1)
            if ni_map.get(py) and r.get("net_income") is not None and rev_map.get(py):
                prev = ni_map[py]
                if prev:
                    rec["netprofit_yoy_pct"] = round(100.0 * (r["net_income"] / prev - 1), 1)
            fins.append(rec)
        out["financials"] = fins[-6:]
        if fins:
            out["as_of"] = fins[-1]["period"]
            out["sources"].append(f"yfinance 财务（截至 {out['as_of']}）")
    except Exception as e:
        out["error"] = (out["error"] or "") + f" fin: {type(e).__name__}"
    try:
        h = t.history(period="5y", auto_adjust=True)
        if h is not None and not h.empty:
            out["price"] = _returns(h["Close"].reset_index(drop=True), str(h.index[-1].date()))
            if out["price"]:
                out["sources"].append("yfinance 行情涨跌幅")
    except Exception:
        pass
    return out


def _evidence(ticker: str) -> dict:
    """证据包，三级降级：① yfinance(prod 可达、免 token) → ② baostock(中国 socket，本地更全)
    → ③ Tushare MCP(需有效 token)。任一拿到财务就用，全失败则返回降级包(主张多判『无法验证』)。"""
    ts_code = normalize_ticker(ticker)
    try:
        ev = _yf_evidence(ts_code)
    except Exception:
        ev = None
    if ev and ev.get("financials"):
        return ev
    try:
        ev2 = _with_timeout(lambda: _baostock_bundle(ts_code), 25.0, None)
    except Exception:
        ev2 = None
    if ev2 and ev2.get("financials"):
        return ev2
    return _tushare_evidence(ts_code)


def _tushare_evidence(ts_code: str) -> dict:
    """兜底：Tushare MCP（需有效 token）。token 失效/缺失则返回降级包 → 主张多判『无法验证』。"""
    out = {"ticker": ts_code, "name": None, "as_of": None,
           "financials": [], "valuation": {}, "sources": [], "error": None}
    tok = _token()
    if not tok:
        out["error"] = "no_data_source"
        return out
    pro = _MCPClient(tok)
    today = datetime.datetime.utcnow().strftime("%Y%m%d")
    try:
        b = pro.query("stock_basic", ts_code=ts_code, fields="ts_code,name,industry")
        if not b.empty:
            out["name"] = b.iloc[0].get("name")
            out["industry"] = b.iloc[0].get("industry")
    except Exception as e:
        out["error"] = f"stock_basic: {type(e).__name__}"
    try:
        fi = pro.query("fina_indicator", ts_code=ts_code, start_date="20190101", end_date=today,
                       fields="ts_code,end_date,or_yoy,netprofit_yoy,grossprofit_margin,roe,debt_to_assets")
        if not fi.empty:
            fi = fi.dropna(subset=["end_date"]).sort_values("end_date").drop_duplicates("end_date", keep="last")
            for _, r in fi.tail(8).iterrows():
                out["financials"].append({
                    "period": r.get("end_date"), "revenue_yoy_pct": _num(r.get("or_yoy")),
                    "netprofit_yoy_pct": _num(r.get("netprofit_yoy")),
                    "gross_margin_pct": _num(r.get("grossprofit_margin")),
                    "roe_pct": _num(r.get("roe")), "liability_to_asset_pct": _num(r.get("debt_to_assets"))})
            if out["financials"]:
                out["as_of"] = out["financials"][-1]["period"]
                out["sources"].append(f"Tushare fina_indicator（截至 {out['as_of']}）")
    except Exception as e:
        out["error"] = (out["error"] or "") + f" fina_indicator: {type(e).__name__}"
    try:
        db = pro.query("daily_basic", ts_code=ts_code, start_date="20200101", end_date=today,
                       fields="ts_code,trade_date,pe_ttm,pb,total_mv")
        if not db.empty:
            db = db.dropna(subset=["trade_date"]).sort_values("trade_date")
            last = db.iloc[-1]
            pe, pb = _num(last.get("pe_ttm")), _num(last.get("pb"))
            out["valuation"] = {"as_of": last.get("trade_date"), "pe_ttm": pe, "pb": pb,
                                "pe_pctile_5y": _pct_rank(db["pe_ttm"], pe),
                                "pb_pctile_5y": _pct_rank(db["pb"], pb)}
            out["sources"].append(f"Tushare daily_basic 估值分位（截至 {last.get('trade_date')}）")
    except Exception as e:
        out["error"] = (out["error"] or "") + f" daily_basic: {type(e).__name__}"
    return out


# ───────────────────────── ⑦ 产业链接地（明白股 sectors）─────────────────────────
def _cbase(t: str) -> str:
    return (t or "").strip().upper().split(".")[0]


def _find_chain(ticker: str, name: str | None) -> dict | None:
    """在明白股产业链图谱里定位 ticker，返回聚焦子图。匹配不到返回 None（⑦退回粗略说明）。"""
    try:
        catalog = (get_sectors() or {}).get("sectors", [])
    except Exception:
        return None
    tb, nm = _cbase(ticker), (name or "").strip()
    for sec in catalog:
        if not isinstance(sec, dict):
            continue
        for layer in sec.get("layers", []) or []:
            for p in layer.get("players", []) or []:
                pt = _cbase(p.get("ticker", ""))
                if (pt and pt == tb) or (nm and p.get("name") and nm in p.get("name")):
                    return _focus(sec, layer, p)
    return None


def _focus(sec: dict, layer: dict, player: dict) -> dict:
    layers = []
    for l in sec.get("layers", []) or []:
        players = [pp.get("name") for pp in (l.get("players") or []) if pp.get("name")][:4]
        layers.append({"layer": l.get("layer"), "stage": l.get("stage"),
                       "tightness": l.get("tightness"), "chokepoint": l.get("chokepoint") or None,
                       "players": players})
    out = {"matched": True, "chain": sec.get("name"), "category": sec.get("category"), "hook": sec.get("hook"),
           "this_player": {"name": player.get("name"), "ticker": player.get("ticker"),
                           "role": player.get("role"), "tier": player.get("tier")},
           "this_layer": {"layer": layer.get("layer"), "stage": layer.get("stage"),
                          "tightness": layer.get("tightness"), "chokepoint": layer.get("chokepoint") or None},
           "layers": layers}
    t = sec.get("transmission")
    if isinstance(t, dict):
        out["transmission"] = {"commodity": (t.get("commodity") or {}).get("name"),
                               "links": [{"name": x.get("name"), "rel": x.get("direction"), "r": x.get("r_change")}
                                         for x in (t.get("links") or [])][:6]}
    return out


# ───────────────────────── A / C / D ─────────────────────────
def _extract(text: str, ts_code: str, name: str | None) -> dict | None:
    user = (f"股票代码：{ts_code}" + (f"（{name}）" if name else "") +
            f"\n\nKOL/博主叙事原文：\n「{text.strip()[:4000]}」\n\n严格只输出 JSON。")
    out = _call(_EXTRACT_SYS, user, max_tokens=2000, timeout=70)
    if "error" in out:
        return {"_error": out["error"], "_detail": out.get("detail")}
    return _json(out.get("text", ""))


def _assemble(ext: dict, ev: dict, chain: dict | None) -> dict | None:
    payload = {"拆解结果": {k: ext.get(k) for k in ("summary", "core_thesis", "direction", "horizon", "claims")},
               "证据包": ev, "产业链图谱": chain or "未提供"}
    user = ("以下是拆解结果、真实证据包、产业链图谱(JSON)。请据此裁决并组卡，"
            "只能用证据包里的数字下『证实/证伪』结论。\n\n"
            + json.dumps(payload, ensure_ascii=False) + "\n\n严格只输出 JSON。")
    out = _call(_ASSEMBLE_SYS, user, max_tokens=3500, timeout=100)
    if "error" in out:
        return {"_error": out["error"], "_detail": out.get("detail")}
    return _json(out.get("text", ""))


def _one_vote(payload_json: str, lens: str) -> dict:
    out = _call(_VERIFY_SYS + "\n你的视角：" + lens,
                "审下面的裁决，只从你的视角挑刺：\n\n" + payload_json + "\n\n只输出 JSON 数组。",
                max_tokens=1500, timeout=70)
    arr = _json(out.get("text", "")) if "error" not in out else None
    return {c.get("id"): c for c in arr if isinstance(c, dict)} if isinstance(arr, list) else {}


def _adversarial(verdicts: list, ev: dict, votes: int) -> dict:
    targets = [v for v in verdicts if v.get("type") == "事实" and v.get("status") in _CHECKABLE]
    if not targets or votes < 1:
        return {"applied": False, "challenges": {}, "n_downgraded": 0, "votes": 0}
    payload = json.dumps({"待质检裁决": [{"id": v.get("id"), "status": v.get("status"),
                                        "basis": v.get("basis"), "evidence": v.get("evidence")} for v in targets],
                          "证据包": ev}, ensure_ascii=False)
    lenses = [_LENSES[i % len(_LENSES)] for i in range(votes)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(votes, 4)) as ex:
        ballots = list(ex.map(lambda L: _one_vote(payload, L), lenses))
    cast = sum(1 for b in ballots if b)
    if not cast:
        return {"applied": False, "challenges": {}, "n_downgraded": 0, "votes": 0}
    challenges, n_down, need = {}, 0, cast // 2 + 1
    for v in targets:
        vid = v.get("id")
        against = [b[vid] for b in ballots if vid in b and not b[vid].get("upheld")]
        if len(against) >= need:
            sugg = max((c.get("suggested_status") for c in against if c.get("suggested_status")),
                       key=lambda s: _CONS.get(s, 0), default="无法验证")
            reason = max(against, key=lambda c: _CONS.get(c.get("suggested_status"), 0)).get("challenge")
            challenges[vid] = {"upheld": False, "suggested_status": sugg, "challenge": reason,
                               "votes_against": len(against), "votes_total": cast}
            n_down += 1
        else:
            challenges[vid] = {"upheld": True, "votes_against": len(against), "votes_total": cast}
    return {"applied": True, "challenges": challenges, "n_downgraded": n_down, "votes": cast}


def _apply(verdicts: list, result: dict) -> list:
    ch, out = result.get("challenges", {}), []
    for v in verdicts:
        c = ch.get(v.get("id"))
        v = dict(v)
        if c and not c.get("upheld"):
            v["status_before_check"] = v.get("status")
            v["status"] = c.get("suggested_status") or "无法验证"
            v["challenge"] = c.get("challenge")
            v["votes"] = f"{c.get('votes_against')}/{c.get('votes_total')} 质疑"
        elif c:
            v["self_checked"] = f"{c.get('votes_total')} 视角通过"
        out.append(v)
    return out


@cached(86400)
def build_card(text: str, ticker: str, selfcheck: bool = True, votes: int = 2) -> dict:
    """跑完整核验流程，返回核验卡。未配置 key → {"ok":False,...}；各阶段失败带 stage 原因。"""
    if not enabled():
        return {"ok": False, "stage": "config", "error": "no_api_key"}
    text = (text or "").strip()
    if len(text) < 8:
        return {"ok": False, "stage": "input", "error": "叙事太短，至少写一句完整的看多/看空理由"}
    ts_code = normalize_ticker(ticker)
    # evidence(baostock，慢) 与 extract(LLM) 互不依赖，并行跑省一截时间；extract 不强依赖公司名。
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as _ex:
        f_ev = _ex.submit(_evidence, ticker)
        f_ext = _ex.submit(_extract, text, ts_code, None)
        ev = f_ev.result()
        ext = f_ext.result()
    name = ev.get("name")
    chain = _find_chain(ts_code, name)
    if not ext or "_error" in (ext or {}):
        return {"ok": False, "stage": "extract", "error": (ext or {}).get("_error", "extract_failed"),
                "detail": (ext or {}).get("_detail")}
    card = _assemble(ext, ev, chain)
    if not card or "_error" in (card or {}):
        return {"ok": False, "stage": "assemble", "error": (card or {}).get("_error", "assemble_failed"),
                "detail": (card or {}).get("_detail")}
    verdicts = card.get("verdicts", [])
    selfcheck_info = None
    if selfcheck and verdicts:
        res = _adversarial(verdicts, ev, votes=votes)
        verdicts = _apply(verdicts, res)
        selfcheck_info = {"ran": res.get("applied", False), "downgraded": res.get("n_downgraded", 0),
                          "votes": res.get("votes", 0)}
    return {
        "ok": True,
        "ticker": ev.get("ticker"), "name": name, "as_of": ev.get("as_of"),
        "summary": ext.get("summary"), "core_thesis": ext.get("core_thesis"),
        "direction": ext.get("direction"), "horizon": ext.get("horizon"),
        "claims": ext.get("claims", []),
        "headline": card.get("headline"), "verdicts": verdicts,
        "self_check": selfcheck_info, "sources": card.get("sources", []),
        "supply_chain_grounded": bool(chain),
        "financial_check": card.get("financial_check", {}),
        "valuation_priced_in": card.get("valuation_priced_in", {}),
        "supply_chain": card.get("supply_chain", {}),
        "bull": card.get("bull", []), "bear": card.get("bear", []),
        "disconfirmers": card.get("disconfirmers", []),
        "falsification": card.get("falsification"), "caveat": card.get("caveat"),
        "evidence_sources": ev.get("sources", []),
    }
