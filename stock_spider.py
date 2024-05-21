"""
cron: 40 30 11 * * 1-5  stock_spider.py
new Env('上证指数');
"""
import sendNotify
import requests
import pysnowball as ball
from stock_detail import get_stock_detail

indexFilters = {
    '上证指数',
    # '上证50',
    '科创50',
    '创业板指',
    # '沪深300',
    '北证50',
}

fundFilters = {
    '酒ETF',
    '芯片ETF',
    '证券ETF',
}

stockFilters = {
    '600519',
    '603605',
    '603444',
}

notifyData = []
stockData = []


# 指数涨幅统计
def get_index_increase():
    list_url = 'https://www.jisilu.cn/data/idx_performance/list/?___jsl=LST___t=1710685332681'
    resp = requests.post(list_url)
    for row in resp.json()['rows']:
        if row['cell']['index_nm'] in indexFilters:
            stock = {
                'id': row['id'],
                'name': row['cell']['index_nm'],
                'increase': row['cell']['increase_rt'],
            }
            notifyData.append(stock)


# 个股涨幅统计
def get_stock_increase():
    for item in stockFilters:
        stockData.append(get_stock_detail(item))


# etf涨幅统计
def get_fund_increase():
    fund_url = 'https://www.jisilu.cn/data/etf/etf_list/?___jsl=LST___t=1710853843396&rp=25&page=1'
    resp = requests.post(fund_url)
    for row in resp.json()['rows']:
        if row['cell']['fund_nm'] in fundFilters:
            stock = {
                'id': row['id'],
                'name': row['cell']['fund_nm'],
                'increase': row['cell']['increase_rt'],
            }
            notifyData.append(stock)


def add_xq_increase(code):
    quote = ball.quote_detail(code)['data']['quote']
    notifyData.append({
        'id': quote['code'],
        'name': quote['name'],
        'increase': quote['percent'],
    })


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
    swData = {
        'id': '801150',
        'name': "医药生物",
        'increase': str(round(((now - last_day) / last_day) * 100, 2)),
    }
    notifyData.append(swData)


def notify_with_markdown():
    markdown_text = '''# 今日涨幅统计
| 代码 | 名称 | 涨幅 |
|--------|--------|--------|
'''
    for item in notifyData:
        markdown_text += f'| {item["id"]} | {item["name"]} | {item["increase"]} %|\n'
    markdown_text += '''# 今日个股涨幅统计
| 代码 | 名称 | 现价 | 涨幅 |
|--------|:--------|--------:|--------|
'''
    for item in stockData:
        markdown_text += f'| {item["id"]} | {item["name"]} | {item["price"]} | {item["increase"]} |\n'
    sendNotify.serverJMy(generate_title(), markdown_text)
    with open("log_stock.md", 'w', encoding='utf-8') as f:
        f.write(markdown_text)


def generate_title() -> str:
    return str(notifyData[0]["name"] + "涨幅为:" + notifyData[0]["increase"] + "%")


if __name__ == '__main__':
    ball.set_token('xq_a_token=e8bf59070a162a60f06134803dd747557a3dbc2e;')
    get_index_increase()
    get_stock_increase()
    get_fund_increase()
    add_xq_increase('CSI930599')
    add_xq_increase('SZ399808')
    add_sw_increase()
    notify_with_markdown()
