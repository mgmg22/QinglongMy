#!/bin/env python3
# -*- coding: utf-8 -*
"""
cron: 5 9 * * * weibo_summary.py
new Env('微博热搜');
"""
from bs4 import BeautifulSoup
import requests
import my_notify

summary_list = []


def filter_tr(tr):
    print("-----")
    # 序号、置顶
    td_text1 = tr.select('td.td-01')
    # 超链接 数量
    td_text2 = tr.select('td.td-02')
    # icon 新、热、暖
    td_text3 = tr.select('td.td-03')
    text = td_text2[0].find('a').get_text()
    num = td_text1[0].get_text()
    href = td_text2[0].find('a')['href']
    state = td_text3[0].get_text()
    # print(str(td_text2[0]))
    # 排除项
    blackList = [
        "<span>剧集", "<span>综艺", "<span>演出", "<span>电影", "<span>音乐", "<span>盛典",
        "ad_id=",
        ".png",
    ]
    if any(sub in str(td_text2[0]) for sub in blackList):
        return False
    # 过滤置顶
    if "icon-top" in str(td_text1[0]):
        return False
    item = {
        'title': num + "." + text,
        'href': href,
        'state': state,
    }
    print(str(td_text2[0]))
    summary_list.append(item)


def get_top_summary():
    url = 'https://s.weibo.com/top/summary'
    # todo 环境变量
    headers = {
        'Cookie': "SUB=_2AkMRUtBSf8NxqwFRmfsUxGrkbop-wg7EieKnDiGJJRMxHRl-yT9kql1ZtRB6OtL-vTbTNhcLy7AgHY2b5GT7UADcvUnR;"
    }
    data = requests.get(url, headers=headers)
    data.encoding = 'utf-8'
    soup = BeautifulSoup(data.text, 'html.parser')
    tr_elements = soup.select('#pl_top_realtimehot > table > tbody> tr')
    for tr in tr_elements:
        filter_tr(tr)


def notify_markdown():
    content = '''# 微博热搜'''
    for item in summary_list:
        state_mark = f'【{item["state"]}】' if item['state'] else ''
        content += f'''
[{item['title']}](https://s.weibo.com/{item['href']}){state_mark}
'''
    notify.serverJMy(summary_list[0]["title"], content)
    with open("summary.md", 'w', encoding='utf-8') as f:
        f.write(content)


if __name__ == '__main__':
    get_top_summary()
    notify_markdown()
