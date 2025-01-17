import os
import json
import aiohttp
from pathlib import Path
import time
from dotenv import load_dotenv


class AIHelper:
    def __init__(self):
        # 加载环境变量
        load_dotenv()

        # API配置
        self.api_key = os.getenv('API_KEY')  # 从环境变量获取API密钥
        if not self.api_key:
            raise ValueError("API_KEY 环境变量未设置")

        self.base_url = os.getenv('API_URL')  # 从环境变量获取API URL
        if not self.base_url:
            raise ValueError("API_URL 环境变量未设置")

    async def chat_completion(self, prompt: str, model: str = "gemini-2.0-flash-exp") -> str:
        # 调用API进行对话
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"请求详情:")
                        print(f"URL: {self.base_url}")
                        print(f"Headers: {headers}")
                        print(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
                        raise Exception(f"API请求失败: {response.status} - {error_text}")

                    data = await response.json()
                    if 'choices' not in data or not data['choices']:
                        print(f"API响应异常: {json.dumps(data, ensure_ascii=False)}")
                        raise Exception("API响应格式错误")

                    # 处理返回的内容
                    content = data['choices'][0]['message']['content']
                    return content

        except Exception as e:
            print(f"调用API时出错: {str(e)}")
            raise

    async def score_log_entries(self, content: str) -> str:
        results = []
        prompt = f"请逐项分析以下内容的价值，在保持所有数据格式不变的前提下，在每一项结尾添加一行数据格式为：「评分1-5分」一句话简要总结的理由\n{content.strip()}"

        for attempt in range(5):  # 尝试最多5次
            try:
                score_response = await self.chat_completion(prompt)
                results.append(score_response)
                break  # 成功后跳出重试循环
            except Exception as e:
                if "429" in str(e):  # 检查是否是429错误
                    print("请求过于频繁，等待重试...")
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    print(f"调用API时出错: {str(e)}")
                    results.append(f"得分结果: 错误 - {str(e)}\n")
                    break  # 其他错误直接跳出重试循环

        # 返回结果字符串
        return "\n".join(results)
