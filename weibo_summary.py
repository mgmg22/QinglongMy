#!/bin/env python3
# -*- coding: utf-8 -*
"""
cron: 5 9 * * * weibo_summary.py
new Env('微博热搜');
"""
from collections import Counter
from bs4 import BeautifulSoup
import requests
import sendNotify

import jieba.analyse

summary_list = []


def filter_tr(tr):
    # print("-----")
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
    nameBlackList = [
        # 演员
        "刘德华 章子怡 成龙 李连杰 周星驰 郭富城 黄晓明 杨幂 赵丽颖 迪丽热巴 王一博 肖战 易烊千玺 王俊凯 王源 鹿晗 吴亦凡 张艺兴 黄子韬 杨洋 张婧仪",
        "刘亦菲 杨颖 郑爽 刘涛 孙俪 周冬雨 刘昊然 张若昀 李现 朱一龙 杨紫 关晓彤 宋茜 吴磊 张天爱 刘诗诗 胡歌 霍建华 陈伟霆 林更新 邓超 陈赫 郑恺 李晨 李兰迪",
        # 歌手
        "周杰伦 王菲 张学友 邓紫棋 华晨宇 周深 蔡徐坤 李宇春 张靓颖 薛之谦 林俊杰 陈奕迅 王力宏 张杰 李荣浩 田馥甄 蔡依林 萧敬腾 五月天 孙燕姿 莫文蔚 吴克群"
        "张惠妹 刘若英 苏打绿 陶喆 潘玮柏 蔡健雅 梁静茹 张韶涵 张宇 周笔畅 何洁 陈楚生 尚雯婕 谭维维 曹格 王铮亮 许嵩 汪苏泷 徐佳莹 方大同 张震岳 霉霉 侃爷",
        # 主持人
        "杜海涛 谢娜 何炅 汪涵 撒贝宁",
        # 运动员
        "孙杨 丁宁 谌龙 傅园慧 宁泽涛 张继科 马龙 郭晶晶 全红婵 易建联 孙颖莎 王楚钦 帕尔默 樊振东 男单 决赛 郑钦文 曼联 热刺 王皓 林孝埈 林诗栋 王曼昱 王艺迪 国足",
        # 导演
        "张艺谋 冯小刚 徐峥 于正",
        # 脱口秀
        "李诞 付鹏 徐志胜 赵晓卉",
        # 其他
        "郎朗 檀健次 王宝强 刘嘉玲 梁朝伟 吴谨言 林志玲 高圆圆 周润发 张曼玉 梁家辉 刘青云 古天乐 张家辉 王昶 黎明 谢霆锋 陈冠希 余文乐 陈小春 郑伊健 谢安琪",
        "容祖儿 杨千嬅 陈慧琳 关智斌 吴尊 陈乔恩 贾静雯 林心如 周杰 苏有朋 吴奇隆 陈志朋 林志颖 言承旭 周渝民 朱孝天 彭于晏 陈道明 张国立 邓婕 陈宝国 张嘉译 海清 孙红雷",
        "孙楠 那英 韩红 毛阿敏 韦唯 谭晶 腾格尔 阎维文 刀郎 凤凰传奇 降央卓玛 宋祖英 李谷一 董文华 王二妮 刘恺威 唐嫣 罗晋 赵薇 黄轩 窦骁 张钧甯 邱泽",
        "陈意涵 许玮甯 吴京 谢楠 张译 黄景瑜 倪妮 井柏然 张子枫 张一山 秦海璐 潘粤明 董洁 王凯 江疏影 靳东 蒋欣 陈晓",
        "张恒 马天宇 王大陆 李沁 秦昊 伊能静 唐艺昕 王丽坤 张雨绮 冯绍峰 张翰 古力娜扎 邓伦 李一桐 王子文 张哲瀚 周也 成毅 赵露思 白鹿 任嘉伦 谭松韵 张予曦",
        "孟美岐 吴宣仪 魏大勋 陈立农 程潇 宋威龙 宋轶 张新成 欧豪 毛不易 张云雷 惠若琪 周慧敏 周雨彤 陈妍希 周柯宇 贺峻霖 陈情令 申裕斌 柳岩 虞书欣",
        "马伊琍 袁泉 吴彦祖 佘诗曼 殷桃 王珞丹 李小冉 马思纯 孙越 郭麒麟 周华健 汪峰 李宗盛 周传雄 刘欢 羽泉 郑源 张信哲 任贤齐 叶珂 庾澄庆 邓为 田曦薇",
        "尹净汉 王鹤润 秦岚 钟丽缇 杨丞琳 范玮琪 徐若瑄 戴佩妮 关淑怡 赵今麦 张真源 戚薇 张元英 东北雨姐 林允儿 佟丽娅 刘宇宁 刘浩存 向佐 周扬青 刘烨 章泽天 张馨予",
    ]
    gameBlackList = [
        "恋与制作人 光遇 王者荣耀 炉石传说 如鸢 秋季赛 第五人格 光与夜之恋 原神",
        # 其他
        "男子 女子 专家 朋友圈 主人 vlog 女团 吻戏 路透 对战 飒 00后 名媛 柯基 赛 收官 闺蜜 男友 租客 弟弟 姐姐 姐妹",
        "到底有多 为什么总是 竟然是",
    ]
    if any(sub in str(td_text2[0]) for sub in blackList):
        return False
    if any(word in str(td_text2[0]) for item in nameBlackList for word in item.split()):
        return False
    if any(word in str(td_text2[0]) for item in gameBlackList for word in item.split()):
        return False
    # 过滤置顶
    if "icon-top" in str(td_text1[0]):
        return False
    item = {
        'num': num,
        'title': text,
        'href': href,
        'state': state,
    }
    # print(str(td_text2[0]))
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


def word_segment():
    jieba.analyse.set_stop_words("stopwords.txt")
    for item in summary_list:
        tags = jieba.analyse.extract_tags(item['title'], topK=20)
        yield from tags


def notify_markdown():
    words = word_segment()
    counts = Counter(words)
    # 获取出现频率最高的3个词和次数
    most_common_words = counts.most_common(3)
    most_common_words_str = " ".join([f"{word}: {count}" for word, count in most_common_words])
    print(most_common_words_str)
    markdown_text = '''# 微博热搜'''
    for item in summary_list:
        state_mark = f'【{item["state"]}】' if item['state'] else ''
        markdown_text += f'''
[{item['num']}.{item['title']}](https://s.weibo.com/{item['href']}){state_mark}
'''
    sendNotify.serverJMy(most_common_words_str, markdown_text)
    with open("log_weibo.md", 'w', encoding='utf-8') as f:
        f.write(markdown_text)


if __name__ == '__main__':
    get_top_summary()
    notify_markdown()
