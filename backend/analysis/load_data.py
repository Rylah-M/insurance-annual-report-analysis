from __future__ import annotations

from pathlib import Path

import pandas as pd

from data_loader import load_database


def load_data(path: str | Path | None = None) -> pd.DataFrame:
    return load_database(str(path) if path else None)
