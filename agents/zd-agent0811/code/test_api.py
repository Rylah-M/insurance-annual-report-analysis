from openai import OpenAI
import os


client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.nwafu-ai.cn/v1"
)


response = client.chat.completions.create(
    model="gpt-5.5",
    messages=[
        {
            "role": "user",
            "content": "你好，请回复测试成功"
        }
    ]
)


print(response.choices[0].message.content)