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
]


def filter_tr(tr):
    print("-----")
    title = tr.select('td.title')
    if not title:
        return False
    if "置顶" in str(title):
        return False
    user = tr.select('td:nth-child(2)')[0].find('a').get_text()
    if user in user_black_list:
        return False
    text = title[0].find('a')['title']
    time = tr.select('td.time')[0].text
    href = title[0].find('a')['href']
    print(text + '\t\t' + href + '\t\t' + user + '\t\t' + time)
    item = {
        'user': user,
        'title': text,
        'href': href,
        'time': time,
    }
    # print(str(td_text2[0]))


def get_top_summary():
    url = 'https://www.douban.com/group/wujiaochang/discussion?start=0'
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
