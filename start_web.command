#!/usr/bin/env bash
# ============================================================
# 保险公司年报智能分析 - 一键启动
# 用法: Finder 双击本文件, 或在终端执行: bash start_web.command
# 说明: 自动启动 MinerU(8001) + 网页后端(8000), 完成后打开浏览器
# ============================================================
set -u

PROJECT="/Users/mowan/Documents/UI_0813"
PY="/Users/mowan/miniconda3/envs/annual_report/bin/python"
MINERU="/Users/mowan/miniconda3/envs/annual_report/bin/mineru-api"
LOG_DIR="$PROJECT/data/logs"
mkdir -p "$LOG_DIR"

echo "=========================================="
echo "  保险公司年报智能分析 - 一键启动"
echo "=========================================="

# 1. MinerU 解析服务 (8001)
if lsof -nP -iTCP:8001 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[OK] MinerU 已在运行 (8001)"
else
  echo "[..] 启动 MinerU 解析服务 (8001)..."
  nohup "$MINERU" --host 127.0.0.1 --port 8001 \
    >> "$LOG_DIR/mineru_api.log" 2>&1 &
fi

# 2. 网页后端 (8000)
if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[OK] 网页后端已在运行 (8000)"
else
  echo "[..] 启动网页后端 (8000)..."
  (
    cd "$PROJECT/backend" && nohup "$PY" -m uvicorn main:app \
      --host 0.0.0.0 --port 8000 \
      >> "$LOG_DIR/web_backend.log" 2>&1 &
  )
fi

# 3. 等待服务就绪(最多 60 秒)
echo "[..] 等待服务就绪..."
WEB=000
MIN=000
for _ in $(seq 1 60); do
  WEB=$(curl -s -m 2 -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null || echo 000)
  MIN=$(curl -s -m 2 -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/health 2>/dev/null || echo 000)
  if [ "$WEB" = "200" ] && [ "$MIN" = "200" ]; then
    break
  fi
  sleep 1
done

if [ "$WEB" = "200" ] && [ "$MIN" = "200" ]; then
  echo "[OK] 服务就绪, 正在打开网页..."
  open http://localhost:8000
else
  echo "[!!] 启动超时, 请查看日志:"
  echo "      $LOG_DIR/mineru_api.log"
  echo "      $LOG_DIR/web_backend.log"
fi

echo "=========================================="
echo "  网页地址: http://localhost:8000"
echo "=========================================="
