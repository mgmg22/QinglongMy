#!/bin/env python3
# -*- coding: utf-8 -*
# """
# cron: 5 9 * * * weibo_summary.py
# new Env('豆瓣租房');
# """
from bs4 import BeautifulSoup
import requests
import sendNotify

summary_list = []

# # 排除项
user_black_list = [
    "杨浦租房",
    "五角场租赁",
    "五角场租房",
    "PiNa@上海直租",
    "五角场附近",
    "沪上蜗居小豆豆",
    "🍃 🇨🇳",
    "豆友280014083",
    "瓜瓜一号的墨迹",
    "黄浦区租房",
    "娜娜小夭",
]


def filter_tr(tr):
    # print("-----")
    title = tr.select('td.title')
    if not title:
        return False
    if "置顶" in str(title):
        return False
    user = tr.select('td:nth-child(2)')[0].find('a').get_text()
    if user in user_black_list:
        return False
    text = title[0].find('a')['title']
    # 排除项
    blackList = [
        "女生",
        "闵行",
        "徐家汇",
        "漕河泾",
        "松江",
        "张江",
        "宝山",
        "嘉定",
        "七宝",
        "静安",
        "莘庄",
        "三林",
        "杨思",
        "虹桥",
        "陆家嘴",
        "泗泾",
        "呼兰",
    ]
    if any(sub in text for sub in blackList):
        return False
    time = tr.select('td.time')[0].text
    href = title[0].find('a')['href']
    print(text + '\t\t' + time + '\t\t' + user + '\t\t' + href)
    item = {
        'user': user,
        'title': text,
        'href': href,
        'time': time,
    }
    # print(str(td_text2[0]))


def get_top_summary():
    # url = 'https://www.douban.com/group/wujiaochang/discussion?start=0'
    # url = 'https://www.douban.com/group/383972/discussion?start=0'
    url = 'https://www.douban.com/group/shanghaizufang/discussion?start=0'
    headers = {
        'accept': "*/*",
        'user-agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    data = requests.get(url, headers=headers)
    data.encoding = 'utf-8'
    soup = BeautifulSoup(data.text, 'html.parser')
    tr_elements = soup.select('#content > div > div.article > div:nth-child(2) > table> tr')
    for tr in tr_elements:
        filter_tr(tr)


if __name__ == '__main__':
    get_top_summary()
    # notify_markdown()
