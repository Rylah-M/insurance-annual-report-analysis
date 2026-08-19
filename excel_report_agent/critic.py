from __future__ import annotations

from typing import Any


def review(analysis: dict[str, Any], markdown: str) -> dict[str, Any]:
    findings: list[dict[str, str]] = []

    # 数据层
    for insight in analysis["insights"]:
        if insight["confidence"] == "high" and not insight.get("evidence"):
            findings.append(
                {"level": "warning", "area": "数据层", "message": f"{insight['id']} 缺少证据链。"}
            )
    if analysis["premium"]["industry_growth"] is None:
        findings.append({"level": "warning", "area": "数据层", "message": "行业整体增速缺失。"})

    # 分析层
    chapters = {
        "执行摘要": "一、执行摘要" in markdown,
        "保费结构": "二、整体保费与业务结构" in markdown,
        "承保盈利": "三、承保盈利与增长质量" in markdown,
        "重点险种": "四、重点险种经营分析" in markdown,
        "阳光画像": "五、阳光经营画像" in markdown,
    }
    for name, present in chapters.items():
        if not present:
            findings.append({"level": "error", "area": "报告层", "message": f"缺少章节：{name}。"})
    if not analysis["insights"]:
        findings.append({"level": "error", "area": "分析层", "message": "未生成任何 Insight。"})
    for insight in analysis["insights"]:
        if not insight.get("interpretation") or not insight.get("so_what"):
            findings.append(
                {"level": "warning", "area": "分析层", "message": f"{insight['id']} 缺少解读或 So What。"}
            )

    # 逻辑层
    for signal in analysis["signals"]:
        if "推测" in signal["message"] and signal["confidence"] == "high":
            findings.append(
                {"level": "warning", "area": "逻辑层", "message": "推测性表述不应标记为 high 置信度。"}
            )

    # 报告层
    if "阳光" not in markdown:
        findings.append({"level": "warning", "area": "报告层", "message": "报告未突出阳光。"})
    if "待验证" not in markdown:
        findings.append({"level": "warning", "area": "报告层", "message": "缺少待验证问题。"})

    passed = all(item["level"] != "error" for item in findings)
    summary = (
        "Quality Critic 审稿通过：核心章节完整，Insight 均具备证据链与 So What。"
        if passed and not findings
        else f"Quality Critic 审稿发现 {len(findings)} 项问题（其中 error {sum(1 for f in findings if f['level'] == 'error')} 项）。"
    )
    return {"passed": passed, "findings": findings, "summary": summary}
