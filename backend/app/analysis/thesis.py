"""论点拆解：把用户一句对当下行情的判断，拆成一个【可被证伪】的结构化论点。

地基是平台已有的真实数据（产业链图谱 + 实证传导 beta），用它约束 LLM——
只能用目录里的真实 ticker，不编；并强制给"多空两面 + 标的与判断的关系 + 如何验证/证伪"。
不给买卖/仓位/涨幅承诺。走 ai_budget 电表，超 AI_DAILY_BUDGET_USD 自动熔断。
产出的 JSON 直接喂前端「论点卡」与统一分享卡引擎。
"""
import json
import os
import re

from ..ai_budget import call_claude
from ..cache import cached

MODEL = os.environ.get("CLAUDE_ANALYST_MODEL", "claude-sonnet-4-6")

SYSTEM = (
    "你是「明白股」的论点拆解师。用户给一句对当下行情/某产业链的判断，你把它拆成一个"
    "可被证伪的结构化论点。这不是帮用户证明他对，而是逼他看清两面、并知道怎么验证自己错没错。\n"
    "铁律：\n"
    "1) ticker 只能用【数据目录】里出现过的，目录里没有的绝不编造——宁可该字段留空或写 null。\n"
    "2) 多空两面都要给；尽量挂目录里的实证数据（传导关系 rel/相关系数 r、卡点 tight）。\n"
    "3) targets 必须标注每个标的『与该判断的关系』：若目录传导显示某环节 rel=\"≈无关\"，"
    "必须诚实点破『买它≠押这个判断』这类常见误区，而不是顺着用户说。\n"
    "4) 必须给『如何验证』：可跟踪的领先指标，以及一条『若 X 没发生/反向，就认错重估』的证伪触发。\n"
    "5) 绝不输出买卖/仓位/目标价/涨幅承诺。结尾 caveat 写明不构成投资建议。\n"
    "6) 若判断与目录数据矛盾（如它其实是共识/拥挤、或传导方向相反），在 bear 或 assumption 里直说。\n"
    "措辞要精炼：bull/bear 每条 ≤40 字、note ≤25 字、scenario 每项 ≤60 字、targets ≤5 个、validation ≤4 条。\n"
    "只输出一个 JSON 对象，不要任何额外文字，schema：\n"
    "{\"chain\":\"命中的产业链中文名\",\"direction\":\"看多|看空|中性\",\"horizon\":\"时间维度\","
    "\"assumption\":\"这句话真正押的核心假设(一句话)\","
    "\"bull\":[\"看多证据(尽量挂数据)\",...3条],\"bear\":[\"看空证据(尽量挂数据)\",...3条],"
    "\"targets\":[{\"layer\":\"环节\",\"name\":\"公司\",\"ticker\":\"目录里的代码或null\",\"relation\":\"同向|≈无关|反向|对照\",\"note\":\"与判断的关系一句话\"}],"
    "\"scenario\":{\"if_holds\":\"若假设成立，历史上谁弹性大(用相对强弱/传导，不给涨幅)\",\"if_wrong\":\"若证伪，谁受伤最重\"},"
    "\"validation\":[\"领先指标1\",\"指标2\",\"指标3\"],"
    "\"falsification\":\"一条证伪触发：若X没发生/反向就认错\","
    "\"caveat\":\"多空与历史敏感度、非涨跌预测、不构成投资建议\"}"
)


def enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _catalog() -> str:
    """平台真实数据目录（精简版，压低输入 token→更快更省）：产业链→环节→真实 ticker + 实证传导。

    每层只保留前 3 个代表性 ticker、去掉 hook 长句——足够给 LLM 做 ticker 地基与传导约束，
    把喂进去的目录从 ~29KB 砍到 ~10KB，显著降低首字延迟与每次调用成本。
    """
    from .sectors import get_sectors
    cat = []
    for s in get_sectors().get("sectors", []):
        if not isinstance(s, dict):
            continue
        layers = []
        for l in (s.get("layers") or []):
            players = [{"t": p.get("ticker"), "n": p.get("name")}
                       for p in (l.get("players") or []) if p.get("ticker")][:3]
            if players or l.get("tightness") == "tight":
                layers.append({"layer": l.get("layer"), "tight": l.get("tightness"), "players": players})
        item = {"key": s.get("key"), "name": s.get("name"), "cat": s.get("category"),
                "layers": layers}
        t = s.get("transmission")
        if t:
            item["transmission"] = {
                "commodity": t["commodity"]["name"],
                "links": [{"name": x["name"], "rel": x["direction"], "r": x["r_change"]} for x in t["links"]],
            }
        cat.append(item)
    return json.dumps(cat, ensure_ascii=False)


@cached(86400)
def build_thesis(judgment: str) -> dict | None:
    """把判断拆成论点卡 JSON。未配置 key 或熔断 → None（端点据 ai_budget.status 给原因）。"""
    if not enabled():
        return None
    j = (judgment or "").strip()[:200]
    if not j:
        return None
    out = call_claude(
        MODEL, SYSTEM,
        f"用户判断：「{j}」\n\n【数据目录】(ticker 只能用这里出现的)：\n{_catalog()}\n\n"
        f"严格按系统要求只输出 JSON。",
        max_tokens=3000, timeout=110)
    text = (out or {}).get("text") or ""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:
        return None
    d["judgment"] = j
    return d
