"""更新指标字典:新增分险种指标 + 修正非车非保证险保费描述(全表重建)。"""

from __future__ import annotations

import openpyxl


PATH = "agents/zd-agent0811/indicator/indicator_dictionary.xlsx"
SRC_PRIORITY = "经营情况分析|分部信息|主要险种经营信息|分险种信息"

ORIGINAL_IDS = {
    "F001", "F002", "F003", "F004", "F005", "F006", "F007", "F008", "F009", "F010",
    "B001", "B002", "B003", "B004", "B005", "B006", "B007", "B008", "B010",
    "B011", "B012", "B013", "B014", "B015", "B016", "B017",
    "R001", "R002", "R003",
}

# 针对既有行的关键词补充(众安/港式口径用词),幂等追加
KEYWORD_PATCHES = {
    "F001": ["淨溢利", "溢利", "歸屬於母公司股東的淨溢利", "淨利潤"],
    "F002": ["承保溢利", "承保溢利/(虧損)", "承保溢利(虧損)"],
    "B001": ["總保費", "总保费", "保费总额"],
    "B002": ["汽車生態總保費", "車險總保費", "汽车生态总保费", "车险总保费"],
    "B005": [],
    "B006": ["健康生態總保費", "健康生态总保费"],
    "B010": ["總保費同比", "保費同比增長", "同比變動", "总保费同比", "保费同比"],
    "B011": ["汽車生態保險服務收入", "汽车生态保险服务收入", "汽車保險保險服務收入", "汽车保险保险服务收入"],
    "F009": ["汽車生態綜合成本率", "汽车生态综合成本率"],
}

# 针对既有行的关键词剔除:
# - 去掉会把"意外伤害及健康保险(意健险)"合并披露误匹配到单独"意外险/健康险"的合并词;
# - 健康险去掉寿险口径的"长期/短期健康险"词。
KEYWORD_REMOVE = {
    "B006": [
        "健康险", "健康保險", "健康險", "健康保险",
        "意外伤害及健康保险", "意外伤害及健康险", "意外伤害和健康保险", "意外健康险",
        "意外险及健康险", "意健险",
        "意外傷害及健康保險", "意外傷害及健康險", "意外健康險", "意外險及健康險", "意健險",
        "长期健康险", "长期健康保险", "短期健康险", "短期健康保险",
        "長期健康險", "長期健康保險", "短期健康險", "短期健康保險",
    ],
    "B014": [
        "意外险", "意外险业务", "意外伤害险", "意外伤害", "意外傷害", "意外險",
        "意外伤害及健康保险", "意外伤害及健康险", "意外伤害和健康保险", "意外健康险",
        "意外险及健康险", "意健险",
        "意外傷害及健康保險", "意外傷害及健康險", "意外健康險", "意外險及健康險", "意健險",
    ],
}

# (显示名, 全称, 短称, 英文, 繁体全称, 繁体短称)
LINES = [
    ("车险", "车险", "机动车辆保险", "motor", "車險", "機動車輛保險"),
    ("非车险", "非车险", "非机动车辆保险", "non-motor", "非車險", "非機動車輛保險"),
    ("农险", "农业保险", "农险", "agricultural", "農業保險", "農險"),
    ("健康险", "健康险", "健康保险", "health", "健康險", "健康保險"),
    ("责任险", "责任保险", "责任险", "liability", "責任保險", "責任險"),
    ("意外险", "意外伤害保险", "意外险", "accident", "意外傷害保險", "意外險"),
    ("企财险", "企业财产保险", "企财险", "commercial property", "企業財產保險", "企財險"),
    ("保证险", "保证保险", "保证险", "guarantee", "保證保險", "保證險"),
    ("货运险", "货物运输保险", "货运险", "cargo transportation", "貨物運輸保險", "貨運險"),
    ("新能源车险", "新能源车险", "新能源车", "new energy vehicle", "新能源車險", "新能源車"),
]


def kw_metric(full: str, short: str, en: str, tf: str, ts: str, metric: str, metric_tw: str, en_metric: str) -> list[str]:
    kws = [
        f"{full}{metric}",
        f"{short}{metric}",
        f"{full}业务{metric}",
        f"{short}业务{metric}",
    ]
    if metric in ("保费", "保险服务收入", "保险服务费用"):
        kws += [f"{full}{metric}合计", f"{short}{metric}合计"]
    if metric == "保费":
        kws += [
            f"{full}{metric}收入", f"{short}{metric}收入",
            f"{full}原保险保费收入", f"{short}原保险保费收入",
            f"{full}原保费收入", f"{short}原保费收入",
        ]
    kws += [
        f"{tf}{metric_tw}", f"{ts}{metric_tw}",
        f"{tf}業務{metric_tw}", f"{ts}業務{metric_tw}",
        f"{en} {en_metric}",
    ]
    return kws


def join(items: list[str]) -> str:
    return "|".join(item for item in items if item)


def patch_keywords(row: list, extra: list[str]) -> None:
    existing = [x for x in str(row[4]).split("|") if x]
    for term in extra:
        if term not in existing:
            existing.append(term)
    row[4] = "|".join(existing)


def remove_keywords(row: list, drop: list[str]) -> None:
    existing = [x for x in str(row[4]).split("|") if x]
    row[4] = "|".join(x for x in existing if x not in drop)


def main() -> None:
    wb = openpyxl.load_workbook(PATH)
    ws = wb["indicator_dictionary"]

    # 读取现有行(仅保留原始 29 行,其中 B004 之后单独修正)
    original = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] in ORIGINAL_IDS:
            original.append(list(row))
    for row in original:
        if row[0] in KEYWORD_PATCHES:
            patch_keywords(row, KEYWORD_PATCHES[row[0]])
        if row[0] in KEYWORD_REMOVE:
            remove_keywords(row, KEYWORD_REMOVE[row[0]])

    new_rows: list[list] = []

    # ---- 保险服务费用 (业务规模指标) B018-B027 ----
    for idx, (display, full, short, en, tf, ts) in enumerate(LINES, start=18):
        kws = kw_metric(full, short, en, tf, ts, "保险服务费用", "保險服務費用", "insurance service expenses")
        new_rows.append([
            f"B{idx:03d}", "业务规模指标", f"{display}保险服务费用",
            f"{full}保险服务费用|{short}保险服务费用|{en} insurance service expenses",
            join(kws),
            f"{full}业务确认的保险服务费用(IFRS 17 口径)。",
            "百万元", "number",
            "按年报分险种披露口径提取;未单独披露该险种保险服务费用则不提取。",
            SRC_PRIORITY,
        ])

    # ---- 保险服务收入 (业务规模指标, 补齐车险/非车险之外的险种) B028-B035 ----
    for idx, (display, full, short, en, tf, ts) in enumerate(LINES[2:], start=28):
        kws = kw_metric(full, short, en, tf, ts, "保险服务收入", "保險服務收入", "insurance service revenue")
        new_rows.append([
            f"B{idx:03d}", "业务规模指标", f"{display}保险服务收入",
            f"{full}保险服务收入|{short}保险服务收入|{en} insurance service revenue",
            join(kws),
            f"{full}业务确认的保险服务收入(IFRS 17 口径)。",
            "百万元", "number",
            "按年报分险种披露口径提取;未单独披露该险种保险服务收入则不提取。",
            SRC_PRIORITY,
        ])

    # ---- 新能源车险保费收入 B036 ----
    full, short, en, tf, ts = "新能源车险", "新能源车", "new energy vehicle", "新能源車險", "新能源車"
    kws = kw_metric(full, short, en, tf, ts, "保费", "保費", "premiums")
    new_rows.append([
        "B036", "业务规模指标", "新能源车险保费收入",
        "新能源车险原保险保费收入|新能源汽车保险保费|new energy vehicle premiums",
        join(kws + ["新能源汽车保险保费", "新能源车险原保费", "新能源車險總保費", "新能源車險佔比", "新能源車險保費佔比", "新能源车险总保费", "新能源车险占比"]),
        "新能源车险(新能源汽车保险)业务的原保险保费收入。仅在公司披露新能源车险/新能源汽车保险数据时提取;未披露不得提取,严禁与整体车险指标混淆。",
        "百万元", "number",
        "按年报披露的'新能源车险/新能源汽车保险'保费提取;若未单独披露绝对金额,但披露了占车险保费比例或同比增速,则提取比例/增速并注明口径;严禁用整体车险保费代替。",
        SRC_PRIORITY,
    ])

    # ---- 意健险(意外伤害及健康保险)合并口径 B037-B039 ----
    yj_full, yj_short, yj_en, yj_tf, yj_ts = (
        "意外伤害及健康保险", "意健险", "accident & health",
        "意外傷害及健康保險", "意健險",
    )
    yj_note = (
        "仅当年报将意外伤害保险与健康保险按'意外伤害及健康保险/意健险'合并口径披露时提取;"
        "若两者分别披露,请分别提取到'意外险''健康险'指标下,本合并指标留空。"
    )
    for bidx, metric, metric_tw, en_metric, name_suffix in [
        (37, "保费", "保費", "premiums", "保费收入"),
        (38, "保险服务收入", "保險服務收入", "insurance service revenue", "保险服务收入"),
        (39, "保险服务费用", "保險服務費用", "insurance service expenses", "保险服务费用"),
    ]:
        kws = kw_metric(yj_full, yj_short, yj_en, yj_tf, yj_ts, metric, metric_tw, en_metric)
        new_rows.append([
            f"B{bidx:03d}", "业务规模指标", f"意健险{name_suffix}",
            f"{yj_full}{metric}|{yj_short}{metric}|{yj_en} {en_metric}",
            join(kws + [f"{yj_tf}{metric_tw}", f"{yj_ts}{metric_tw}"]),
            f"{yj_full}(意健险)业务合并披露口径的{metric}。{yj_note}",
            "百万元", "number",
            f"按'意外伤害及健康保险/意健险'合并口径提取;若分别披露意外伤害保险与健康保险,本指标留空。",
            SRC_PRIORITY,
        ])

    # ---- 意健险承保利润 F029 / 综合成本率 F030 ----
    for fmetric, category, fname, unit, dtype in [
        ("承保利润", "盈利能力指标", "意健险承保利润", "百万元", "number"),
        ("综合成本率", "承保质量指标", "意健险综合成本率", "%", "percentage"),
    ]:
        kws = kw_metric(
            yj_full, yj_short, yj_en, yj_tf, yj_ts,
            fmetric, "承保利潤" if "承保" in fmetric else "綜合成本率",
            "underwriting profit" if "承保" in fmetric else "combined ratio",
        )
        new_rows.append([
            f"F{29 if fmetric == '承保利润' else 30:03d}", category, fname,
            f"{yj_full}{fmetric}|{yj_short}{fmetric}|{yj_short}COR" if "成本" in fmetric else f"{yj_full}{fmetric}|{yj_short}{fmetric}",
            join(kws),
            f"{yj_full}(意健险)业务合并披露口径的{fmetric}。{yj_note}",
            unit, dtype,
            f"按'意外伤害及健康保险/意健险'合并口径提取;若分别披露意外伤害保险与健康保险,本指标留空。",
            SRC_PRIORITY,
        ])

    # ---- 承保利润 (盈利能力指标) F011-F020 ----
    for idx, (display, full, short, en, tf, ts) in enumerate(LINES, start=11):
        kws = kw_metric(full, short, en, tf, ts, "承保利润", "承保利潤", "underwriting profit")
        if "新能源" in full:
            note = "仅在公司披露新能源车险/新能源汽车保险相关承保利润时提取;未披露不得提取,严禁与整体车险承保利润混淆。"
            calc = "按年报分险种披露口径提取;新能源车险须单独披露,否则不得提取。"
        else:
            note = ""
            calc = "按年报分险种披露口径提取;未披露则不提取。"
        definition = f"{full}业务承保端形成的利润或亏损。" + (f"{note}" if note else "")
        new_rows.append([
            f"F{idx:03d}", "盈利能力指标", f"{display}承保利润",
            f"{full}承保利润|{short}承保利润|{en} underwriting profit",
            join(kws + [f"{full}承保经营利润", f"{short}承保经营利润"]),
            definition,
            "百万元", "number", calc, SRC_PRIORITY,
        ])

    # ---- 综合成本率 (承保质量指标, 补齐车险/非车险之外的险种) F021-F028 ----
    for idx, (display, full, short, en, tf, ts) in enumerate(LINES[2:], start=21):
        kws = kw_metric(full, short, en, tf, ts, "综合成本率", "綜合成本率", "combined ratio")
        if "新能源" in full:
            note = "仅在公司披露新能源车险/新能源汽车保险综合成本率时提取;未披露不得提取,严禁与整体车险综合成本率混淆。"
            calc = "按年报分险种披露口径提取;新能源车险须单独披露,否则不得提取。"
        else:
            note = ""
            calc = "按年报分险种披露口径提取;未披露则不提取。"
        definition = f"{full}业务综合成本率(COR)。" + (f"{note}" if note else "")
        new_rows.append([
            f"F{idx:03d}", "承保质量指标", f"{display}综合成本率",
            f"{full}综合成本率|{short}综合成本率|{en} combined ratio",
            join(kws + [f"{full}COR", f"{short}COR", f"{full}承保综合成本率", f"{short}承保综合成本率"]),
            definition,
            "%", "percentage", calc, SRC_PRIORITY,
        ])

    # ---- 修正 B004 非车非保证险保费 ----
    for row in original:
        if row[0] == "B004":
            row[4] = (
                "非车非保证险|非车非保证保险|非车非保证险保费|非车非保证险保费收入"
                "|非车非保证保险保费|非车非保证保险保费收入"
                "|剔除保证保险后的非车险|不含保证保险的非车险|扣除保证保险的非车险|排除保证保险的非车险"
                "|non-auto non-guarantee premiums|非車非保證險|非車非保證保險"
                "|剔除保證保險後的非車險|不含保證保險的非車險"
            )
            row[5] = (
                "剔除保证保险后的非车险保费收入(=非车险保费收入-保证保险保费收入)。"
                "仅当年报明确披露'剔除/不含/扣除/排除保证保险'的非车险保费时提取。"
            )
            row[8] = (
                "若年报未单独披露保证保险保费,或未明确'剔除保证保险'口径,"
                "则该指标无对应数值,不得提取;严禁用非车险保费收入代替。"
            )

    # 全表重建:表头 + 原始行 + 新增行
    ws.delete_rows(2, ws.max_row - 1)
    for row in original + new_rows:
        ws.append(row)
    wb.save(PATH)
    print(f"重建完成: 原始 {len(original)} 行 + 新增 {len(new_rows)} 行 = {len(original) + len(new_rows)} 行")


if __name__ == "__main__":
    main()
