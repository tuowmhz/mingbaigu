"""散户热度榜：东方财富股吧人气排名（公开数据）。

产品逻辑：散户要的不是更快的信息，是"该看哪只"的钩子——
全市场散户此刻在围观什么，本身就是最好的钩子。
同花顺/富途没有免费稳定的公开接口，东财人气榜是同类最优替代。
"""
import json
from pathlib import Path

import requests

from ..cache import cached

_H = {"User-Agent": "Mozilla/5.0"}
RANK_URL = "https://emappdata.eastmoney.com/stockrank/getAllCurrentList"
BATCH_NAME_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
NAMES_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "cn_names.json"


def _load_names() -> dict:
    try:
        return json.loads(NAMES_FILE.read_text()) if NAMES_FILE.exists() else {}
    except Exception:
        return {}


def _resolve_names(scs: list[str]) -> dict[str, str]:
    """批量解析中文名（单次请求），结果永久落盘——股票名字不会变。"""
    names = _load_names()
    missing = [sc for sc in scs if sc not in names]
    if missing:
        secids = ",".join(("0." if sc.startswith("SZ") else "1.") + sc[2:] for sc in missing)
        try:
            r = requests.get(BATCH_NAME_URL, params={
                "secids": secids, "fields": "f12,f13,f14", "invt": "2", "fltt": "2",
            }, headers=_H, timeout=10)
            for row in (r.json().get("data") or {}).get("diff") or []:
                prefix = "SZ" if row.get("f13") == 0 else "SH"
                names[prefix + str(row.get("f12"))] = row.get("f14")
            NAMES_FILE.parent.mkdir(parents=True, exist_ok=True)
            NAMES_FILE.write_text(json.dumps(names, ensure_ascii=False))
        except Exception:
            pass  # 限流时优雅降级显示代码，下次刷新自动补上
    return names


@cached(1800)  # 30 分钟——热度榜本来就不该高频刷
def get_retail_heat(limit: int = 12) -> dict | None:
    try:
        r = requests.post(RANK_URL, json={
            "appId": "appId01", "globalId": "786e4c21-70dc-435a-93bb-38",
            "marketType": "", "pageNo": 1, "pageSize": limit,
        }, headers=_H, timeout=12)
        rows = r.json().get("data") or []
    except Exception:
        return None
    if not rows:
        return None

    scs = [row.get("sc", "") for row in rows[:limit] if len(row.get("sc", "")) > 2]
    names = _resolve_names(scs)
    items = []
    for row in rows[:limit]:
        sc = row.get("sc", "")
        if len(sc) < 3:
            continue
        suffix = ".SZ" if sc.startswith("SZ") else ".SS"
        items.append({
            "ticker": sc[2:] + suffix,          # 转成本平台可分析的代码
            "name": names.get(sc) or sc,
            "rank": row.get("rk"),
            "rank_change": row.get("hisRc"),     # 相比上期的名次变化（正=蹿升）
        })
    return {
        "items": items,
        "source": "东方财富股吧人气榜",
        "note": "散户围观榜 ≠ 推荐榜：热度蹿升常意味着剧烈波动已经发生——它告诉你该研究什么，不告诉你该买什么。",
    }
