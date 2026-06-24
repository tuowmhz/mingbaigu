"""机构持仓（个股视角）：哪些大机构持有这只股票。来自 13F 公开汇总。"""
import pandas as pd
import yfinance as yf

from ..cache import cached


@cached(86400)
def get_holders(ticker: str) -> dict | None:
    try:
        df = yf.Ticker(ticker).institutional_holders
    except Exception:
        return None
    if df is None or df.empty:
        return None
    items = []
    for _, row in df.head(10).iterrows():
        pct = row.get("pctHeld")
        items.append({
            "holder": str(row.get("Holder", "")),
            "pct_held": round(float(pct), 4) if pd.notna(pct) else None,
            "value": float(row["Value"]) if pd.notna(row.get("Value")) else None,
            "date": str(row.get("Date Reported", ""))[:10],
        })
    total_pct = sum(i["pct_held"] for i in items if i["pct_held"]) if items else 0
    return {
        "items": items,
        "top10_pct": round(total_pct, 4),
        "source": "13F 机构持仓汇总",
    }
