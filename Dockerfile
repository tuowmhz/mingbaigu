# 多阶段构建：前端打包 → 单一 Python 容器（FastAPI 伺服 API + 静态页）
FROM node:22-slim AS frontend
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/tests ./tests
COPY --from=frontend /fe/dist ./frontend/dist
RUN mkdir -p /app/data
# A股策略账本作为「种子」打进镜像的非卷路径（/app/data 是持久卷会遮盖镜像同名目录）。
# 服务器读「卷 ∪ 种子」并集；月度新增条目随每次部署带上来。
COPY backend/data/ashare_strategy ./app/quant/ashare/_seed_ledger
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
