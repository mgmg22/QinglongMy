"""
cron: 40 30 11 * * 1-5  stock_spider.py
new Env('上证指数');
雪球API:https://github.com/uname-yang/pysnowball
申万宏源数据：https://www.swsresearch.com/institute_sw/allIndex/releasedIndex/releasedetail?code=801150&name=%E5%8C%BB%E8%8D%AF%E7%94%9F%E7%89%A9
"""
from sendNotify import serverJMy
import requests
import pysnowball as ball
import datetime
import json

stockFilters = [
    'SH600519',
    'SH603605',
    'SH603444',
    'SZ000002',
    'SH600276',
    # etf
    'SH513100',
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
        print(f"add_xq_increase An error occurred: {e}")


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
    increase = ''
    current = ''
    try:
        # resp = requests.get(sw_url, headers=headers, verify=False)
        resp = requests.get(sw_url, headers=headers)
        if resp.status_code != 200:
            print(f"请求失败，状态码：{resp.status_code}")
            return
        data = resp.json()['data'][0]
        if datetime.date.today().strftime('%Y%m%d') != str(data['trading_date']):
            print('申万行情返回日期错误')
            return
        last_day = float(data['l3'])
        now = float(data['l8'])
        increase = str(round(((now - last_day) / last_day) * 100, 2))
        current = str(now)
    except requests.exceptions.RequestException as e:
        print(e)
    except json.JSONDecodeError as e:
        print("JSON解析错误:", e)
    except IndexError as e:
        print("索引错误:", e)
    except Exception as e:
        print("发生错误:", e)
    finally:
        notifyData.append({
            'id': '801150',
            'name': "医药生物",
            'increase': increase,
            'current': current,
            'avg_price': '',
            'href': wx_url + 'plate/200/detail?plateId=01801150',
        })
        print(f"801150\t医药生物\t{increase}")


def notify_with_markdown():
    if len(notifyData) < 2:
        serverJMy("获取上证数据失败，请检查！！", "")
        return
    today = get_today()
    markdown_text = f'''### {today} 行情
| 名称 | 现价 | 涨幅 | 均价 |
|--------|--------|--------|--------|
'''
    for item in notifyData:
        markdown_text += f'| [{item["name"]}]({item["href"]}) | {item["current"]} | {item["increase"]}%| {item["avg_price"]} |\n'
    serverJMy(generate_title(), markdown_text)
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
    # https://github.com/uname-yang/pysnowball/issues/1
    r = requests.get("https://xueqiu.com/hq", headers={"user-agent": "Mozilla"})
    t = r.cookies["xq_a_token"]
    # print(t)
    ball.set_token(f'xq_a_token={t}')
    add_xq_increase('SH000001')
    add_xq_increase('SZ399808')
    add_sw_increase()
    add_xq_increase('CSI930599')
    get_stock_increase()
    notify_with_markdown()
