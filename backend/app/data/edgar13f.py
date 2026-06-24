"""大佬持仓：直接从 SEC EDGAR 解析知名机构的最新 13F-HR 文件。

只用相对权重（单笔市值/组合总市值），避开 13F 申报单位的历史变更问题。
"""
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import requests

from ..cache import cached

# SEC 要求 UA 里有联系方式
_HEADERS = {"User-Agent": "StockPrediction research tool (contact: github.com/tuowmhz/StockPrediction)"}

FAMOUS = [
    ("伯克希尔·哈撒韦（巴菲特）", "0001067983"),
    ("桥水基金（达利欧）", "0001350694"),
    ("文艺复兴科技（西蒙斯）", "0001037389"),
]


def _latest_13f_holdings(cik: str) -> list[dict] | None:
    try:
        sub = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                           headers=_HEADERS, timeout=20).json()
        recent = sub["filings"]["recent"]
        idx = next(i for i, f in enumerate(recent["form"]) if f == "13F-HR")
        accession = recent["accessionNumber"][idx].replace("-", "")
        cik_num = str(int(cik))
        base = f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{accession}"
        index = requests.get(f"{base}/index.json", headers=_HEADERS, timeout=20).json()
        xml_files = [f["name"] for f in index["directory"]["item"]
                     if f["name"].lower().endswith(".xml")
                     and "primary" not in f["name"].lower()]
        # infotable 通常是除 primary_doc 外最大的 xml
        info_name = next((n for n in xml_files if "info" in n.lower()), None) or (xml_files[-1] if xml_files else None)
        if not info_name:
            return None
        xml = requests.get(f"{base}/{info_name}", headers=_HEADERS, timeout=30).text
    except Exception:
        return None

    # 去命名空间解析
    xml = re.sub(r'xmlns(:\w+)?="[^"]+"', "", xml, count=2)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None

    holdings: dict[str, float] = {}
    for it in root.iter():
        if not it.tag.endswith("infoTable"):
            continue
        name = value = None
        for ch in it:
            tag = ch.tag.split("}")[-1]
            if tag == "nameOfIssuer":
                name = (ch.text or "").strip().title()
            elif tag == "value" and ch.text:
                try:
                    value = float(ch.text)
                except ValueError:
                    value = None
        if name and value:
            holdings[name] = holdings.get(name, 0.0) + value
    if not holdings:
        return None
    total = sum(holdings.values())
    top = sorted(holdings.items(), key=lambda kv: -kv[1])[:12]
    return [{"issuer": n, "weight": round(v / total, 4)} for n, v in top]


@cached(86400)
def get_famous_13f() -> dict:
    with ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(lambda f: (_latest_13f_holdings(f[1])), FAMOUS))
    filers = []
    for (name, cik), holdings in zip(FAMOUS, results):
        if holdings:
            filers.append({"name": name, "cik": cik, "holdings": holdings})
    out = {
        "filers": filers,
        "source": "SEC EDGAR 13F-HR（季度披露，有最长 45 天滞后）",
        "note": "13F 只披露美股多头持仓，看不到空头/衍生品/海外仓位；权重为组合内相对占比。",
    }
    if not filers:
        out["unavailable_reason"] = (
            "当前网络环境访问 SEC EDGAR 被拒（403）——SEC 会屏蔽部分网络的自动化请求。"
            "换一个网络环境（如家庭宽带/手机热点）重启后端即可恢复；个股页的机构持仓不受影响。"
        )
    return out
