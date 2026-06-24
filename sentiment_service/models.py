"""情感模型加载与打分：英文 ProsusAI/finbert，中文 FinBERT2 微调头。

懒加载：进程启动不阻塞，首个请求触发加载并缓存。纯 CPU 推理即可。
分数约定：返回 [-1, 1]，= Σ Pᵢ·polarityᵢ（正 +1 / 负 -1 / 中性 0）的期望极性，
比离散三分类更细腻，下游 news_signal 直接当 text_override 用。
"""
import os
import threading

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# 英文：开箱即用的三分类金融情感模型
EN_MODEL_ID = os.environ.get("EN_MODEL_ID", "ProsusAI/finbert")
# 中文：本地微调出的 FinBERT2 情感头目录。不存在 → 中文不可用，后端回落中文词典。
ZH_MODEL_PATH = os.environ.get("ZH_MODEL_PATH", "/app/finbert2-zh-sentiment")

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MAX_LEN = int(os.environ.get("SENTIMENT_MAX_LEN", "256"))

_lock = threading.Lock()
_models: dict[str, tuple | None] = {}  # "en"/"zh" -> (tokenizer, model, polarity_by_id) | None


def _polarity(label) -> float:
    """标签文本 → 极性。兼容英文/中文/数字标签命名。"""
    s = str(label).lower()
    if any(k in s for k in ("pos", "正", "利好", "bull", "看多")):
        return 1.0
    if any(k in s for k in ("neg", "负", "利空", "bear", "看空")):
        return -1.0
    return 0.0  # neutral / 中性 / 其它


def _load(path_or_id: str):
    tok = AutoTokenizer.from_pretrained(path_or_id)
    model = AutoModelForSequenceClassification.from_pretrained(path_or_id)
    model.eval().to(DEVICE)
    pol = {int(i): _polarity(l) for i, l in model.config.id2label.items()}
    return tok, model, pol


def _ensure(name: str):
    if name in _models:
        return _models[name]
    with _lock:
        if name in _models:  # 双重检查，避免并发重复加载
            return _models[name]
        try:
            if name == "en":
                _models[name] = _load(EN_MODEL_ID)
            elif name == "zh":
                _models[name] = _load(ZH_MODEL_PATH) if os.path.isdir(ZH_MODEL_PATH) else None
            else:
                _models[name] = None
        except Exception:
            _models[name] = None
        return _models[name]


@torch.no_grad()
def score(name: str, texts: list[str]) -> list[float] | None:
    """对一组文本打分。模型不可用返回 None（让后端回落）。"""
    m = _ensure(name)
    if not m or not texts:
        return None
    tok, model, pol = m
    enc = tok(texts, padding=True, truncation=True,
              max_length=MAX_LEN, return_tensors="pt").to(DEVICE)
    probs = torch.softmax(model(**enc).logits, dim=-1).cpu().tolist()
    return [round(sum(p * pol[i] for i, p in enumerate(row)), 4) for row in probs]


_CJK = tuple(range(0x4E00, 0x9FFF + 1))


def _is_cjk(s: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in s)


def score_lang(lang: str, texts: list[str]) -> list[float] | None:
    """lang: 'en' | 'zh' | 'auto'（按字符自动路由）。"""
    if lang in ("en", "zh"):
        return score(lang, texts)
    # auto：按语言分桶后各自打分，再按原顺序拼回
    out: list[float | None] = [None] * len(texts)
    buckets = {"en": [], "zh": []}
    for i, t in enumerate(texts):
        buckets["zh" if _is_cjk(t) else "en"].append((i, t))
    for name, pairs in buckets.items():
        if not pairs:
            continue
        s = score(name, [t for _, t in pairs])
        if s is None:
            continue
        for (idx, _), val in zip(pairs, s):
            out[idx] = val
    return out


def status(name: str) -> str:
    """供 /health 报告：loaded / unavailable / configured（未加载但可加载）。"""
    if name in _models:
        return "loaded" if _models[name] else "unavailable"
    if name == "zh":
        return "configured" if os.path.isdir(ZH_MODEL_PATH) else "unavailable"
    return "configured"  # en 远程模型，首个请求时加载
