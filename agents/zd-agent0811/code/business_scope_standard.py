"""business_scope 口径标准化层。

只新增 business_scope_type 分类，不改动原始 business_scope。
枚举：集团口径 / 财险口径 / 特殊财险口径。
"""

from __future__ import annotations


BUSINESS_SCOPE_TYPES = ("集团口径", "财险口径", "特殊财险口径")

GROUP_MARKERS = (
    "集团口径",
    "集团合并",
    "本集团",
    "集团",
    "集團",
    "合并口径",
    "合并",
    "合併",
    "母公司及子公司合并",
    "母公司及子公司合併",
    "母公司合并",
    "母公司合併",
)

PROPERTY_MARKERS = (
    "财险",
    "产险",
    "财产保险",
    "财产险",
    "財險",
    "產險",
    "財產保險",
    "財產險",
    "非寿险",
    "非壽險",
    "property insurance",
)

SPECIAL_MARKERS = (
    # 单独主体、不含/扣除等范围限定
    "单体",
    "单體",
    "母公司口径",
    "母公司口徑",
    "不含",
    "不包括",
    "不包含",
    "扣除",
    "剔除",
    # 特殊主体或区域
    "太保香港",
    "香港",
    "境内",
    "境外",
    "再保",
    "信农险",
    # 特定业务范围
    "车险",
    "車險",
    "机动车辆险",
    "機動車輛險",
    "机动车险",
    "非机动车辆险",
    "非機動車輛險",
    "农业险",
    "農險",
    "农险",
    "健康险",
    "健康生態",
    "健康生态",
    "汽车生态",
    "汽車生態",
    "意外伤害",
    "意外險",
    "意外险",
    "责任保险",
    "責任保險",
    "保证保险",
    "保證保險",
    "货物运输",
    "貨物運輸",
    "货运险",
    "貨運險",
    "新能源车险",
    "新能源車險",
    "企业财产保险",
    "企業財產保險",
    # 特殊计量或负债口径
    "采用保费分配法计量",
    "採用保費分配法計量",
    "保险合同负债",
    "保險合同負債",
)

NO_SCOPE_MARKERS = (
    "未披露",
    "暂无",
    "未提供",
    "未找到",
)


def classify_business_scope_type(business_scope) -> str:
    """把原始业务范围归类为标准口径；空值保持为空。"""
    if business_scope is None:
        return ""
    text = str(business_scope).strip()
    if not text:
        return ""
    if any(marker in text for marker in NO_SCOPE_MARKERS):
        return ""
    if any(marker in text for marker in GROUP_MARKERS):
        return "集团口径"
    if any(marker in text for marker in SPECIAL_MARKERS):
        return "特殊财险口径"
    if any(marker in text for marker in PROPERTY_MARKERS):
        return "财险口径"
    # 无法匹配集团/财险关键词的自定义描述按特殊口径处理，
    # 避免丢失口径信息，也便于人工在审核页面修正。
    return "特殊财险口径"
