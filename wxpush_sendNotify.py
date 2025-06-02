import requests
import os
from dotenv import load_dotenv
from typing import List, Optional
import json

load_dotenv()
WX_PUSH_TOKEN = os.getenv('WX_PUSH_TOKEN')


def send_wxpusher_html_message(summary: str, content: str, topic_id: int, uids: Optional[List[str]] = None,
                               url=None):
    payload = {
        "appToken": WX_PUSH_TOKEN,
        "summary": summary,
        "content": content,
        "topicIds": [topic_id],
        "contentType": 2,  # 设置为 HTML
        "verifyPayType": 1  # 1:只发送给付费的用户，2:只发送给未订阅或者订阅过期的用户. Defaults to 0.
    }
    if uids:
        payload["uids"] = uids
    if url:
        payload["url"] = url
    headers = {
        "Content-Type": "application/json"
    }
    # print(payload)
    try:
        response = requests.post('https://wxpusher.zjiecode.com/api/send/message', headers=headers,
                                 data=json.dumps(payload))
        response.raise_for_status()
        json_response = response.json()
        # print(json_response)
        return ""
    except requests.exceptions.RequestException as e:
        return f"\n✨微信推送请求错误: {e}"
