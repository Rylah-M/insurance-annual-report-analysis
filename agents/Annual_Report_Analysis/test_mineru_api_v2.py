#v2不考虑抓取不相关图片
import requests
import os


pdf_path = "./data/太保24Q2-A股.pdf"

output_dir = "./output"


url = "http://127.0.0.1:8000/file_parse"


data = {
    "backend": "pipeline",
    "lang": "ch",
    "start_page": 0,
    "end_page": 1,

    # 关闭图片分析
    "image_analysis": False,

    # 保留表格
    "table": True,

    # 保留公式
    "formula": False,
}


files = {
    "files": (
        os.path.basename(pdf_path),
        open(pdf_path, "rb"),
        "application/pdf"
    )
}


print("开始解析...")


response = requests.post(
    url,
    files=files,
    data=data,
    timeout=1800
)


print("status:", response.status_code)

print(response.text[:500])