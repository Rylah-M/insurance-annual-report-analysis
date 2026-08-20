#!/usr/bin/env bash
# ============================================================
# parse_v1 一键启动（MinerU 解析服务 + Web 界面）
# 用法：
#   1) Finder 里双击本文件（.command，macOS）
#   2) 或在终端执行：bash start.command
# 服务以后台方式运行，日志保存在 data/logs/ 下
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 自动定位项目目录（兼容桌面快捷方式等任意位置的启动器副本）
if [ ! -f "$SCRIPT_DIR/start_mineru_api.sh" ]; then
    for cand in \
        "$SCRIPT_DIR/parse-agent0820" \
        "$HOME/Desktop/parse-agent0820" \
        "$HOME/parse-agent0820" \
        "$HOME/Documents/parse-agent0820"; do
        if [ -f "$cand/start_mineru_api.sh" ]; then
            SCRIPT_DIR="$cand"
            break
        fi
    done
fi

if [ ! -f "$SCRIPT_DIR/start_mineru_api.sh" ]; then
    echo "❌ 找不到 parse_v1 项目目录（缺少 start_mineru_api.sh）"
    echo "   请把本启动器放回项目文件夹内，或双击项目里的 start.command"
    read -p "按回车键关闭窗口..." _
    exit 1
fi

cd "$SCRIPT_DIR"
mkdir -p data/logs

ENV_NAME="${PARSE_V1_ENV:-annual_report}"
CONDA_BASE="${CONDA_BASE:-$HOME/miniconda3}"
if [ ! -d "$CONDA_BASE" ]; then
    CONDA_BASE="$HOME/anaconda3"
fi
STREAMLIT_BIN="$CONDA_BASE/envs/$ENV_NAME/bin/streamlit"

if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "✔ MinerU 解析服务已在运行（8000 端口）"
else
    echo "▶ 启动 MinerU 解析服务..."
    nohup bash "$SCRIPT_DIR/start_mineru_api.sh" > "$SCRIPT_DIR/data/logs/mineru_api.log" 2>&1 &
fi

if lsof -nP -iTCP:8501 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "✔ Web 界面已在运行（8501 端口）"
else
    echo "▶ 启动 Web 界面..."
    if [ -x "$STREAMLIT_BIN" ]; then
        nohup "$STREAMLIT_BIN" run "$SCRIPT_DIR/app.py" \
            --server.headless true --server.port 8501 \
            > "$SCRIPT_DIR/data/logs/streamlit.log" 2>&1 &
    else
        echo "  未找到 $STREAMLIT_BIN，尝试通过 conda 启动..."
        nohup conda run -n "$ENV_NAME" streamlit run "$SCRIPT_DIR/app.py" \
            --server.headless true --server.port 8501 \
            > "$SCRIPT_DIR/data/logs/streamlit.log" 2>&1 &
    fi
fi

echo ""
echo "正在等待服务就绪..."
for _ in $(seq 1 30); do
    API_OK=$(curl -s -m 2 -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health 2>/dev/null || echo 000)
    UI_OK=$(curl -s -m 2 -o /dev/null -w "%{http_code}" http://127.0.0.1:8501 2>/dev/null || echo 000)
    if [ "$API_OK" = "200" ] && [ "$UI_OK" = "200" ]; then
        break
    fi
    sleep 1
done

if [ "$API_OK" = "200" ] && [ "$UI_OK" = "200" ]; then
    echo ""
    echo "✅ 解析服务：http://127.0.0.1:8000"
    echo "✅ Web 界面：http://localhost:8501"
    echo "（日志：data/logs/mineru_api.log、data/logs/streamlit.log）"
    open http://localhost:8501 2>/dev/null || true
    sleep 3
else
    echo ""
    echo "❌ 服务启动失败，最近日志："
    echo "---- mineru_api.log ----"
    tail -5 "$SCRIPT_DIR/data/logs/mineru_api.log" 2>/dev/null || true
    echo "---- streamlit.log ----"
    tail -5 "$SCRIPT_DIR/data/logs/streamlit.log" 2>/dev/null || true
    read -p "按回车键关闭窗口..." _
    exit 1
fi
