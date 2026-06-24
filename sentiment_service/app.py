"""情感微服务：英文 FinBERT / 中文 FinBERT2，给主站 news_signal 调用。

本地：  uvicorn app:app --port 8001
线上：  独立 fly app，空闲休眠省钱（见 fly.toml）。服务挂了主站自动回落词典。
"""
from fastapi import FastAPI
from pydantic import BaseModel

import models

app = FastAPI(title="StockPrediction Sentiment Service")


class Req(BaseModel):
    texts: list[str]
    lang: str = "auto"  # en | zh | auto


@app.get("/health")
def health():
    return {
        "ready": True,
        "device": models.DEVICE,
        "en": models.status("en"),
        "zh": models.status("zh"),
    }


@app.post("/sentiment")
def sentiment(req: Req):
    """返回每条文本的情感分 [-1,1]；对应模型不可用时该语言返回 null。"""
    return {"scores": models.score_lang(req.lang, req.texts), "lang": req.lang}
