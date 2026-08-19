import csv
import json
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tag_utils import resolve_tag, resolve_chunk_file, OUTPUT_DIR, PROJECT_ROOT


# =========================
# 1. 文件路径（自动识别chunk标识）
# =========================

tag = resolve_tag()

extracted_file = os.path.join(OUTPUT_DIR, f"extracted_indicator_result_{tag}.json")

chunk_file = resolve_chunk_file()

output_dir = OUTPUT_DIR

database_dir = os.path.join(PROJECT_ROOT, "database_result")

database_file = os.path.join(database_dir, "database.csv")


# =========================
# 2. 数据库字段
# =========================

HEADERS = [
    "company_id",
    "company",
    "year",
    "report_period",
    "indicator_id",
    "indicator_name",
    "indicator_standard_name",
    "indicator_value",
    "unit",
    "business_scope",
    "business_type",
    "source_file",
    "source_page",
    "source_chunk_id",
    "source_text",
    "extraction_time",
    "confidence_score",
    "review_status",
]


DICTIONARY_ROWS = [
    ["field_name", "中文说明", "数据类型", "示例/枚举", "备注"],
    ["company_id", "公司唯一编码", "文本", "PICC_PC / PA_PC / CPIC_PC", "无法唯一推断时留空。"],
    ["company", "公司名称", "文本", "中国太保", "保留提取结果中的 company。"],
    ["year", "年份", "整数", "2024", "用于年度、半年度、季度数据归属年份。"],
    ["report_period", "报告期间", "文本", "2024FY / 2024H1 / 2024Q3", "由 chunks 文件中的 year 与 quarter 推断。"],
    ["indicator_id", "指标编号", "文本", "F006", "保持原指标编码体系。"],
    ["indicator_name", "原始指标名称", "文本", "综合成本率", "保留提取结果中的 indicator_name。"],
    ["indicator_standard_name", "标准化指标名称", "文本", "综合成本率", "默认与 indicator_name 一致。"],
    ["indicator_value", "指标值", "数字/文本", "97.1", "来自 extracted_indicator_result.json。"],
    ["unit", "单位", "文本", "% / 百万元", "来自 extracted_indicator_result.json。"],
    ["business_scope", "业务范围", "文本", "太保产险单体", "来自 extracted_indicator_result.json。"],
    ["business_type", "业务类型", "文本", "车险 / 非车险", "按指标名称简单推断；无法推断时留空。"],
    ["source_file", "来源文件", "文本", "chunks.json", "当前输入 chunks 文件名。"],
    ["source_page", "页码", "文本", "P56", "当前 chunks 未提供时留空。"],
    ["source_chunk_id", "来源 chunk 编号", "文本", "taibao_2024_q3_a_026", "按 source_text 在 chunks 中尽量匹配。"],
    ["source_text", "原文", "文本", "公司披露...", "来自 extracted_indicator_result.json。"],
    ["extraction_time", "提取时间", "日期", "2026-08-11", "生成数据库文件的日期。"],
    ["confidence_score", "置信度", "数字/文本", "0.99", "来自 extracted_indicator_result.json。"],
    ["review_status", "审核状态", "文本", "待审核", "默认待审核。"],
]


# =========================
# 3. 工具函数
# =========================

def load_json(file_path):

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def infer_report_period(chunks):

    if not chunks:
        return ""

    first_chunk = chunks[0]
    year = str(first_chunk.get("year", "")).strip()
    quarter = str(first_chunk.get("quarter", "")).strip()

    if year and quarter:
        return f"{year}{quarter}"

    return year


def infer_business_type(indicator_name):

    if "非车" in indicator_name or "非机动车" in indicator_name:
        return "非车险"

    if "车险" in indicator_name or "机动车" in indicator_name:
        return "车险"

    if "农业" in indicator_name or "农险" in indicator_name:
        return "农业险"

    if "健康" in indicator_name:
        return "健康险"

    return ""


def find_source_chunk(item, chunks):

    source_text = str(item.get("source_text", "")).strip()

    if not source_text:
        return "", ""

    compact_source_text = "".join(source_text.split())

    for chunk in chunks:

        chunk_text = (
            str(chunk.get("content", ""))
            +
            str(chunk.get("tables", ""))
        )

        compact_chunk_text = "".join(chunk_text.split())

        if source_text in chunk_text or compact_source_text in compact_chunk_text:
            return (
                chunk.get("chunk_id", ""),
                chunk.get("source_page", "")
                or chunk.get("page", "")
                or chunk.get("page_number", "")
            )

    return "", ""


def build_database_rows(extracted_results, chunks):

    source_file = Path(chunk_file).name
    report_period = infer_report_period(chunks)
    extraction_time = datetime.now().strftime("%Y-%m-%d")

    rows = []

    for item in extracted_results:

        source_chunk_id, source_page = find_source_chunk(item, chunks)
        indicator_name = item.get("indicator_name", "")

        rows.append(
            {
                "company_id": "",
                "company": item.get("company", ""),
                "year": item.get("year", ""),
                "report_period": report_period,
                "indicator_id": item.get("indicator_id", ""),
                "indicator_name": indicator_name,
                "indicator_standard_name": indicator_name,
                "indicator_value": item.get("indicator_value", ""),
                "unit": item.get("unit", ""),
                "business_scope": item.get("business_scope", ""),
                "business_type": infer_business_type(indicator_name),
                "source_file": source_file,
                "source_page": source_page,
                "source_chunk_id": source_chunk_id,
                "source_text": item.get("source_text", ""),
                "extraction_time": extraction_time,
                "confidence_score": item.get("confidence_score", ""),
                "review_status": "待审核",
            }
        )

    return rows


def dedupe_key(row):

    return (
        row.get("source_file", ""),
        str(row.get("company", "")),
        str(row.get("year", "")),
        str(row.get("report_period", "")),
        str(row.get("indicator_id", "")),
        str(row.get("indicator_name", "")),
    )


# =========================
# 4. CSV总库
# =========================

def update_database_csv(rows):

    database_path = Path(database_file)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    existing_rows = []

    if database_path.exists():
        with open(database_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)

    replacement_keys = {dedupe_key(row) for row in rows}

    kept_rows = [
        row
        for row in existing_rows
        if dedupe_key(row) not in replacement_keys
    ]

    final_rows = kept_rows + rows

    with open(database_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(final_rows)

    return database_path, len(existing_rows), len(final_rows)


# =========================
# 5. 轻量XLSX写入
# =========================

def column_letter(index):

    result = ""

    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result

    return result


def xml_text(value):

    if value is None:
        value = ""

    return escape(str(value), {'"': "&quot;"})


def build_sheet_xml(rows, column_widths):

    sheet_data = []

    for row_index, row in enumerate(rows, start=1):
        cells = []
        style_id = "1" if row_index == 1 else "0"

        for col_index, value in enumerate(row, start=1):
            cell_ref = f"{column_letter(col_index)}{row_index}"
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr" s="{style_id}">'
                f"<is><t>{xml_text(value)}</t></is>"
                f"</c>"
            )

        sheet_data.append(
            f'<row r="{row_index}">{"".join(cells)}</row>'
        )

    cols = []

    for index, width in enumerate(column_widths, start=1):
        cols.append(
            f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        )

    last_column = column_letter(max(len(row) for row in rows))
    last_row = len(rows)

    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
    <sheetViews>
        <sheetView workbookViewId="0">
            <pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
        </sheetView>
    </sheetViews>
    <cols>{"".join(cols)}</cols>
    <sheetData>{"".join(sheet_data)}</sheetData>
    <autoFilter ref="A1:{last_column}{last_row}"/>
</worksheet>'''


def write_xlsx(indicator_rows, output_excel_file):

    indicator_sheet_rows = [
        HEADERS,
        *[[row.get(header, "") for header in HEADERS] for row in indicator_rows],
    ]

    dictionary_sheet_rows = DICTIONARY_ROWS

    indicator_widths = [
        14, 24, 10, 14, 14, 22, 22, 16, 10,
        32, 16, 18, 12, 22, 60, 16, 16, 14
    ]
    dictionary_widths = [26, 28, 16, 30, 46]

    files = {
        "[Content_Types].xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
    <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
    <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
    <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
    <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
    <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>''',
        "_rels/.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
    <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
    <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>''',
        "xl/workbook.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
    <sheets>
        <sheet name="indicator_result" sheetId="1" r:id="rId1"/>
        <sheet name="dictionary" sheetId="2" r:id="rId2"/>
    </sheets>
</workbook>''',
        "xl/_rels/workbook.xml.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
    <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
    <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>''',
        "xl/styles.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
    <fonts count="2">
        <font><sz val="11"/><name val="Calibri"/></font>
        <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
    </fonts>
    <fills count="3">
        <fill><patternFill patternType="none"/></fill>
        <fill><patternFill patternType="gray125"/></fill>
        <fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill>
    </fills>
    <borders count="2">
        <border><left/><right/><top/><bottom/><diagonal/></border>
        <border>
            <left style="thin"><color rgb="FFD9E2F3"/></left>
            <right style="thin"><color rgb="FFD9E2F3"/></right>
            <top style="thin"><color rgb="FFD9E2F3"/></top>
            <bottom style="thin"><color rgb="FFD9E2F3"/></bottom>
            <diagonal/>
        </border>
    </borders>
    <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
    <cellXfs count="2">
        <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
        <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    </cellXfs>
    <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>''',
        "xl/worksheets/sheet1.xml": build_sheet_xml(indicator_sheet_rows, indicator_widths),
        "xl/worksheets/sheet2.xml": build_sheet_xml(dictionary_sheet_rows, dictionary_widths),
        "docProps/core.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:dcmitype="http://purl.org/dc/dcmitype/"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <dc:creator>Codex</dc:creator>
    <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
    <dcterms:created xsi:type="dcterms:W3CDTF">{datetime.now(timezone.utc).isoformat()}</dcterms:created>
    <dcterms:modified xsi:type="dcterms:W3CDTF">{datetime.now(timezone.utc).isoformat()}</dcterms:modified>
</cp:coreProperties>''',
        "docProps/app.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
    xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
    <Application>Codex</Application>
</Properties>''',
    }

    with zipfile.ZipFile(output_excel_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)


# =========================
# 6. 主程序
# =========================

def main():

    extracted_results = load_json(extracted_file)
    chunks = load_json(chunk_file)

    rows = build_database_rows(extracted_results, chunks)

    output_excel_file = (
        Path(output_dir)
        /
        f"indicator_database_{tag}.xlsx"
    )

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    write_xlsx(rows, output_excel_file)

    database_path, old_count, new_count = update_database_csv(rows)

    print("指标数据库Excel生成完成")
    print("输入提取结果:", extracted_file)
    print("输入chunks:", chunk_file)
    print("结果数量:", len(rows))
    print("Excel输出:", output_excel_file)
    print("CSV总库:", database_path)
    print("总库原记录数:", old_count)
    print("总库现记录数:", new_count)


if __name__ == "__main__":
    main()
