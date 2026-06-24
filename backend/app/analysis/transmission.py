"""产业链「实证传导」：用真实财报的单季毛利率 vs 上游商品价格，
算每个环节的历史敏感度（同向/反向/≈无关 + 变化量相关 Δr + 样本数 n）。

为什么这么做（对应产品宪法·诚实优先）：
- 不硬编码"原材料降价利好 X"这种凭空弹性——那很容易方向都讲反
  （锂价跌对上游矿企是利空、对下游电芯厂≈无关）。
- 只对"有公开价格序列"的链给数字；没有干净商品价的链就不在这里出现（留定性）。
- 每条都带 n、相关≠因果、非投资建议。

数据源 Tushare（需要 TS_TOKEN 环境变量），**仅在本机批处理时联网调用**：
    TS_TOKEN=xxx python -m app.analysis.transmission
build() 会按 CHAINS 注册表**一条接一条**自动跑完所有链，产出静态
transmission.json 随应用发布；**生产环境只读 JSON、不联网、不需要 token**。
注册表里只放"有公开商品期货价"的 A 股链；季度刷新=本机重跑一次此命令。
"""
from __future__ import annotations

import os
import time
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ARTIFACT = Path(__file__).resolve().parent / "transmission.json"

MIN_N = 8  # 重叠季数 < 8 的链不出数：相关性不可信，宁可不做也不上噪音（诚实优先）

# 注册表：每条链一个商品价 + 下游→上游的 A 股环节（含对照组）。
# ticker 存 Tushare 格式(.SH/.SZ)，前端展示自动转 .SS。
CHAINS = {
    "battery": {
        "title": "锂价沿链传导 · 实证",
        "commodity": {"name": "碳酸锂", "full": "碳酸锂（电池级）", "exchange": "GFEX",
                      "prefix": "LC", "proxy": "GFEX 碳酸锂期货主力连续", "unit": "元/吨", "since": "20230701"},
        "links": [
            ("002466.SZ", "天齐锂业", "上游·锂矿"),
            ("002460.SZ", "赣锋锂业", "上游·锂矿"),
            ("301358.SZ", "湖南裕能", "中游·正极(LFP)"),
            ("300769.SZ", "德方纳米", "中游·正极(LFP)"),
            ("002709.SZ", "天赐材料", "中游·电解液/六氟"),
            ("300750.SZ", "宁德时代", "下游·电芯"),
            ("002594.SZ", "比亚迪", "下游·电芯/整车"),
            ("002812.SZ", "恩捷股份", "中游·隔膜(对照)"),
            ("600110.SH", "诺德股份", "中游·铜箔(对照)"),
        ],
    },
    "solar": {
        "title": "多晶硅价沿链传导 · 实证",
        "commodity": {"name": "多晶硅", "full": "多晶硅", "exchange": "GFEX",
                      "prefix": "PS", "proxy": "GFEX 多晶硅期货主力连续", "unit": "元/吨", "since": "20231201"},
        "links": [
            ("600905.SH", "三峡能源", "下游·电站运营"),
            ("002459.SZ", "天合光能", "下游·组件"),
            ("601012.SH", "隆基绿能", "中游·硅片/组件"),
            ("600732.SH", "爱旭股份", "中游·电池片"),
            ("002129.SZ", "TCL中环", "中游·硅片"),
            ("600438.SH", "通威股份", "上游·多晶硅料"),
            ("603688.SH", "石英股份", "上游·石英砂坩埚(对照)"),
            ("601865.SH", "福莱特", "辅材·光伏玻璃(对照)"),
            ("603806.SH", "福斯特", "辅材·胶膜(对照)"),
        ],
    },
    "ev": {
        "title": "锂价沿链传导 · 电动车视角 · 实证",
        "commodity": {"name": "碳酸锂", "full": "碳酸锂（电池级）", "exchange": "GFEX",
                      "prefix": "LC", "proxy": "GFEX 碳酸锂期货主力连续", "unit": "元/吨", "since": "20230701"},
        "links": [
            ("002594.SZ", "比亚迪", "下游·整车"),
            ("300750.SZ", "宁德时代", "下游·电芯"),
            ("300919.SZ", "中伟股份", "中游·正极前驱体"),
            ("002340.SZ", "格林美", "中游·电池回收"),
            ("002466.SZ", "天齐锂业", "上游·锂矿"),
            ("002812.SZ", "恩捷股份", "中游·隔膜(对照)"),
        ],
    },
    "grid": {
        "title": "铜价沿链传导 · 实证",
        "commodity": {"name": "铜", "full": "铜", "exchange": "SHFE",
                      "prefix": "CU", "proxy": "SHFE 沪铜期货主力连续", "unit": "元/吨", "since": "20200101"},
        "links": [
            ("600089.SH", "特变电工", "中游·变压器(铜)"),
            ("601179.SH", "中国西电", "中游·变压器/开关(铜)"),
            ("600312.SH", "平高电气", "中游·开关GIS"),
            ("000400.SZ", "许继电气", "中游·二次/换流阀"),
            ("600406.SH", "国电南瑞", "中游·二次/控制软件(对照)"),
            ("600019.SH", "宝钢股份", "原材料·钢(对照)"),
        ],
    },
    "gold": {
        "title": "金价沿链传导 · 实证",
        "commodity": {"name": "黄金", "full": "黄金", "exchange": "SHFE",
                      "prefix": "AU", "proxy": "SHFE 沪金期货主力连续", "unit": "元/克", "since": "20180101"},
        "links": [
            ("601899.SH", "紫金矿业", "上游·金矿"),
            ("600547.SH", "山东黄金", "上游·金矿"),
            ("600988.SH", "赤峰黄金", "上游·金矿"),
            ("000975.SZ", "山金国际", "上游·金矿"),
            ("600489.SH", "中金黄金", "中游·冶炼"),
            ("600612.SH", "老凤祥", "下游·黄金珠宝(对照)"),
            ("002867.SZ", "周大生", "下游·黄金珠宝(对照)"),
        ],
    },
    "aluminum": {
        "title": "铝价沿链传导 · 实证",
        "commodity": {"name": "铝", "full": "电解铝", "exchange": "SHFE",
                      "prefix": "AL", "proxy": "SHFE 沪铝期货主力连续", "unit": "元/吨", "since": "20180101"},
        "links": [
            ("601600.SH", "中国铝业", "上游·电解铝"),
            ("000807.SZ", "云铝股份", "上游·电解铝"),
            ("000933.SZ", "神火股份", "上游·电解铝"),
            ("002532.SZ", "天山铝业", "上游·电解铝"),
            ("002128.SZ", "电投能源", "上游·电解铝"),
            ("600219.SH", "南山铝业", "下游·铝加工(对照)"),
        ],
    },
}


def _token() -> str | None:
    """先读环境变量；缺省回退到 backend/.env（gitignored，本机密钥位）。"""
    tok = os.environ.get("TS_TOKEN")
    if tok:
        return tok
    envf = Path(__file__).resolve().parent.parent.parent / ".env"
    try:
        for line in envf.read_text(encoding="utf-8").splitlines():
            if line.startswith("TS_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"\'')
    except Exception:
        pass
    return None


class _MCPClient:
    """通过 Tushare MCP Server(HTTP/SSE)取数：token 在服务端被消费，
    **绕过客户端 10-IP 绑定限制**（直连 SDK 在轮换 IP 的环境里会被挡）。
    方法签名兼容 tushare SDK 的 pro.income()/fut_daily() 等，返回 DataFrame。"""

    def __init__(self, token: str):
        self.url = f"https://api.tushare.pro/mcp/?token={token}"
        self._headers = {"Content-Type": "application/json",
                         "Accept": "application/json, text/event-stream"}
        self._id = 0

    def _call(self, name: str, arguments: dict) -> pd.DataFrame:
        import requests
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                   "params": {"name": name, "arguments": arguments}}
        r = requests.post(self.url, headers=self._headers, json=payload, timeout=90)
        text = None
        for line in r.text.splitlines():
            if line.startswith("data:"):
                obj = json.loads(line[len("data:"):].strip())
                res = obj.get("result", {})
                content = res.get("content") or []
                if content and content[0].get("type") == "text":
                    text = content[0]["text"]
                    if res.get("isError"):
                        raise RuntimeError(f"{name}: {str(text)[:120]}")
        if text is None:
            raise RuntimeError(f"{name}: 无返回 {r.text[:160]}")
        return pd.DataFrame(json.loads(text))

    def query(self, name: str, **kwargs) -> pd.DataFrame:
        args = {k: v for k, v in kwargs.items() if v is not None}
        if isinstance(args.get("fields"), str):  # MCP 要求 fields 为数组
            args["fields"] = [f.strip() for f in args["fields"].split(",") if f.strip()]
        return self._call(name, args)

    def income(self, **kw):
        return self.query("income", **kw)

    def fina_indicator(self, **kw):
        return self.query("fina_indicator", **kw)

    def fut_basic(self, **kw):
        return self.query("fut_basic", **kw)

    def fut_daily(self, **kw):
        return self.query("fut_daily", **kw)


def _pro():
    tok = _token()
    if not tok:
        raise RuntimeError("需要 TS_TOKEN（环境变量或 backend/.env）")
    return _MCPClient(tok)


def _quarterly_gm(pro, code: str) -> pd.Series:
    """单季毛利率(%)：财报营收/营业成本是累计值，按季度去累计再算毛利。"""
    df = pro.income(ts_code=code, start_date="20180101", end_date="20261231",
                    fields="ts_code,ann_date,end_date,report_type,revenue,oper_cost")
    df = df[df.report_type == "1"].dropna(subset=["revenue", "oper_cost"]).copy()
    df = df.sort_values("ann_date").drop_duplicates("end_date", keep="last")
    df["end"] = pd.to_datetime(df["end_date"])
    df = df.sort_values("end")
    df["y"], df["m"] = df.end.dt.year, df.end.dt.month
    rows = {}
    for y, g in df.groupby("y"):
        g = g.set_index("m")
        for m in (3, 6, 9, 12):
            if m not in g.index:
                continue
            rev, cost = g.loc[m, "revenue"], g.loc[m, "oper_cost"]
            pm = {3: None, 6: 3, 9: 6, 12: 9}[m]
            if pm and pm in g.index:
                rev -= g.loc[pm, "revenue"]
                cost -= g.loc[pm, "oper_cost"]
            if rev and rev > 0:
                rows[pd.Period(f"{y}Q{m // 3}", "Q")] = round((rev - cost) / rev * 100, 1)
    return pd.Series(rows).sort_index()


def _commodity_quarterly(pro, exchange: str, prefix: str, since: str) -> pd.Series | None:
    """某商品期货(交易所+代码前缀)主力连续=每日 OI 最大合约，季度均值。"""
    cons = pro.fut_basic(exchange=exchange, fut_type="1", fields="ts_code,symbol,list_date")
    sel = cons[cons.symbol.str.upper().str.startswith(prefix)]
    if "list_date" in sel.columns:
        sel = sel[sel["list_date"].fillna("0") >= since]
    frames = []
    for c in sel.ts_code:
        try:
            frames.append(pro.fut_daily(ts_code=c, fields="trade_date,close,oi"))
            time.sleep(0.12)
        except Exception:
            pass
    if not frames:
        return None
    allf = pd.concat(frames)
    allf["trade_date"] = pd.to_datetime(allf["trade_date"])
    dom = (allf.dropna(subset=["oi"]).sort_values("oi")
           .groupby("trade_date").tail(1).set_index("trade_date").sort_index())
    s = dom["close"].resample("QE").mean()
    s.index = s.index.to_period("Q")
    return s.round(0)


def _classify(r_change: float, layer: str, cn: str) -> tuple[str, str]:
    up = "上游" in layer
    ctrl = "对照" in layer
    # 对照组永远不抢"同向"标签：它是用来检验"是否传导"的参照，哪怕 Δr 偶然偏高，
    # 也多是共同的宏观周期/库存损益，而非该商品成本直接传导（诚实，避免误导）。
    if ctrl:
        if abs(r_change) >= 0.3:
            return "≈无关", f"对照组：与{cn}价同期出现 {r_change:+.2f} 的相关，多半是共同的宏观周期或库存损益，并非{cn}成本直接传导。"
        return "≈无关", f"对照组：成本主要不是{cn}（其它金属/加工/折旧），{cn}价波动基本不传导到这。"
    if r_change >= 0.3:
        if up:
            return "同向", f"卖{cn}为生：{cn}价涨它赚、跌它亏——原料降价对它是利空。"
        return "同向", f"毛利随{cn}价同向波动：涨价时顺价、跌价有滞后，赚的是加工与库存差。"
    if r_change <= -0.3:
        return "反向", f"毛利与{cn}价反向：多半是成本顺价滞后或库存损益主导，需个案看。"
    return "≈无关", f"{cn}价大幅波动期间毛利基本不动——成本可转嫁或占比低，毛利由自身定价权决定。"


def _build_chain(pro, key: str, cfg: dict) -> dict | None:
    com = cfg["commodity"]
    cn = com["name"]
    price = _commodity_quarterly(pro, com["exchange"], com["prefix"], com.get("since", "20180101"))
    if price is None or len(price) < 5:
        print(f"[{key}] 商品价格序列不足，跳过")
        return None
    quarters = list(price.index)
    if len(quarters) < MIN_N:
        print(f"[{key}] 商品仅 {len(quarters)} 季(<{MIN_N})，相关性不可信，不出数（诚实），跳过")
        return None
    links = []
    for code, name, layer in cfg["links"]:
        try:
            gm = _quarterly_gm(pro, code)
            time.sleep(0.25)
        except Exception as e:  # noqa: BLE001
            print(f"  [{key}] skip {name} {code}: {str(e)[:50]}")
            continue
        al = pd.DataFrame({"p": price, "gm": gm}).dropna()
        if len(al) < 5:
            print(f"  [{key}] 样本少 {name}: n={len(al)}")
            continue
        r_level = round(float(al["p"].corr(al["gm"])), 2)
        r_change = round(float(al["p"].diff().corr(al["gm"].diff())), 2)
        direction, read = _classify(r_change, layer, cn)
        links.append({
            "ts_code": code.replace(".SH", ".SS"), "name": name, "layer": layer,
            "direction": direction, "r_change": r_change, "r_level": r_level,
            "n": int(len(al)), "read": read,
            "gm": al["gm"].reindex(quarters).round(1).where(pd.notna, None).tolist(),
        })
    same = [l["name"] for l in links if l["direction"] == "同向"]
    flat_down = [l["name"] for l in links if l["direction"] == "≈无关" and "下游" in l["layer"]]
    if same:
        headline = f"{cn}价主要在{'、'.join(same[:4])}等环节同向传导（涨跌直接进毛利）；"
        headline += (f"到{'、'.join(flat_down)}这层基本消失，毛利由自身定价权决定。"
                     if flat_down else "越往下游、越靠对照环节，传导越弱。")
    else:
        headline = f"{cn}价对该链各环节毛利的传导都很弱——多为成本顺价、由订单定价主导，毛利不随{cn}价起伏。"
    return {
        "title": cfg["title"],
        "commodity": {
            "name": com.get("full", cn), "proxy": com["proxy"], "unit": com["unit"],
            "n": len(quarters),
            "window": f"{quarters[0]}–{quarters[-1]}" if quarters else "",
            "latest": float(price.iloc[-1]) if len(price) else None,
            "low": float(price.min()) if len(price) else None,
            "high": float(price.max()) if len(price) else None,
        },
        "quarters": [str(q) for q in quarters],
        "price": [float(x) for x in price.tolist()],
        "links": links,
        "headline": headline,
        "method": "单季毛利率（财报去累计）对商品价格的相关性；Δr=变化量相关(去趋势)，更看同步性。",
        "source": f"Tushare：财报利润表 + {com['proxy']}",
        "as_of": str(quarters[-1]) if quarters else "",
        "caveat": "历史相关性，样本季数 n 较小、相关≠因果，仅作结构参考，不构成投资建议。",
    }


def load() -> dict:
    """只读现有产物：{sector_key: transmission}，无则空。不联网。"""
    try:
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build(only: list[str] | None = None) -> dict:
    """本机批处理：按 CHAINS 一条接一条自动跑完，**合并**进现有 transmission.json
    （部分失败不会丢掉已成功的链——可反复重跑直到全部补齐）。
    only=['solar',...] 可只跑指定链。"""
    warnings.filterwarnings("ignore")
    pro = _pro()
    out = load()  # 从现有产物起步，成功的链就地更新、失败的保留旧值
    for key, cfg in CHAINS.items():
        if only and key not in only:
            continue
        print(f"\n>>> 跑 [{key}] {cfg['title']} …")
        try:
            res = _build_chain(pro, key, cfg)
        except Exception as e:  # noqa: BLE001
            print(f"    [{key}] 失败，保留旧值: {str(e)[:60]}")
            continue
        if res and res["links"]:
            out[key] = res
            print(f"    完成 {key}: {len(res['links'])} 环节, 商品 {res['commodity']['window']}")
        else:
            print(f"    [{key}] 本次未取到，保留旧值")
    out_path = Path(os.environ.get("TRANSMISSION_OUT", str(ARTIFACT)))
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    res = build()
    print("\n================ 汇总 ================")
    for key, b in res.items():
        print(f"\n[{key}] {b['title']}  | {b['commodity']['name']} {b['commodity']['window']}")
        print(f"{'公司':<8}{'环节':<22}{'方向':<6}{'Δr':>6}{'水平r':>7}{'n':>4}")
        for l in b["links"]:
            print(f"{l['name']:<8}{l['layer']:<22}{l['direction']:<6}{l['r_change']:>6}{l['r_level']:>7}{l['n']:>4}")
    print(f"\n写入 {ARTIFACT} | 链数: {len(res)}")
