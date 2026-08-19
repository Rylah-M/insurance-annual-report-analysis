import os
import sys
import glob


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHUNK_DIR = os.path.join(PROJECT_ROOT, "chunk")

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")


def newest_chunk_file():
    """返回 chunk 目录中最新修改的 *_chunks.json"""
    files = sorted(
        glob.glob(os.path.join(CHUNK_DIR, "*_chunks.json")),
        key=os.path.getmtime,
        reverse=True
    )
    if not files:
        raise FileNotFoundError(
            f"chunk 目录中没有找到 *_chunks.json 文件: {CHUNK_DIR}"
        )
    return files[0]


def resolve_tag():
    """
    输出标识规则：
    1. 命令行第一个参数指定（如 python chunk_rerank.py 中国人保_2025_Q4_A股）；
    2. 否则取 chunk 目录中最新 *_chunks.json 的文件名标识。
    """
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.endswith(".json"):
            arg = arg.replace("_chunks.json", "")
        return os.path.basename(arg)
    return os.path.basename(newest_chunk_file()).replace("_chunks.json", "")


def resolve_chunk_file():
    """
    返回本次要处理的 chunk 文件路径：
    1. 命令行第一个参数为 *_chunks.json 路径（绝对/相对均可）时直接使用；
    2. 否则使用 chunk 目录下最新的 *_chunks.json。
    """
    if len(sys.argv) > 1 and sys.argv[1].endswith("_chunks.json"):
        arg = sys.argv[1]
        if os.path.exists(arg):
            return arg
        return os.path.join(CHUNK_DIR, arg)
    return newest_chunk_file()
