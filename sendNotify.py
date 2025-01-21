#!/usr/bin/env python3
# _*_ coding:utf-8 _*_
import base64
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
import threading
import time
import urllib.parse

import requests
from md_util import markdown_to_html
from wxpush_sendNotify import send_wxpusher_html_message

# 添加对 .env 文件的支持
try:
    from dotenv import load_dotenv

    # 优先尝试加载 .env 文件
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
except ImportError:
    print("提示: 可以安装 python-dotenv 来使用 .env 文件功能")
    pass

# 原先的 print 函数和主线程的锁
_print = print
mutex = threading.Lock()

IS_LOCAL_DEV = os.getenv('IS_LOCAL_DEV', 'false').lower()


def is_product_env():
    return IS_LOCAL_DEV != 'true'


# 定义新的 print 函数
def print(text, *args, **kw):
    """
    使输出有序进行，不出现多线程同一时间输出导致错乱的问题。
    """
    with mutex:
        _print(text, *args, **kw)


# 通知服务
# fmt: off
push_config = {
    'HITOKOTO': False,  # 启用一言（随机句子）

    'BARK_PUSH': '',  # bark IP 或设备码，例：https://api.day.app/DxHcxxxxxRxxxxxxcm/
    'BARK_ARCHIVE': '',  # bark 推送是否存档
    'BARK_GROUP': '',  # bark 推送分组
    'BARK_SOUND': '',  # bark 推送声音

    'CONSOLE': True,  # 控制台输出

    'DD_BOT_SECRET': '',  # 钉钉机器人的 DD_BOT_SECRET
    'DD_BOT_TOKEN': '',  # 钉钉机器人的 DD_BOT_TOKEN

    'FSKEY': '',  # 飞书机器人的 FSKEY

    'GOBOT_URL': '',  # go-cqhttp
    # 推送到个人QQ：http://127.0.0.1/send_private_msg
    # 群：http://127.0.0.1/send_group_msg
    'GOBOT_QQ': '',  # go-cqhttp 的推送群或用户
    # GOBOT_URL 设置 /send_private_msg 时填入 user_id=个人QQ
    #               /send_group_msg   时填入 group_id=QQ群
    'GOBOT_TOKEN': '',  # go-cqhttp 的 access_token

    'GOTIFY_URL': '',  # gotify地址,如https://push.example.de:8080
    'GOTIFY_TOKEN': '',  # gotify的消息应用token
    'GOTIFY_PRIORITY': 0,  # 推送消息优先级,默认为0

    'IGOT_PUSH_KEY': '',  # iGot 聚合推送的 IGOT_PUSH_KEY

    'PUSH_KEY': '',  # server 酱的 PUSH_KEY，兼容旧版与 Turbo 版

    'QMSG_KEY': '',  # qmsg 酱的 QMSG_KEY
    'QMSG_TYPE': '',  # qmsg 酱的 QMSG_TYPE

    'TG_BOT_TOKEN': '',  # tg 机器人的 TG_BOT_TOKEN，例：1407203283:AAG9rt-6RDaaX0HBLZQq0laNOh898iFYaRQ
    'TG_USER_ID': '',  # tg 机器人的 TG_USER_ID，例：1434078534
    'TG_API_HOST': '',  # tg 代理 api
    'TG_PROXY_AUTH': '',  # tg 代理认证参数
    'TG_PROXY_HOST': '',  # tg 机器人的 TG_PROXY_HOST
    'TG_PROXY_PORT': '',  # tg 机器人的 TG_PROXY_PORT

    'PUSH_KEY_MY': '',  # server 酱的 PUSH_KEY，兼容旧版与 Turbo 版  我的
    'PUSH_KEY_SECOND': '',  # server 酱的 PUSH_KEY，兼容旧版与 Turbo 版  我的
    'PUSH_ME_KEY': '',  # push.i-i.me的用户令牌
}
notify_function = []
# fmt: on

# 首先读取 面板变量 或者 github action 运行变量
for k in push_config:
    if os.getenv(k):
        v = os.getenv(k)
        push_config[k] = v


def bark(title: str, content: str) -> None:
    """
    使用 bark 推送消息。
    """
    if not push_config.get("BARK_PUSH"):
        print("bark 服务的 BARK_PUSH 未设置!!\n取消推送")
        return
    print("bark 服务启动")

    if push_config.get("BARK_PUSH").startswith("http"):
        url = f'{push_config.get("BARK_PUSH")}/{urllib.parse.quote_plus(title)}/{urllib.parse.quote_plus(content)}'
    else:
        url = f'https://api.day.app/{push_config.get("BARK_PUSH")}/{urllib.parse.quote_plus(title)}/{urllib.parse.quote_plus(content)}'

    bark_params = {
        "BARK_ARCHIVE": "isArchive",
        "BARK_GROUP": "group",
        "BARK_SOUND": "sound",
    }
    params = ""
    for pair in filter(
            lambda pairs: pairs[0].startswith("BARK_")
                          and pairs[0] != "BARK_PUSH"
                          and pairs[1]
                          and bark_params.get(pairs[0]),
            push_config.items(),
    ):
        params += f"{bark_params.get(pair[0])}={pair[1]}&"
    if params:
        url = url + "?" + params.rstrip("&")
    response = requests.get(url).json()

    if response["code"] == 200:
        print("bark 推送成功！")
    else:
        print("bark 推送失败！")


def console(title: str, content: str) -> None:
    """
    使用 控制台 推送消息。
    """
    print(f"{title}\n\n{content}")


def dingding_bot(title: str, content: str) -> None:
    """
    使用 钉钉机器人 推送消息。
    """
    if not push_config.get("DD_BOT_SECRET") or not push_config.get("DD_BOT_TOKEN"):
        print("钉钉机器人 服务的 DD_BOT_SECRET 或者 DD_BOT_TOKEN 未设置!!\n取消推送")
        return
    print("钉钉机器人 服务启动")

    timestamp = str(round(time.time() * 1000))
    secret_enc = push_config.get("DD_BOT_SECRET").encode("utf-8")
    string_to_sign = "{}\n{}".format(timestamp, push_config.get("DD_BOT_SECRET"))
    string_to_sign_enc = string_to_sign.encode("utf-8")
    hmac_code = hmac.new(
        secret_enc, string_to_sign_enc, digestmod=hashlib.sha256
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    url = f'https://oapi.dingtalk.com/robot/send?access_token={push_config.get("DD_BOT_TOKEN")}&timestamp={timestamp}&sign={sign}'
    headers = {"Content-Type": "application/json;charset=utf-8"}
    data = {"msgtype": "markdown", "markdown": {"title": f"{title}", "text": f"{content}"}}
    response = requests.post(
        url=url, data=json.dumps(data), headers=headers, timeout=15
    ).json()

    if not response["errcode"]:
        print("钉钉机器人 推送成功！")
    else:
        print("钉钉机器人 推送失败！")


def dingding_bot_with_key(title: str, content: str, bot_key: str) -> None:
    """
    使用 钉钉机器人 推送消息。
    """
    if not os.getenv(bot_key):
        print(f"钉钉机器人{bot_key} 未设置!!\n取消推送")
        return
    print(f"钉钉机器人{bot_key} 服务启动")
    token = os.getenv(bot_key)
    timestamp = str(round(time.time() * 1000))
    secret_enc = token.encode("utf-8")
    string_to_sign = "{}\n{}".format(timestamp, bot_key)
    string_to_sign_enc = string_to_sign.encode("utf-8")
    hmac_code = hmac.new(
        secret_enc, string_to_sign_enc, digestmod=hashlib.sha256
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    url = f'https://oapi.dingtalk.com/robot/send?access_token={token}&timestamp={timestamp}&sign={sign}'
    headers = {"Content-Type": "application/json;charset=utf-8"}
    data = {"msgtype": "markdown", "markdown": {"title": f"{title}", "text": f"{content}"}}
    response = requests.post(
        url=url, data=json.dumps(data), headers=headers, timeout=15
    ).json()

    if not response["errcode"]:
        print(f"钉钉机器人{bot_key} 推送成功！")
    else:
        print("钉钉机器人{bot_key} 推送失败！")


def feishu_bot(title: str, content: str) -> None:
    """
    使用 飞书机器人 推送消息。
    """
    if not push_config.get("FSKEY"):
        print("飞书 服务的 FSKEY 未设置!!\n取消推送")
        return
    print("飞书 服务启动")

    url = f'https://open.feishu.cn/open-apis/bot/v2/hook/{push_config.get("FSKEY")}'
    data = {"msg_type": "text", "content": {"text": f"{title}\n\n{content}"}}
    response = requests.post(url, data=json.dumps(data)).json()

    if response.get("StatusCode") == 0:
        print("飞书 推送成功！")
    else:
        print("飞书 推送失败！错误信息如下：\n", response)


def go_cqhttp(title: str, content: str) -> None:
    """
    使用 go_cqhttp 推送消息。
    """
    if not push_config.get("GOBOT_URL") or not push_config.get("GOBOT_QQ"):
        print("go-cqhttp 服务的 GOBOT_URL 或 GOBOT_QQ 未设置!!\n取消推送")
        return
    print("go-cqhttp 服务启动")

    url = f'{push_config.get("GOBOT_URL")}?access_token={push_config.get("GOBOT_TOKEN")}&{push_config.get("GOBOT_QQ")}&message=标题:{title}\n内容:{content}'
    response = requests.get(url).json()

    if response["status"] == "ok":
        print("go-cqhttp 推送成功！")
    else:
        print("go-cqhttp 推送失败！")


def gotify(title: str, content: str) -> None:
    """
    使用 gotify 推送消息。
    """
    if not push_config.get("GOTIFY_URL") or not push_config.get("GOTIFY_TOKEN"):
        print("gotify 服务的 GOTIFY_URL 或 GOTIFY_TOKEN 未设置!!\n取消推送")
        return
    print("gotify 服务启动")

    url = f'{push_config.get("GOTIFY_URL")}/message?token={push_config.get("GOTIFY_TOKEN")}'
    data = {"title": title, "message": content, "priority": push_config.get("GOTIFY_PRIORITY")}
    response = requests.post(url, data=data).json()

    if response.get("id"):
        print("gotify 推送成功！")
    else:
        print("gotify 推送失败！")


def iGot(title: str, content: str) -> None:
    """
    使用 iGot 推送消息。
    """
    if not push_config.get("IGOT_PUSH_KEY"):
        print("iGot 服务的 IGOT_PUSH_KEY 未设置!!\n取消推送")
        return
    print("iGot 服务启动")

    url = f'https://push.hellyw.com/{push_config.get("IGOT_PUSH_KEY")}'
    data = {"title": title, "content": content}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(url, data=data, headers=headers).json()

    if response["ret"] == 0:
        print("iGot 推送成功！")
    else:
        print(f'iGot 推送失败！{response["errMsg"]}')


def serverJ(title: str, content: str) -> None:
    """
    通过 serverJ 推送消息。
    """
    if not push_config.get("PUSH_KEY"):
        print("serverJ 服务的 PUSH_KEY 未设置!!\n取消推送")
        return
    print("serverJ 服务启动")

    data = {"text": title, "desp": content.replace("\n", "\n\n")}
    if push_config.get("PUSH_KEY").index("SCT") != -1:
        url = f'https://sctapi.ftqq.com/{push_config.get("PUSH_KEY")}.send'
    else:
        url = f'https://sc.ftqq.com/${push_config.get("PUSH_KEY")}.send'
    response = requests.post(url, data=data).json()

    if response.get("errno") == 0 or response.get("code") == 0:
        print("serverJ 推送成功！")
    else:
        print(f'serverJ 推送失败！错误码：{response["message"]}')


def qmsg_bot(title: str, content: str) -> None:
    """
    使用 qmsg 推送消息。
    """
    if not push_config.get("QMSG_KEY") or not push_config.get("QMSG_TYPE"):
        print("qmsg 的 QMSG_KEY 或者 QMSG_TYPE 未设置!!\n取消推送")
        return
    print("qmsg 服务启动")

    url = f'https://qmsg.zendee.cn/{push_config.get("QMSG_TYPE")}/{push_config.get("QMSG_KEY")}'
    payload = {"msg": f'{title}\n\n{content.replace("----", "-")}'.encode("utf-8")}
    response = requests.post(url=url, params=payload).json()

    if response["code"] == 0:
        print("qmsg 推送成功！")
    else:
        print(f'qmsg 推送失败！{response["reason"]}')


def telegram_bot(title: str, content: str) -> None:
    """
    使用 telegram 机器人 推送消息。
    """
    if not push_config.get("TG_BOT_TOKEN") or not push_config.get("TG_USER_ID"):
        print("tg 服务的 bot_token 或者 user_id 未设置!!\n取消推送")
        return
    print("tg 服务启动")

    if push_config.get("TG_API_HOST"):
        url = f"https://{push_config.get('TG_API_HOST')}/bot{push_config.get('TG_BOT_TOKEN')}/sendMessage"
    else:
        url = (
            f"https://api.telegram.org/bot{push_config.get('TG_BOT_TOKEN')}/sendMessage"
        )
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "chat_id": str(push_config.get("TG_USER_ID")),
        "text": f"{title}\n\n{content}",
        "disable_web_page_preview": "true",
    }
    proxies = None
    if push_config.get("TG_PROXY_HOST") and push_config.get("TG_PROXY_PORT"):
        if push_config.get("TG_PROXY_AUTH") is not None and "@" not in push_config.get(
                "TG_PROXY_HOST"
        ):
            push_config["TG_PROXY_HOST"] = (
                    push_config.get("TG_PROXY_AUTH")
                    + "@"
                    + push_config.get("TG_PROXY_HOST")
            )
        proxyStr = "http://{}:{}".format(
            push_config.get("TG_PROXY_HOST"), push_config.get("TG_PROXY_PORT")
        )
        proxies = {"http": proxyStr, "https": proxyStr}
    response = requests.post(
        url=url, headers=headers, params=payload, proxies=proxies
    ).json()

    if response["ok"]:
        print("tg 推送成功！")
    else:
        print("tg 推送失败！")


def one() -> str:
    """
    获取一条一言。
    :return:
    """
    url = "https://v1.hitokoto.cn/"
    res = requests.get(url).json()
    return res["hitokoto"] + "    ----" + res["from"]


if push_config.get("BARK_PUSH"):
    notify_function.append(bark)
if push_config.get("CONSOLE"):
    notify_function.append(console)
if push_config.get("DD_BOT_TOKEN") and push_config.get("DD_BOT_SECRET"):
    notify_function.append(dingding_bot)
if push_config.get("FSKEY"):
    notify_function.append(feishu_bot)
if push_config.get("GOBOT_URL") and push_config.get("GOBOT_QQ"):
    notify_function.append(go_cqhttp)
if push_config.get("GOTIFY_URL") and push_config.get("GOTIFY_TOKEN"):
    notify_function.append(gotify)
if push_config.get("IGOT_PUSH_KEY"):
    notify_function.append(iGot)
if push_config.get("PUSH_KEY"):
    notify_function.append(serverJ)
if push_config.get("QMSG_KEY") and push_config.get("QMSG_TYPE"):
    notify_function.append(qmsg_bot)
if push_config.get("TG_BOT_TOKEN") and push_config.get("TG_USER_ID"):
    notify_function.append(telegram_bot)


def send(title: str, content: str) -> None:
    if not content:
        print(f"{title} 推送内容为空！")
        return

    hitokoto = push_config.get("HITOKOTO")

    text = one() if hitokoto else ""
    content += "\n\n" + text

    ts = [
        threading.Thread(target=mode, args=(title, content), name=mode.__name__)
        for mode in notify_function
    ]
    [t.start() for t in ts]
    [t.join() for t in ts]


def main():
    send("title", "content")


def serverJSecond(title: str, content: str) -> None:
    if not push_config.get("PUSH_KEY_SECOND"):
        print("serverJ My服务的 PUSH_KEY_SECOND 未设置!!\n取消推送")
        return
    data = {"text": title, "desp": content}
    url = f'https://sctapi.ftqq.com/{push_config.get("PUSH_KEY_SECOND")}.send'

    response = requests.post(url, data=data).json()

    if response.get("errno") == 0 or response.get("code") == 0:
        print("serverJ SECOND推送成功！")
    else:
        print(f'serverJ SECOND推送失败！错误码：{response["message"]}')


def serverJMy(title: str, content: str) -> None:
    if not push_config.get("PUSH_KEY_MY"):
        print("serverJ My服务的 PUSH_KEY_MY 未设置!!\n取消推送")
        return
    data = {"text": title, "desp": content}
    url = f'https://sctapi.ftqq.com/{push_config.get("PUSH_KEY_MY")}.send'

    response = requests.post(url, data=data).json()

    if response.get("errno") == 0 or response.get("code") == 0:
        print("serverJ My推送成功！")
        serverJSecond(title, content)
    else:
        print(f'serverJ My推送失败！错误码：{response["message"]}')


def push_me(title: str, content: str, msg_type: str) -> None:
    if not push_config.get("PUSH_ME_KEY"):
        print("pushMe服务的 PUSH_ME_KEY 未设置!!\n取消推送")
        return
    url = "https://push.i-i.me"
    payload = {
        'push_key': push_config.get("PUSH_ME_KEY"),
        'title': title,
        'content': content,
        'type': msg_type
    }
    headers = {
        'accept': '*/*',
        'accept-encoding': 'gzip',
        'accept-language': 'zh-CN,zh;q=0.9',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.6045.160 Safari/537.36'
    }
    response = requests.post(url, headers=headers, data=payload)
    print(response.text)


def send_wx_push(summary: str, markdown_text: str, topic_id):
    html_content = markdown_to_html(markdown_text)
    # print(html_content)
    uid = [os.getenv('admin_uid')]
    if is_product_env():
        uid.append(os.getenv('yun_uid'))
    else:
        summary = f'测试消息：{summary}'
    return send_wxpusher_html_message(summary=summary, content=html_content, topic_id=topic_id, uids=uid)


if __name__ == "__main__":
    main()
