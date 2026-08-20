"""后端薄壳:实际检索代码在 agents/qa-agent0820/code/chunk_index.py。"""

from __future__ import annotations

import sys
from pathlib import Path

_CODE_DIR = Path(__file__).resolve().parents[2] / "agents" / "qa-agent0820" / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from chunk_index import *  # noqa: E402,F401,F403
