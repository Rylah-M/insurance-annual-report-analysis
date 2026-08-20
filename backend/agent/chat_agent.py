"""后端薄壳:实际问答代码在 agents/qa-agent0820/code/chat_agent.py。"""

from __future__ import annotations

import sys
from pathlib import Path

_CODE_DIR = Path(__file__).resolve().parents[2] / "agents" / "qa-agent0820" / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from chat_agent import *  # noqa: E402,F401,F403
