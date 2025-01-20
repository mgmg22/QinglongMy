import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()
WX_URL = os.getenv('WX_URL')
WX_TOKEN = os.getenv('WX_TOKEN')


def send_wxpusher_html_message(summary: str, content: str, topic_id: str = None, uids: str = None, url=None):
    payload = {
        "appToken": WX_TOKEN,
        "summary": summary,
        "content": content,
        "contentType": 2,  # 设置为 HTML
        "verifyPayType": 1  # 1:只发送给付费的用户，2:只发送给未订阅或者订阅过期的用户. Defaults to 0.
    }
    if topic_id:
        payload["topicIds"] = [int(topic_id)]
    if uids:
        payload["uids"] = [uids]
    if url:
        payload["url"] = url
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(WX_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        json_response = response.json()
        # print(json_response)
        return f"wxPush{json_response.get('msg')}"
    except requests.exceptions.RequestException as e:
        return f"wxPush请求错误: {e}"
