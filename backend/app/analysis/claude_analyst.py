"""Claude 深度解读插槽：把平台全部结构化分析喂给 Claude，产出真正的深度人话研报。

启用方式：export ANTHROPIC_API_KEY=sk-ant-...（fly secrets set 同理）。
未配置时本模块完全静默——规则版"一页看懂"继续工作，零影响。

成本控制：默认 claude-sonnet-4-6，每只股票每天最多生成一次（缓存 24h），
单篇约 1500 输出 token ≈ $0.02-0.03/股/天；全部调用走 ai_budget 电表，
当日累计费用触到 AI_DAILY_BUDGET_USD（默认 $1）后自动熔断、降级到规则版。
"""
import json
import os

from ..ai_budget import call_claude
from ..cache import cached

MODEL = os.environ.get("CLAUDE_ANALYST_MODEL", "claude-sonnet-4-6")

SYSTEM = (
    "你是「明白股」的首席分析师。用户是普通散户，你的任务是把结构化分析数据写成"
    "一篇 400-600 字的深度但极易读的中文分析。纪律："
    "1) 必须有一个贯穿全文的比喻或故事钩子；"
    "2) 深度来自'把数字之间的因果讲出来'，不是堆砌数字；"
    "3) 必须诚实：模型没有优势就直说，风险写具体（最大回撤意味着什么）；"
    "4) 结尾给一段'如果你是三种人'（长线/波段/还没买）各一句话视角，但绝不给具体买卖指令；"
    "5) 不用'综上所述'这类套话，像聪明朋友聊天那样写。"
)


def enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


@cached(86400)
def deep_analysis(ticker: str, context_json: str) -> dict | None:
    """context_json 为平台结构化分析的紧凑摘要（缓存键含内容指纹的日期粒度由调用方控制）。

    只缓存成功结果；失败（含预算熔断）返回 None，下次请求自动重试，
    具体原因由端点查 ai_budget.status() 给出。
    """
    if not enabled():
        return None
    out = call_claude(
        MODEL, SYSTEM,
        f"以下是 {ticker} 的全部结构化分析数据，写出深度人话分析：\n{context_json}",
        max_tokens=1500, timeout=60)
    return out if out.get("text") else None


def build_context(detail: dict) -> str:
    """从 /api/stock 的完整响应里提取喂给 Claude 的紧凑上下文。"""
    keep = {
        "ticker": detail.get("ticker"),
        "name": detail.get("name_cn"),
        "quote": detail.get("quote"),
        "fundamentals": detail.get("fundamentals"),
        "risk": detail.get("risk"),
        "judge": (detail.get("adversarial") or {}).get("judge"),
        "bull_case": [a["text"] for a in (detail.get("adversarial") or {}).get("bull_case", [])][:5],
        "bear_case": [a["text"] for a in (detail.get("adversarial") or {}).get("bear_case", [])][:5],
        "news_signal": (detail.get("news") or {}).get("signal"),
        "top_news": [i["title"] for i in (detail.get("news") or {}).get("items", [])[:8]],
        "prediction_backtest": (detail.get("prediction") or {}).get("backtest"),
        "insider_judge": ((detail.get("insider") or {}).get("summary") or {}).get("judge"),
        "events": detail.get("events"),
    }
    return json.dumps(keep, ensure_ascii=False)
