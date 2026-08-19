#!/usr/bin/env bash
# 启动 MinerU 本地 API 服务（外部依赖，需保持窗口运行）
# 自动选择运行环境：项目内 .venv（系统 Python）或 conda 环境
# 用法：./start_mineru_api.sh
set -e

ENV_NAME="${PARSE_V1_ENV:-annual_report}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 服务输出统一写到 parse_v1/data/mineru_api_output，避免污染项目 output/
export MINERU_API_OUTPUT_ROOT="$SCRIPT_DIR/data/mineru_api_output"
# 每批处理页数调小（默认 64），降低单批内存峰值，避免低内存时子进程崩溃（Broken pipe）
export MINERU_PROCESSING_WINDOW_SIZE="${MINERU_PROCESSING_WINDOW_SIZE:-32}"

# 方式一：项目内 venv（通过 setup.sh 用系统 Python 创建）
if [ -x "$SCRIPT_DIR/.venv/bin/mineru-api" ]; then
    exec "$SCRIPT_DIR/.venv/bin/mineru-api" --host 127.0.0.1 --port 8000
fi

# 方式二：conda 环境
CONDA_SH=""
for cand in "$HOME/miniconda3/etc/profile.d/conda.sh" "$HOME/anaconda3/etc/profile.d/conda.sh"; do
    if [ -f "$cand" ]; then
        CONDA_SH="$cand"
        break
    fi
done
if [ -z "$CONDA_SH" ] && command -v conda >/dev/null 2>&1; then
    CONDA_BASE="$(conda info --base 2>/dev/null || true)"
    # Windows（Git Bash）下把 C:\ 格式路径转成 /c/ 格式
    if command -v cygpath >/dev/null 2>&1 && [ -n "$CONDA_BASE" ]; then
        CONDA_BASE="$(cygpath -u "$CONDA_BASE" 2>/dev/null || true)"
    fi
    if [ -n "$CONDA_BASE" ] && [ -f "$CONDA_BASE/etc/profile.d/conda.sh" ]; then
        CONDA_SH="$CONDA_BASE/etc/profile.d/conda.sh"
    fi
fi
if [ -n "$CONDA_SH" ]; then
    source "$CONDA_SH"
    conda activate "$ENV_NAME"
    exec mineru-api --host 127.0.0.1 --port 8000
fi

echo "❌ 未找到可用的解析环境。请先运行 bash setup.sh 完成安装（需要 conda 或 Python 3.10-3.13）"
exit 1
