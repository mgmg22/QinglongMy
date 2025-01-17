import os
import json
import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, Optional
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
        
        # 使用当前目录
        self.current_dir = Path.cwd()

    def parse_metadata_string(self, metadata_string: str) -> str:
        """
        处理API返回的字符串，移除首尾行
        """
        lines = metadata_string.strip().split('\n')
        if len(lines) > 2:
            lines = lines[1:-1]  # 移除第一行和最后一行
        return '\n'.join(lines).strip()

    async def chat_completion(self, prompt: str, model: str = "gemini-2.0-flash-exp") -> str:
        """
        调用API进行对话
        """
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
                    return self.parse_metadata_string(content)
                    
        except Exception as e:
            print(f"调用API时出错: {str(e)}")
            raise

    async def generate_tdk(self, 
                          keyword: str, 
                          description: str, 
                          output_filename: str = 'tdk.json') -> Optional[Dict]:
        """
        生成TDK信息并保存到文件
        """
        prompt = (
            "我希望你扮演一位SEO专家。作为一位SEO专家，你拥有广泛的知识和经验，"
            "能够帮助网站提高在搜索引擎结果中的排名，吸引更多的流量和用户。"
            "你熟悉各种搜索引擎的算法和规则，并能运用各种策略和技巧来优化网站的内容、"
            "结构和链接，以提升其在搜索结果中的可见性。"
            f"我正在开发一个网站，网站的关键词是:{keyword}，网站的主要功能是：{description},"
            "请基于这些信息给出合适的TDK(使用英文返回)。"
            '请使用json格式返回。返回格式示例：{"title":"","description":"","keywords":""}'
        ).strip()
        
        try:
            # 调用API获取响应
            response = await self.chat_completion(prompt)
            print(f"API原始响应: {response}")
            
            # 解析JSON响应
            tdk_data = json.loads(response)
            
            # 保存到文件
            output_path = self.current_dir / output_filename
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(tdk_data, f, ensure_ascii=False, indent=2)
            
            print(f"生成结果:\n{json.dumps(tdk_data, ensure_ascii=False, indent=2)}")
            print(f"已写入文件: {output_path}")
            
            return tdk_data
            
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            print(f"原始响应内容: {response}")
        except Exception as e:
            print(f"生成TDK时出错: {str(e)}")
        
        return None

# 使用示例
async def main():
    helper = AIHelper()
    keyword = 'app image ai'
    description = '利用AI技术实现对图片进行扩展，在保证原始图片不变的前提下，扩展四周的内容，且能与原图片保持内容延续性'
    
    await helper.generate_tdk(keyword, description)

if __name__ == "__main__":
    asyncio.run(main()) 