"""
cron: 40 30 11 * * 1-5  stock_spider.py
new Env('上证指数');
"""
import sendNotify
import requests
import pysnowball as ball
import datetime

fundFilters = {
    '酒ETF',
    '芯片ETF',
    '证券ETF',
}

stockFilters = [
    'SH600519',
    'SH603605',
    'SH603444',
    'SH688111',
    # etf
    'SH510300',
    'SH512880',
    'SZ164906'
]

notifyData = []

wx_url = "https://wzq.tenpay.com/mp/v2/#/"
exchange_types = {
    'CSI': 'cs',
    'SH': '1',
    'SZ': '0'
}


# 个股涨幅统计
def get_stock_increase():
    for item in stockFilters:
        add_xq_increase(item)


def add_xq_increase(symbol):
    try:
        quote = ball.quote_detail(symbol)['data']['quote']
        # print(quote)
        price = format(quote['current'], '.2f')
        code = quote['code']
        notifyData.append({
            'id': code,
            'name': quote['name'],
            'increase': str(quote['percent']),
            'current': price,
            'avg_price': format(quote['avg_price'], '.2f'),
            'href': get_wx_href(code, quote['exchange']),
        })
        print(f"{code}\t{quote['name']}\t{price}")
    except Exception as e:
        # 打印异常信息
        print(f"An error occurred: {e}")


def get_wx_href(code, exchange):
    exchange_type = exchange_types.get(exchange, '1')
    return wx_url + f'trade/stock_detail.shtml?scode={code}&type={exchange_type}'


#  专门获取医药生物（801150.SL）的数据
def add_sw_increase():
    sw_url = 'https://www.swsresearch.com/institute-sw/api/index_publish/details/index_spread/?swindexcode=801150'
    headers = {
        'accept': "*/*",
        'user-agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    resp = requests.get(sw_url, headers=headers, verify=False)
    data = resp.json()['data'][0]
    last_day = float(data['l3'])
    now = float(data['l8'])
    notifyData.append({
        'id': '801150',
        'name': "医药生物",
        'increase': str(round(((now - last_day) / last_day) * 100, 2)),
        'current': str(now),
        'avg_price': '',
        'href': wx_url + 'plate/200/detail?plateId=01801150',
    })


def notify_with_markdown():
    if len(notifyData) < 2:
        sendNotify.serverJMy("获取上证数据失败，请检查！！", "")
        return
    today = get_today()
    markdown_text = f'''# {today} 行情
| 名称 | 现价 | 涨幅 | 均价 |
|--------|--------|--------|--------|
'''
    for item in notifyData:
        markdown_text += f'| [{item["name"]}]({item["href"]}) | {item["current"]} | {item["increase"]}%| {item["avg_price"]} |\n'
    sendNotify.serverJMy(generate_title(), markdown_text)
    with open("log_stock.md", 'w', encoding='utf-8') as f:
        f.write(markdown_text)


def get_today() -> str:
    today = datetime.date.today()
    weekday = today.weekday()
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    day_name = days[weekday]
    return str(today) + " " + day_name


def generate_title() -> str:
    return str(notifyData[0]["name"] + "涨幅为:" + notifyData[0]["increase"] + "%")


if __name__ == '__main__':
    ball.set_token('xq_a_token=2c5e1bd8101bfb889949cc25a0bd9dd3b828cd8f')  # token一个月会失效
    add_xq_increase('SH000001')
    add_xq_increase('SZ399808')
    add_sw_increase()
    add_xq_increase('CSI930599')
    get_stock_increase()
    notify_with_markdown()
