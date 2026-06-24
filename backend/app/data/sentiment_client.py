"""统一情感微服务客户端：英文 FinBERT / 中文 FinBERT2 打分，VADER+词典兜底。

跑着情感微服务（见 sentiment_service/，本地 8001 / 线上独立 fly app）时，
新闻情绪改由金融特化模型打分；服务不可用则返回 None，news_signal 自动回落，零影响。
"""
import os

import requests

from ..cache import cached

SENTIMENT_URL = os.environ.get("SENTIMENT_URL", "http://127.0.0.1:8001")


@cached(60)
def available() -> bool:
    try:
        r = requests.get(f"{SENTIMENT_URL}/health", timeout=2)
        return bool(r.json().get("ready"))
    except Exception:
        return False


def score_batch(texts: list[str], lang: str) -> dict[str, float] | None:
    """批量打分：返回 {文本: 分数([-1,1])}；该语言模型不可用或服务挂了返回 None。

    lang: 'en' | 'zh' | 'auto'
    """
    texts = [t for t in texts if t]
    if not texts or not available():
        return None
    try:
        r = requests.post(f"{SENTIMENT_URL}/sentiment",
                          json={"texts": texts, "lang": lang}, timeout=45)
        scores = r.json().get("scores")
        if not scores:
            return None
        # auto 模式下未命中模型的条目为 None，过滤掉
        return {t: s for t, s in zip(texts, scores) if s is not None}
    except Exception:
        return None
