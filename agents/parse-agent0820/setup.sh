#!/usr/bin/env bash
# parse_v1 一键环境安装脚本（目标电脑首次使用）
#
# 自动检测两种方式：
#   1) 有 conda            → 创建 conda 环境（Python 3.11）
#   2) 有 Python 3.10-3.13 → 在项目内创建 .venv 虚拟环境
#
# 用法：bash setup.sh
set -e

trap 'echo; echo "❌ 安装在第 $LINENO 行失败。"; echo "   如果错误是 Permission denied，通常是“没有写入权限”导致："; echo "   1) 确认把 parse_v1 解压到了自己的用户目录（如 ~/parse_v1），不要在系统目录里运行；"; echo "   2) 确认当前用户对 conda/Python 安装目录有写权限；"; echo "   3) 也可以改用下方 README 里的手动安装命令。"; echo "   请把上方完整报错输出发给维护者，便于定位。"; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_NAME="${PARSE_V1_ENV:-annual_report}"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -w "$SCRIPT_DIR" ]; then
    echo "❌ 当前目录没有写入权限：$SCRIPT_DIR"
    echo "   请把 parse_v1 解压到自己的用户目录（例如 ~/parse_v1）后重试。"
    exit 1
fi

# ---------- 定位 conda ----------
CONDA_SH=""
for cand in "$HOME/miniconda3/etc/profile.d/conda.sh" "$HOME/anaconda3/etc/profile.d/conda.sh"; do
    if [ -f "$cand" ]; then
        CONDA_SH="$cand"
        break
    fi
done
if [ -z "$CONDA_SH" ] && command -v conda >/dev/null 2>&1; then
    CONDA_BASE="$(conda info --base 2>/dev/null || true)"
    # Windows（Git Bash）下 conda 返回的是 C:\ 格式路径，转成 /c/ 格式
    if command -v cygpath >/dev/null 2>&1 && [ -n "$CONDA_BASE" ]; then
        CONDA_BASE="$(cygpath -u "$CONDA_BASE" 2>/dev/null || true)"
    fi
    if [ -n "$CONDA_BASE" ] && [ -f "$CONDA_BASE/etc/profile.d/conda.sh" ]; then
        CONDA_SH="$CONDA_BASE/etc/profile.d/conda.sh"
    fi
fi

# ---------- 选择安装方式 ----------
if [ -n "$CONDA_SH" ]; then
    echo "==> 检测到 conda，使用 conda 环境：${ENV_NAME}"
    source "$CONDA_SH"
    if conda env list | grep -qE "^\s*${ENV_NAME}\s"; then
        echo "==> 环境 ${ENV_NAME} 已存在，跳过创建"
    else
        echo "==> 1/4 创建 conda 环境 ${ENV_NAME}（Python 3.11）"
        conda create -n "$ENV_NAME" python=3.11 -y
    fi
    PYTHON="conda run -n $ENV_NAME python"
    PIP="conda run -n $ENV_NAME python -m pip"
    MODELS="conda run -n $ENV_NAME mineru-models-download"
    ACTIVATE_HINT="conda activate ${ENV_NAME}"
else
    echo "==> 未找到 conda，改用系统 Python + venv"
    PY_BIN="${PARSE_V1_PYTHON:-python3}"
    if ! command -v "$PY_BIN" >/dev/null 2>&1; then
        echo "❌ 未找到 python3，请先安装 Python 3.10-3.13：https://www.python.org"
        exit 1
    fi
    PY_VER="$("$PY_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    case "$PY_VER" in
        3.10|3.11|3.12|3.13) ;;
        *)
            echo "❌ 当前 Python 版本为 ${PY_VER}，MinerU 需要 3.10-3.13"
            exit 1
            ;;
    esac
    echo "==> 使用 Python ${PY_VER}，在项目内创建虚拟环境 .venv"
    "$PY_BIN" -m venv "$VENV_DIR"
    PYTHON="$VENV_DIR/bin/python"
    PIP="$VENV_DIR/bin/python -m pip"
    MODELS="$VENV_DIR/bin/mineru-models-download"
    ACTIVATE_HINT="source ${VENV_DIR}/bin/activate"
fi

echo "==> 安装依赖（streamlit / requests）"
"$PIP" install --upgrade pip
"$PIP" install -r "$SCRIPT_DIR/requirements.txt"

echo "==> 安装开源解析引擎 MinerU"
"$PIP" install mineru

echo "==> 下载 MinerU 模型（约 1-2 GB）"
echo "    （如无法访问 HuggingFace，请先执行：export MINERU_MODEL_SOURCE=modelscope）"
"$MODELS"

echo
echo "✅ 安装完成。使用方法："
echo "   1) 启动解析服务：  ./start_mineru_api.sh"
echo "   2) 启动界面：      先激活环境（${ACTIVATE_HINT}），再执行 streamlit run app.py"
echo "   3) 浏览器打开：    http://localhost:8501"
