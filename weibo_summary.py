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
        "章子怡 成龙 李连杰 周星驰 郭富城 赵丽颖 王一博 肖战 易烊千玺 王俊凯 王源 鹿晗 吴亦凡 张婧仪 严屹宽",
        "郑爽 孙俪 周冬雨 张若昀 李现 朱一龙 关晓彤 宋茜 吴磊 张天爱 胡歌 霍建华 邓超 郑恺 李晨 李兰迪",
        "张晚意 成毅",
        # 歌手
        "周杰伦 王菲 张学友 邓紫棋 华晨宇 周深 蔡徐坤 李宇春 张靓颖 薛之谦 王力宏 张杰 李荣浩 田馥甄 萧敬腾 五月天 孙燕姿 莫文蔚 吴克群 龚琳娜",
        "张惠妹 苏打绿 陶喆 潘玮柏 蔡健雅 梁静茹 张韶涵 张宇 周笔畅 何洁 尚雯婕 谭维维 曹格 王铮亮 许嵩 徐佳莹 方大同 张震岳 霉霉 侃爷",
        # 主持人
        "谢娜 何炅 撒贝宁",
        # 运动员
        "丁宁 谌龙 宁泽涛 张继科 马龙 郭晶晶 全红婵 易建联 孙颖莎 王楚钦 帕尔默 樊振东 男单 女单 决赛 郑钦文 曼联 王皓 王曼昱 国足 奥运 冠军 郭艾伦 潘展乐",
        "梅西",
        # 导演
        "冯小刚 徐峥 于正",
        # 脱口秀
        "脱口秀 李诞 付鹏 徐志胜 赵晓卉 庞博 张雪峰",
        # 其他
        "郎朗 檀健次 王宝强 梁朝伟 吴谨言 高圆圆 周润发 张曼玉 梁家辉 古天乐 张家辉 王昶 黎明 谢霆锋 余文乐 郑伊健 谢安琪",
        "容祖儿 关智斌 吴尊  贾静雯 周杰 苏有朋 吴奇隆 言承旭 周渝民 朱孝天 彭于晏 张国立 邓婕 张嘉译 海清 孙红雷",
        "孙楠 那英 韩红 毛阿敏 韦唯 谭晶 腾格尔 阎维文 刀郎 凤凰传奇 降央卓玛 宋祖英 李谷一 董文华 王二妮 唐嫣 罗晋 赵薇 窦骁 张钧甯 邱泽",
        "许玮甯 吴京 谢楠 张译 倪妮 井柏然 张子枫 张一山 秦海璐 潘粤明 董洁 王凯 江疏影 靳东 蒋欣 乐华 霍思燕 沙溢 金星",
        "张恒 马天宇 王大陆 李沁 秦昊 伊能静 王丽坤 张雨绮 冯绍峰 张翰 古力娜扎 邓伦 李一桐 王子文 张哲瀚 周也 成毅 赵露思 白鹿 任嘉伦 谭松韵 张予曦",
        "孟美岐 吴宣仪 魏大勋 程潇 宋威龙 宋轶 张新成 欧豪 毛不易 张云雷 惠若琪 周慧敏 周雨彤 周柯宇 贺峻霖 申裕斌 柳岩 虞书欣 丁程鑫",
        "马伊琍 袁泉 吴彦祖 佘诗曼 殷桃 王珞丹 李小冉 马思纯 孙越 郭麒麟 周华健 李宗盛 周传雄 羽泉 郑源 张信哲 任贤齐 叶珂 庾澄庆 邓为 田曦薇",
        "尹净汉 王鹤润 秦岚 钟丽缇 范玮琪 徐若瑄 戴佩妮 关淑怡 赵今麦 张真源 戚薇 张元英 东北雨姐 佟丽娅 向佐 周扬青 章泽天 张馨予",
        "何猷君 徐锦江 金秀贤 曹宝儿 骆鑫 张棨乔 范晓萱 听泉 时代少年团 gigi hanni 韩素希 李惠利 鞠婧祎 周震南 赵一博 费曼 易梦玲 孟佳 董宇辉",
        # 姓
        "杨 汪 陈 朴 翁 黄 刘 杜 花 林",
        # 单字
        "娱 艺 婚 孕 飒 爷 尸 师 友 赛 癌 妆 热 冷 座 贷",
        "比0 比1 比2 比3 比4 比5 比6 比7 比8 比9 乒 四强 八强 战胜 vs 晋级 输",
        "0分 1分 2分 3分 4分 5分 6分 7分 8分 9分",
        "0后",
        # 英文
        "chill belike vivo oppo vlog cp mbti 强森 布朗尼",
    ]
    gameBlackList = [
        "恋与制作人 光遇 王者 炉石 如鸢 秋季赛 第五人格 光与夜之恋 原神 星穹铁道 kpl 皮肤 抽卡 阵容 回归 uzi 勇士 联盟",
        "沈星回",
        # 其他
        "男子 老人 女子 小伙 女孩 女儿 专家 主人 夫妇 女团 对战 名媛 柯基 闺蜜 租客 弟弟 姐 妈 生图 代言 儿子 父亲 钓系 公主 演员 维密 首秀 班主任 情侣 老公",
        "清华 童年 女主播 歌手 车主 实习 司机 小学",
        "恋综 宝 吻戏 路透 票房 预告 时尚 强奸 猥亵 侵犯 出轨 美甲 回购 护肤 跳楼 骨折 奔现 优惠 收官 预制菜 兼职 公司 解约 解散 经纪 网红 救人 校",
        "到底有多 为什么总是 竟然是 值得 到底是 海洋 谁能 北方 是懂 抑郁 情绪 骗 0万 嫌疑 证据 飞机 差点 没认出 太香了",
    ]
    countryList = [
        "法国 土耳其 印度 中东",
    ]
    title = str(td_text2[0]).lower()
    if any(sub in title for sub in blackList):
        return False
    if any(word in title for item in nameBlackList for word in item.split()):
        return False
    if any(word in title for item in gameBlackList for word in item.split()):
        return False
    if any(word in title for item in countryList for word in item.split()):
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
