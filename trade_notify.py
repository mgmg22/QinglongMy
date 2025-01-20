"""
cron: 1-29 10,11,13,14 * * 1-5  trade_notify.py
new Env('行情监控');
雪球API:https://github.com/uname-yang/pysnowball
"""
import sendNotify
import requests
import pysnowball as ball
import json


def add_xq_increase(symbol):
    try:
        quote = ball.quote_detail(symbol)['data']['quote']
        print(json.dumps(quote, ensure_ascii=False, indent=2))
        current = quote['current']
        high = quote['high']
        low = quote['low']
        amplitude = quote['amplitude']
        open_price = quote['open']
        title = quote['name']
        content = (f'''高：{high}    低：{low}    涨幅：{str(quote['percent'])}%
开：{open_price}    振幅：{amplitude}%''')
        print(content)
        check_and_notify(amplitude, open_price, current, high, low, title, content)
    except Exception as e:
        # 打印异常信息
        print(f"add_xq_increase An error occurred: {e}")


def check_and_notify(amplitude, open_price, current, high, low, title, content):
    if amplitude > 1.1:
        check_sell_point(open_price, current, high, title, content)
        check_buy_point(open_price, current, low, title, content)


def check_sell_point(open_price, current, high, title, content):
    if current - open_price > 10 and high - current < 5:
        title = f'[f]{title}卖点:{current}'
        send_notification(title, content)


def check_buy_point(open_price, current, low, title, content):
    if open_price - current > 10 and current - low < 3:
        title = f'[s]{title}买点:{current}'
        send_notification(title, content)


def send_notification(title, content):
    print(title)
    print(content)
    sendNotify.push_me(title, content, "text")


if __name__ == '__main__':
    r = requests.get("https://xueqiu.com/hq", headers={"user-agent": "Mozilla"})
    t = r.cookies["xq_a_token"]
    ball.set_token(f'xq_a_token={t}')
    add_xq_increase('SH600519')
