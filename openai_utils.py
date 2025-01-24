import os
import json
import aiohttp
from dotenv import load_dotenv
import asyncio


class AIHelper:
    def __init__(self):
        # 加载环境变量
        load_dotenv()
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

    def clean_response(self, response: str) -> str:
        """去除响应中的 ```json 和 ``` 标记，并确保返回有效的 JSON 字符串"""
        # print("Original response:", response)  # 打印原始响应

        # 尝试找到 JSON 内容的开始和结束
        try:
            # 查找 JSON 数组的开始和结束
            start_idx = response.find('[')
            end_idx = response.rfind(']') + 1

            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                # 验证是否为有效的 JSON
                try:
                    json.loads(json_str)
                    return json_str
                except json.JSONDecodeError as e:
                    print(f"JSON validation failed: {e}")

            print("Failed to find valid JSON content")
            return response  # 如果无法找到有效的 JSON，返回原始响应

        except Exception as e:
            print(f"Error in clean_response: {e}")
            return response

    async def analyze_content(self, content: dict, prompt: str) -> str:
        results = []
        try:
            score_response = await self.chat_completion(prompt)
            # print("API Response:", score_response)  # 打印 API 响应
            cleaned_response = self.clean_response(score_response)

            # 验证清理后的响应是否为有效的 JSON
            try:
                json.loads(cleaned_response)
                results.append(cleaned_response)
            except json.JSONDecodeError as e:
                print(f"Invalid JSON after cleaning: {e}")
                return json.dumps(content)

        except Exception as e:
            print(f"调用API时出错: {str(e)}")
            print("等待 1 分钟后重试...")
            await asyncio.sleep(60)  # 等待 1 分钟重试
            try:
                score_response = await self.chat_completion(prompt)
                cleaned_response = self.clean_response(score_response)
                results.append(cleaned_response)
            except Exception as e:
                print(f"重试时出错: {str(e)}")
                return json.dumps(content)

        # 返回结果字符串
        return results[0]
