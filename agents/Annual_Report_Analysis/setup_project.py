from pathlib import Path

# 当前项目根目录
root = Path.cwd()

# 文件夹结构
folders = [
    "data",
    "output"
]

# 文件结构
files = [
    "pdf_parser.py",
    "README.md",
    "requirements.txt"
]

# 创建文件夹
for folder in folders:
    path = root / folder
    path.mkdir(exist_ok=True)
    print(f"Created folder: {path}")

# 创建文件
for file in files:
    path = root / file
    if not path.exists():
        path.touch()
        print(f"Created file: {path}")

print("\n✅ Annual_Report_Analysis structure created!")