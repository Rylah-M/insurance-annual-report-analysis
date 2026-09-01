"""Run the standardexcel-agent as a subprocess and return the generated file."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = PROJECT_ROOT / "agents" / "standardexcel-agent0826"
MAIN_PY = AGENT_DIR / "main.py"


def generate_standardexcel_bytes(companies: list[str], years: list[int]) -> bytes:
    """Generate standardexcel.xlsx bytes for the selected companies and years."""
    cleaned_companies = [c.strip() for c in companies if c and c.strip()]
    cleaned_years = sorted({int(y) for y in years})
    if not cleaned_companies or not cleaned_years:
        raise ValueError("公司和年份不能为空")

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        output_path = Path(tmp.name)

    try:
        command = [
            sys.executable,
            str(MAIN_PY),
            "--companies",
            ",".join(cleaned_companies),
            "--years",
            ",".join(str(year) for year in cleaned_years),
            "--output",
            str(output_path),
        ]
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if process.returncode != 0:
            detail = (process.stderr or process.stdout or "").strip()
            raise RuntimeError(detail or "standardexcel 生成失败")
        return output_path.read_bytes()
    finally:
        try:
            output_path.unlink(missing_ok=True)
        except Exception:
            pass
