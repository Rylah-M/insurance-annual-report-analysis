#v1会抓取不相关图片
import requests

pdf_path = "./data/2024年中国平安年度报告.pdf"

url = "http://127.0.0.1:8000/file_parse"

files = {
    "files": open(pdf_path, "rb")
}

data = {
    "backend": "pipeline",
    "lang": "ch",
    "start_page": 0,
    "end_page": 1
}

print("开始解析...")

response = requests.post(
    url,
    files=files,
    data=data,
    timeout=600
)

print("状态码:", response.status_code)

print(response.text[:2000])