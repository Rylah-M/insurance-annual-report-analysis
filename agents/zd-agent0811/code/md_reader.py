import os


# =====================
# 文件路径
# =====================

md_file = "../md/2024年中国平安年度报告.md"


# =====================
# 读取Markdown
# =====================

with open(
    md_file,
    "r",
    encoding="utf-8"
) as f:

    text = f.read()


print("读取成功")

print(
    "文本长度:",
    len(text)
)


print("\n前500字符:")
print(text[:500])
