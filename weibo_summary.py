#!/bin/env python3
# -*- coding: utf-8 -*
"""
cron: 1 8/1 * * * weibo_summary.py
new Env('微博热搜');
"""
from collections import Counter
from urllib.parse import quote
import requests
import sendNotify
import jieba.analyse
import sqlite3
from datetime import datetime

summary_list = []
conn = sqlite3.connect('wb.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS titles (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        state TEXT NOT NULL
    )
    ''')


def filter_item(realtime_item):
    # 剧集等 辟谣等
    if realtime_item.get('flag_desc'):
        return False
    if realtime_item.get('is_ad'):
        return False
    title = realtime_item['word'].lower().strip()
    state = realtime_item['label_name']
    for row in get_db_data():
        if title == row[1]:
            if state == row[2]:
                print('重复已忽略')
                return False
            if row[2] == '热':
                print('上过热门已忽略')
                return False
            if state == '':
                print('重复可忽略')
                return False
    print(realtime_item)
    nameBlackList = [
        # 演员
        "章子怡 成龙 李连杰 周星驰 郭富城 赵丽颖 王一博 肖战 易烊千玺 王俊凯 王源 鹿晗 吴亦凡 严屹宽",
        "孙俪 周冬雨 张若昀 李现 朱一龙 关晓彤 宋茜 霍建华 邓超 郑恺 李晨 李兰迪",
        "张晚意 成毅",
        # 歌手
        "周杰伦 王菲 张学友 邓紫棋 华晨宇 周深 蔡徐坤 张靓颖 薛之谦 王力宏 张杰 李荣浩 田馥甄 萧敬腾 五月天 孙燕姿 莫文蔚 吴克群",
        "张惠妹 苏打绿 陶喆 潘玮柏 蔡健雅 梁静茹 张韶涵 张宇 周笔畅 何洁 尚雯婕 谭维维 曹格 王铮亮 许嵩 方大同 张震岳 霉霉",
        # 主持人
        "何炅 撒贝宁",
        # 运动员
        "丁宁 谌龙 宁泽涛 张继科 马龙 郭晶晶 全红婵 易建联 孙颖莎 王楚钦 帕尔默 樊振东 郑钦文 王曼昱 奥运 冠军 郭艾伦 潘展乐 丁俊晖 苏炳添",
        "梅西",
        "球 国足 曼联 湖人 男单 女单 决赛 女双 马拉松",
        # 导演
        "冯小刚 徐峥 于正",
        # 脱口秀
        "脱口秀 李诞 付鹏 徐志胜 赵晓卉 庞博 张雪峰 付航",
        # 其他
        "郎朗 檀健次 王宝强 梁朝伟 吴谨言 高圆圆 周润发 张曼玉 梁家辉 古天乐 张家辉 王昶 黎明 谢霆锋 余文乐 郑伊健 谢安琪 代高政 宋仲基 张本智和",
        "关智斌 吴尊  贾静雯 周杰 苏有朋 吴奇隆 言承旭 周渝民 朱孝天 张国立 邓婕 张嘉译 海清 孙红雷 吉克隽逸",
        "那英 毛阿敏 韦唯 谭晶 腾格尔 阎维文 刀郎 降央卓玛 宋祖英 李谷一 董文华 王二妮 唐嫣 赵薇 窦骁 张钧甯 邱泽 金晨 尤长靖",
        "许玮甯 吴京 张译 倪妮 井柏然 张子枫 张一山 秦海璐 潘粤明 董洁 王凯 靳东 蒋欣 乐华 霍思燕 沙溢 金星",
        "张恒 马天宇 王大陆 李沁 秦昊 伊能静 王丽坤 张雨绮 冯绍峰 张翰 邓伦 李一桐 王子文 张哲瀚 周也 成毅 赵露思 白鹿 任嘉伦 谭松韵 张予曦",
        "孟美岐 吴宣仪 魏大勋 程潇 宋威龙 宋轶 张新成 毛不易 张云雷 惠若琪 周慧敏 周雨彤 周柯宇 贺峻霖 申裕斌 柳岩 金莎",
        "马伊琍 袁泉 吴彦祖 佘诗曼 王珞丹 马思纯 孙越 郭麒麟 周华健 李宗盛 周传雄 羽泉 郑源 张信哲 任贤齐 叶珂 庾澄庆 邓为 田曦薇",
        "尹净汉 王鹤润 秦岚 钟丽缇 范玮琪 徐若瑄 戴佩妮 关淑怡 赵今麦 张真源 戚薇 张元英 东北雨姐 佟丽娅 向佐 周扬青 章泽天 张馨予 张云龙 范丞丞 李庚希",
        "何猷君 徐锦江 金秀贤 张棨乔 范晓萱 听泉 时代少年团 gigi hanni 李惠利 周震南 赵一博 费曼 易梦玲 孟佳 董宇辉 景甜 权志龙 晓华 向太 王祖贤 王鹤棣 钟楚曦 徐静蕾",
        "钟睒睒",
        # 姓
        "杨 汪 陈 朴 翁 黄 刘 杜 花 林 沈 韩 阮 曾 彭 虞 殷 崔 姚 罗 祝 冉 闵",
        # 名
        "磊 祺 咪 梓 禹 楷 灿 栩 琦 毓 鑫 莹 豪 琳 帝 俊 楠 婧 娜 皓",
        # 英文
        "chill belike vivo oppo iqoo vlog cp mbti boy 强森 布朗尼 詹姆斯 萨 贝克汉姆 cos gq love vip star new",
    ]
    gameBlackList = [
        # 游戏
        "和平精英 光遇 王者 荣耀 炉石 如鸢 秋季赛 第五人格 原神 星穹铁道 逆水寒 kpl jdg 皮肤 抽卡 阵容 回归 uzi 勇士 联盟 战队 九尾 绝区零 鸣潮 mlxg",
        "电竞 上路 下路 中路 对战 一血 mvp 传奇 战神 国服 退役 ig 复出 金克丝",
        "比0 比1 比2 比3 比4 比5 比6 比7 比8 比9 乒 四强 八强 战胜 vs 晋级 输",
        "0分 1分 2分 3分 4分 5分 6分 7分 8分 9分",
        "0集 1集 2集 3集 4集 5集 6集 7集 8集 9集 一集",
        "0后 0万",
        "大一 大二 大三 大四",
        # 其他
        "海洋 北方 良品铺子 天空",
    ]
    countryList = [
        "法国 土耳其 印度 中东 瑞士 印尼 埃及 缅",
        # 天气
        "热 冷 季 秋 暖 酸 甜 苦 辣 臭 冬 夏 春 雪",
        # 新闻
        "兼职 爆料 奔现 优惠 薅 羊毛 套路 有人 平均 年度 捐款 爆款 带娃 安检 老外 纪委 落 回应 慈善 吵架 首都 逮捕",
        # 轻
        "造谣 后悔 网传 吐槽 贫困 古人 幻 内耗 加油 狂喜 意难平 保护 灵魂 烂尾 尸 疑 悼 去世 澡 贷 截图 洗白 不雅 偷 怼 酒后 公交",
        # 健康
        "外卖 预制菜 救人 跳楼 骨折 奔现 白血病 糖尿 疱疹 癌 血压 献血 一生 卫生 精神 拖延 炎症 症状 嘌呤 针灸 心脏 肺 肾 ptsd 驼背 聋哑 受伤 虱",
        # 动物
        "动物 熊 柯基 蛇 鸡 虎 狗 猫 蜂 鼠 鹤",
    ]
    otherList = [
        # 单字
        "座 骑 厕 车 说 宿",
        # 娱乐
        "女团 娱 艺 剧 恋 乐 毯 逝 赛 歌 舞 演 戏 幼 痘 婚 孕 飒 经纪 网红 公司 解约 解散 维密 首秀 生图 代言 路透 票房 预告 时尚 收官 钓系 镜头 亮相",
        "开机 追星 长得 辟谣 古装 魅 梗 工作室 女装 模仿 影 松弛 耶 顶流 表情 粉丝 感谢 档 照 合约 续约 资源 摄 组合 咖 幕",
        # 女性
        "妆 面霜 名媛 闺蜜 公主 美甲 回购 护肤 断糖 镯 发色 滤镜 身材 相亲 屁股 腿 脸 媚 吻 依偎 鼻 妃 爱 搭 爽 哄 浪漫 眼 国货 中式 月子 挑染",
        "强奸 猥亵 侵犯 出轨 家暴 性侵 原谅",
        # 人称
        "奶 婴 爷 姐 父 儿 弟 妈 爹 老公 妻 嫂 夫妇 女孩 前夫 友 男子 老人 女子 女生 小伙 宝 年轻 老头 小孩",
        # 身份
        "主人 租客 女主播 实习 司机 情侣 全职 村委 保安 开除 丁克 教练 快递 员工 导游",
        # 食物
        "面包 烤肉 茶",
        # 学
        "校 清华 浙大 专家 班主任 小学 中学 同学 四六级 师",
        # 水
        "背锅 什么 值得 到底 差点 没认出 太香了 杀疯了 再也不 告诉 偶遇 怎么 童年 谁能 是懂 抑郁 情绪 骗 证据 盘点 评论区 原来 了解 心愿 吗 真正 恶心 智障 离谱",
        "担心 嘴真严 世上 迟到 歉 简历 副业 狠狠 啥 竟然 仪式 江湖",
    ]
    if any(word in title for item in nameBlackList for word in item.split()):
        print("in nameBlackList")
        return False
    if any(word in title for item in gameBlackList for word in item.split()):
        print("in gameBlackList")
        return False
    if any(word in title for item in countryList for word in item.split()):
        print("in countryList")
        return False
    if any(word in title for item in otherList for word in item.split()):
        print("in otherList")
        return False
    # print(realtime_item)
    item = {
        'num': realtime_item['realpos'],
        'title': title,
        'state': state,
    }
    summary_list.append(item)


def get_hot_search():
    url = 'https://weibo.com/ajax/side/hotSearch'
    resp = requests.get(url)
    resp.encoding = 'utf-8'
    elements = resp.json()['data']['realtime']
    for realtime_item in elements:
        filter_item(realtime_item)


def word_segment():
    jieba.analyse.set_stop_words("stopwords.txt")
    for item in summary_list:
        tags = jieba.analyse.extract_tags(item['title'], topK=20)
        yield from tags


def notify_markdown():
    if summary_list:
        words = word_segment()
        counts = Counter(words)
        # 获取出现频率最高的3个词且次数>1
        markdown_text = ''
        most_common_words = [(word, count) for word, count in counts.most_common(3) if count > 1]
        if most_common_words:
            markdown_text = f'''### {" ".join([f"{word}: {count}" for word, count in most_common_words])}'''
            print(markdown_text)
        for item in summary_list:
            state_mark = f'【{item["state"]}】' if item['state'] else ''
            markdown_text += f'''
{item['num']}.[{item['title']}](https://m.weibo.cn/search?containerid=231522type%3D1%26q%3D{quote(item['title'])}&_T_WM=16922097837&v_p=42){state_mark}
'''
        insert_db(summary_list)
        # sendNotify.push_me(get_title(), markdown_text, "markdown")
        sendNotify.push_me(get_title(), markdown_text, "markdata")
        with open("log_weibo.md", 'w', encoding='utf-8') as f:
            f.write(markdown_text)


def get_title() -> str:
    return str(datetime.now().hour) + "点微博热搜"


def insert_db(list):
    # 使用列表推导式将每个元素转换成元组
    tuples_list = [(x['title'], x['state']) for x in list]
    # 使用 executemany 来插入或替换记录
    cursor.executemany('INSERT OR REPLACE INTO titles (name, state) VALUES (?, ?)', tuples_list)
    conn.commit()


def print_db():
    for row in get_db_data():
        print(row)


def get_db_data():
    cursor.execute('SELECT * FROM titles')
    return cursor.fetchall()


def close_db():
    if cursor:
        cursor.close()
    if conn:
        conn.close()


if __name__ == '__main__':
    try:
        # print_db()
        get_hot_search()
        notify_markdown()
    finally:
        close_db()
