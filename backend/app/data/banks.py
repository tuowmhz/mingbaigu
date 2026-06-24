"""银行公开监管数据：FDIC BankFind Suite API（官方、免费、无需密钥）。

上市主体是银行控股公司，FDIC 数据对应其旗下受 FDIC 保险的银行实体，
反映的是银行核心业务（存贷款、资本、盈利）的监管口径数据。
"""
import requests

from ..cache import cached
from ..config import BANK_FDIC, CACHE_TTL_FDIC

API_BASE = "https://banks.data.fdic.gov/api"

# 取最近 8 个季度的关键指标
FIELDS = "REPDTE,ASSET,DEP,NETINC,ROA,ROE,NIMY,EQ,LNLSNET"

FIELD_DESC = {
    "ASSET": "总资产（千美元）",
    "DEP": "总存款（千美元）",
    "NETINC": "净利润（千美元）",
    "ROA": "总资产收益率 %",
    "ROE": "净资产收益率 %",
    "NIMY": "净息差 %",
    "EQ": "股东权益（千美元）",
    "LNLSNET": "净贷款（千美元）",
}


def _resolve_cert(ticker: str) -> int | None:
    info = BANK_FDIC.get(ticker)
    if not info:
        return None
    cert = info["cert"]
    # 校验 CERT 是否仍有效，无效则按名称搜索兜底
    try:
        r = requests.get(
            f"{API_BASE}/institutions",
            params={"filters": f"CERT:{cert}", "fields": "NAME,CERT,ACTIVE", "limit": 1},
            timeout=15,
        )
        data = r.json().get("data", [])
        if data:
            return cert
    except Exception:
        return cert  # 网络抖动时直接用配置值
    try:
        r = requests.get(
            f"{API_BASE}/institutions",
            params={"search": f"NAME:{info['entity']}", "fields": "NAME,CERT,ACTIVE",
                    "limit": 1, "sort_by": "ASSET", "sort_order": "DESC"},
            timeout=15,
        )
        data = r.json().get("data", [])
        if data:
            return int(data[0]["data"]["CERT"])
    except Exception:
        pass
    return None


@cached(CACHE_TTL_FDIC)
def get_bank_financials(ticker: str) -> dict | None:
    """最近 8 个季度的 FDIC 监管财务数据 + 同比变化。"""
    cert = _resolve_cert(ticker)
    if cert is None:
        return None
    try:
        r = requests.get(
            f"{API_BASE}/financials",
            params={
                "filters": f"CERT:{cert}",
                "fields": FIELDS,
                "sort_by": "REPDTE",
                "sort_order": "DESC",
                "limit": 8,
                "format": "json",
            },
            timeout=20,
        )
        rows = [item["data"] for item in r.json().get("data", [])]
    except Exception:
        return None
    if not rows:
        return None

    def r2(v):
        return None if v is None else round(float(v), 2)

    quarters = []
    for row in rows:
        rep = str(row.get("REPDTE", ""))
        quarters.append({
            "report_date": f"{rep[:4]}-{rep[4:6]}-{rep[6:8]}" if len(rep) == 8 else rep,
            "total_assets_k": row.get("ASSET"),
            "total_deposits_k": row.get("DEP"),
            "net_income_k": row.get("NETINC"),
            "roa": r2(row.get("ROA")),
            "roe": r2(row.get("ROE")),
            "net_interest_margin": r2(row.get("NIMY")),
            "equity_k": row.get("EQ"),
            "net_loans_k": row.get("LNLSNET"),
        })

    latest, oldest = quarters[0], quarters[-1]

    def yoy(key):
        a, b = latest.get(key), oldest.get(key)
        if a is None or b in (None, 0):
            return None
        return round((a / b - 1) * 100, 2)

    return {
        "entity": BANK_FDIC[ticker]["entity"],
        "cert": cert,
        "source": "FDIC BankFind Suite API",
        "quarters": quarters,
        "trend": {
            "assets_change_pct": yoy("total_assets_k"),
            "deposits_change_pct": yoy("total_deposits_k"),
            "loans_change_pct": yoy("net_loans_k"),
        },
    }
