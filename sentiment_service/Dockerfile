# 情感微服务镜像：CPU torch + 英文 FinBERT(预热进镜像) + 中文 FinBERT2 微调头
FROM python:3.12-slim
WORKDIR /app

# 先装 CPU 版 torch，避免拉进上 GB 的 CUDA 依赖
RUN pip install --no-cache-dir "torch>=2.2" --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py models.py ./
# 中文 checkpoint（train_finbert2_zh.py 产物）。先跑训练再 build。
COPY finbert2-zh-sentiment ./finbert2-zh-sentiment
ENV ZH_MODEL_PATH=/app/finbert2-zh-sentiment
ENV HF_HOME=/app/.hf

# 把英文 ProsusAI/finbert 预下载进镜像，冷启动无需联网、加载即用
RUN python -c "from transformers import AutoModelForSequenceClassification, AutoTokenizer; \
m='ProsusAI/finbert'; AutoTokenizer.from_pretrained(m); AutoModelForSequenceClassification.from_pretrained(m)"

EXPOSE 8001
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8001}"]
