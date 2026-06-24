#!/bin/bash
# 一键启动 StockPrediction（后端 8000 + 前端 5173）
set -e
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3.12}"

# 后端环境
if [ ! -f backend/.venv/bin/uvicorn ]; then
  echo "[1/3] 创建后端环境并安装依赖…"
  "$PYTHON" -m venv backend/.venv
  backend/.venv/bin/pip install -q -r backend/requirements.txt
else
  echo "[1/3] 后端环境已就绪"
fi

# 前端依赖
if [ ! -d frontend/node_modules ]; then
  echo "[2/3] 安装前端依赖…"
  (cd frontend && npm install --silent)
else
  echo "[2/3] 前端依赖已就绪"
fi

echo "[3/3] 启动服务…（Ctrl+C 同时停止两者）"
trap 'kill 0' EXIT
(cd backend && .venv/bin/uvicorn app.main:app --port 8000 --log-level warning) &
(cd frontend && npm run dev --silent) &
sleep 2
echo ""
echo "✅ 打开 http://localhost:5173"
wait
