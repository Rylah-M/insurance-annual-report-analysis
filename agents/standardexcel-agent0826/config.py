"""Configuration for the standardexcel-agent.

The agent generates a peer-comparison workbook from:
1. database/database_result.csv
2. indicator_metadata.xlsx (analysis rules)
3. indicator_dictionary.xlsx (indicator definitions)
"""

from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = AGENT_DIR.parents[1]

DATABASE_PATH = PROJECT_ROOT / "database" / "database_result.csv"
INDICATOR_METADATA_PATH = AGENT_DIR / "indicator_metadata.xlsx"
INDICATOR_DICTIONARY_PATH = (
    PROJECT_ROOT / "agents" / "zd-agent0811" / "indicator" / "indicator_dictionary.xlsx"
)
OUTPUT_DIR = AGENT_DIR / "output"
OUTPUT_FILE = OUTPUT_DIR / "standardexcel.xlsx"

# All report periods covered by the workbook: 2022-2026, Q2 and Q4 of each year.
PERIODS = [
    "2022Q2",
    "2022Q4",
    "2023Q2",
    "2023Q4",
    "2024Q2",
    "2024Q4",
    "2025Q2",
    "2025Q4",
    "2026Q2",
    "2026Q4",
]

# Only property-insurance scopes take part in the comparison.
ALLOWED_SCOPE_TYPES = {"财险口径", "特殊财险口径"}
EXCLUDED_SCOPE_TYPES = {"集团口径"}

# Company row order. 阳光 is intentionally kept last.
COMPANY_ORDER = ["人保", "太保", "平安", "大地", "太平", "众安", "阳光"]
COMPANY_DISPLAY_NAMES = {
    "人保": "人保",
    "太保": "太保",
    "平安": "平安",
    "大地": "大地",
    "太平": "太平",
    "众安": "众安（产险业务）",
    "阳光": "阳光",
}

TOTAL_ROW_LABEL = "所有上市公司合计"

# indicator_metadata.indicator_category -> workbook sheet name.
CATEGORY_SHEETS = [
    ("盈利能力指标", "盈利能力对比"),
    ("业务规模指标", "业务规模对比"),
    ("经营效率指标", "经营效率对比"),
    ("风险管理指标", "偿付能力对比"),
]

CATEGORY_ANGLES = {
    "盈利能力对比": "盈利能力",
    "业务规模对比": "业务规模",
    "经营效率对比": "经营效率",
    "偿付能力对比": "偿付能力",
}

FORMAT_AMOUNT = "#,##0.00"
FORMAT_PERCENT = '0.0"%"'
