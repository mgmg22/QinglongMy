import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()
WX_URL = os.getenv('WX_URL')
WX_TOKEN = os.getenv('WX_TOKEN')


def send_wxpusher_html_message(summary: str, content: str, topic_ids: str = None, uids: str = None, url=None, verify_pay_type=0):
    """
    使用 WxPusher API 发送 HTML 消息。

    Args:
        app_token (str): WxPusher 的 AppToken。
        content (str): 要发送的 HTML 内容。
        summary (str, optional): 消息摘要。 Defaults to None.
        topic_ids (list, optional): 发送目标的 topicId 列表。 Defaults to None.
        uids (list, optional): 发送目标的 UID 列表。 Defaults to None.
        url (str, optional): 原文链接。 Defaults to None.
        verify_pay_type (int, optional): 是否验证订阅时间，0：不验证，1:只发送给付费的用户，2:只发送给未订阅或者订阅过期的用户. Defaults to 0.

    Returns:
        dict: API 返回的 JSON 数据。
    """
    url = ""
    payload = {
        "appToken": WX_TOKEN,
        "summary": summary,
        "content": content,
        "contentType": 2,  # 设置为 HTML
        "verifyPayType": verify_pay_type
    }
    if topic_ids:
        payload["topic_ids"] = topic_ids
    if uids:
        payload["uids"] = [uids]
    if url:
        payload["url"] = url
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(WX_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # 如果请求失败，会抛出异常
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求错误: {e}")
        return None