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
    "自由奔放",
    "江湖不良人",
    "华夏东路",
    "清风秀雅",
    "灵感之刃",
    "给你俩窝窝",
    "简单点",
    "忧伤的旋律",
    "C",
    "九头奈子",
    "李好闲。",
    "小张要增肌",
    "虚伪的世界",
    "森女与鹿林",
    "提子",
    "悲伤的诗篇",
    "相思成殇",
    "安静的等待",
    "-Joker",
    "豆友279607317",
    "豆友279607320",
    "豆友270169870",
    "豆友279607122",
    "祈鹤",
    "可怜式.暧情",
    "如花美眷",
    "豆友279434723",
    "豆友279434727",
    "从悲伤中抽离",
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
        "女生", "房源", "公积金", "居住证", "钥匙", "别墅",
        "闵行", "徐家汇", "漕河泾", "漕宝", "七宝", "虹桥",
        "松江", "九亭", "莘庄",
        "青浦", "泗泾",
        "宝山", "上海大学", "呼兰", "彭浦",
        "嘉定",
        "浦东", "陆家嘴", "张江", "世纪公园", "龙阳路", "花木",
        "静安",
        "普陀",
        "三林", "杨思", "世博",
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
    summary_list.append(item)


def get_top_summary(start):
    # url = 'https://www.douban.com/group/wujiaochang/discussion?start='+ str(start)
    # url = 'https://www.douban.com/group/383972/discussion?start='+ str(start)
    url = 'https://www.douban.com/group/shanghaizufang/discussion?start=' + str(start)
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
    if len(summary_list) <= 20:
        print("-----")
        get_top_summary(start + 25)


if __name__ == '__main__':
    get_top_summary(0)
    # notify_markdown()
