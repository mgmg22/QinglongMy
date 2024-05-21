"""
cron: 40 30 11 * * 1-5  stock_spider.py
new Env('上证指数');
"""
import sendNotify
import requests
import pysnowball as ball

fundFilters = {
    '酒ETF',
    '芯片ETF',
    '证券ETF',
}

stockFilters = [
    'SH600519',
    'SH603605',
    'SH603444',
    # etf
    'SH510300',
    'SH512880',
    'SZ164906'
]

notifyData = []


# 个股涨幅统计
def get_stock_increase():
    for item in stockFilters:
        add_xq_increase(item)


def add_xq_increase(code):
    quote = ball.quote_detail(code)['data']['quote']
    # print(quote)
    price = format(quote['current'], '.2f')
    notifyData.append({
        'id': quote['code'],
        'name': quote['name'],
        'increase': str(quote['percent']),
        'current': price,
        'avg_price': format(quote['avg_price'], '.2f'),
    })
    print(f"{quote['code']}\t{quote['name']}\t{price}")


#  专门获取医药生物（801150.SL）的数据
def add_sw_increase():
    sw_url = 'http://www.swsresearch.com/institute-sw/api/index_publish/details/index_spread/?swindexcode=801150'
    headers = {
        'accept': "*/*",
        'user-agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    resp = requests.get(sw_url, headers=headers)
    data = resp.json()['data'][0]
    last_day = float(data['l3'])
    now = float(data['l8'])
    notifyData.append({
        'id': '801150',
        'name': "医药生物",
        'increase': str(round(((now - last_day) / last_day) * 100, 2)),
        'current': str(now),
        'avg_price': '',
    })


def notify_with_markdown():
    markdown_text = '''# 今日行情
| 名称 | 现价 | 涨幅 | 均价 |
|--------|--------|--------|--------|
'''
    for item in notifyData:
        markdown_text += f'| {item["name"]} | {item["current"]} | {item["increase"]}%| {item["avg_price"]} |\n'
    sendNotify.serverJMy(generate_title(), markdown_text)
    with open("log_stock.md", 'w', encoding='utf-8') as f:
        f.write(markdown_text)


def generate_title() -> str:
    return str(notifyData[0]["name"] + "涨幅为:" + notifyData[0]["increase"] + "%")


if __name__ == '__main__':
    ball.set_token('xq_a_token=e8bf59070a162a60f06134803dd747557a3dbc2e')
    add_xq_increase('SH000001')
    add_xq_increase('SZ399808')
    add_sw_increase()
    add_xq_increase('CSI930599')
    get_stock_increase()
    notify_with_markdown()
