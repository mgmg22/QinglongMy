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
        "孙俪 周冬雨 李现 朱一龙 关晓彤 宋茜 霍建华 邓超 郑恺 李晨 李兰迪 惠英红",
        "成毅",
        # 歌手
        "周杰伦 王菲 邓紫棋 华晨宇 周深 蔡徐坤 薛之谦 王力宏 李荣浩 田馥甄 萧敬腾 五月天 孙燕姿 莫文蔚 吴克群",
        "苏打绿 陶喆 潘玮柏 蔡健雅 梁静茹 周笔畅 何洁 尚雯婕 谭维维 曹格 王铮亮 许嵩 方大同 霉霉",
        # 主持人
        "何炅 撒贝宁",
        # 运动员
        "丁宁 谌龙 宁泽涛 马龙 郭晶晶 全红婵 易建联 孙颖莎 王楚钦 帕尔默 樊振东 郑钦文 王曼昱 奥运 冠军 郭艾伦 潘展乐 丁俊晖 苏炳添 邓亚萍",
        "梅西",
        "球 国足 曼联 湖人 男单 女单 决赛 女双 马拉松 兴奋",
        # 导演
        "冯小刚 徐峥 于正",
        # 脱口秀
        "脱口秀 李诞 付鹏 徐志胜 赵晓卉 庞博 付航",
        # 其他
        "郎朗 檀健次 王宝强 梁朝伟 吴谨言 高圆圆 周润发 梁家辉 古天乐 王昶 黎明 谢霆锋 余文乐 郑伊健 谢安琪 代高政 宋仲基 古巨基",
        "关智斌 吴尊  贾静雯 周杰 苏有朋 吴奇隆 言承旭 周渝民 朱孝天 邓婕 海清 孙红雷 吉克隽逸 梁洛施",
        "那英 毛阿敏 韦唯 谭晶 腾格尔 阎维文 刀郎 降央卓玛 宋祖英 李谷一 董文华 王二妮 唐嫣 赵薇 窦骁 邱泽 金晨 尤长靖",
        "许玮甯 吴京 倪妮 井柏然 秦海璐 潘粤明 董洁 王凯 靳东 蒋欣 乐华 霍思燕 沙溢 金星",
        "马天宇 王大陆 李沁 秦昊 伊能静 王丽坤 冯绍峰 邓伦 李一桐 王子文 周也 成毅 赵露思 白鹿 任嘉伦 谭松韵",
        "吴宣仪 魏大勋 程潇 宋威龙 宋轶 毛不易 惠若琪 周慧敏 周雨彤 周柯宇 贺峻霖 申裕斌 柳岩 金莎",
        "马伊琍 袁泉 吴彦祖 佘诗曼 王珞丹 马思纯 孙越 郭麒麟 周华健 李宗盛 周传雄 羽泉 郑源 任贤齐 叶珂 庾澄庆 邓为 田曦薇",
        "尹净汉 王鹤润 秦岚 钟丽缇 范玮琪 徐若瑄 戴佩妮 关淑怡 赵今麦 戚薇 东北雨姐 佟丽娅 向佐 周扬青 章泽天 范丞丞 李庚希 胡彦斌",
        "何猷君 徐锦江 金秀贤 范晓萱 听泉 gigi hanni 李惠利 周震南 赵一博 费曼 易梦玲 董宇辉 景甜 权志龙 晓华 向太 王祖贤 王鹤棣 钟楚曦 徐静蕾",
        "钟睒睒 唐三 大冰 辛芷蕾 沙一汀 梅艳芳",
        # 姓
        "杨 汪 陈 朴 翁 黄 刘 杜 花 林 沈 韩 阮 曾 彭 虞 殷 崔 姚 罗 祝 冉 闵 张 孟",
        # 名
        "磊 祺 咪 梓 禹 楷 灿 栩 琦 毓 鑫 莹 豪 琳 帝 俊 楠 婧 娜 皓 霏",
        # 英文
        "chill belike vivo oppo iqoo vlog cp mbti boy 强森 布朗尼 詹姆斯 萨 贝克汉姆 cos gq love vip star new baby ins ost cue",
    ]
    gameBlackList = [
        # 游戏
        "和平精英 光遇 王者 荣耀 炉石 如鸢 秋季赛 第五人格 原神 星穹铁道 kpl jdg 皮肤 抽卡 阵容 回归 uzi 勇士 联盟 战队 九尾 绝区零 鸣潮 mlxg 剑网",
        "电竞 上路 下路 中路 对战 一血 mvp 传奇 战神 国服 退役 ig 复出 金克丝 双城 英雄 签 转会 队",
        "比0 比1 比2 比3 比4 比5 比6 比7 比8 比9 乒 四强 八强 战胜 vs 晋级 输",
        "0分 1分 2分 3分 4分 5分 6分 7分 8分 9分 冠王 连胜",
        "0集 1集 2集 3集 4集 5集 6集 7集 8集 9集 一集",
        "0后 0万",
        # 其他
        "海洋 北方 天空 李白 评测",
        # 衣
        "裤 内衣 戒指 镯 搭 妆 面霜 挑染 裙 猴 羽绒",
    ]
    countryList = [
        "法国 土耳其 印度 中东 瑞士 印尼 埃及 缅 澳",
        # 天气
        "热 冷 季 秋 暖 酸 甜 苦 辣 臭 冬 夏 春 雪 寒 太阳 星期 今天",
        # 新闻
        "兼职 爆料 自曝 奔现 优惠 薅 羊毛 套路 有人 平均 年度 捐款 爆款 带娃 安检 老外 纪委 落 回应 慈善 吵架 首都 逮捕 主持 成人礼 人贩 双开 烈士 歼 锦旗",
        # 轻
        "造谣 网传 吐槽 贫困 古人 幻 加油 保护 魂 烂尾 尸 疑 去世 澡 贷 截图 洗白 不雅 偷 怼 酒后 公交 诈 怒喷 彩蛋 未来 人均 可能",
        # 健康
        "外卖 预制菜 救人 跳楼 骨折 奔现 白血病 糖尿 疱疹 癌 血压 献血 一生 卫生 精神 拖延 炎症 症状 嘌呤 针灸 心脏 肺 肾 ptsd 驼背 聋哑 受伤 虱 感冒 咳嗽 睡眠 住院 异物 子宫",
        # 动物
        "动物 熊 柯基 蛇 鸡 虎 狗 猫 蜂 鼠 鹤 鸟屎 野猪 蝎",
    ]
    otherList = [
        # 单字
        "座 骑 厕 车 说 宿",
        # 娱乐
        "团 娱 艺 剧 恋 乐 毯 逝 赛 唱 歌 舞 演 戏 幼 痘 婚 孕 飒 经纪 网红 公司 解约 解散 维密 首秀 生图 代言 路透 票房 预告 时尚 收官 钓系 镜头 亮相 海报 出道",
        "开机 追星 长得 辟谣 古装 魅 梗 工作室 女装 模仿 影 松弛 耶 顶流 表情 粉 感谢 档 照 合约 续约 资源 摄 组合 咖 幕 男主 见面 配角 大秀 素人 大片 磕 人气 明星 杀青",
        # 女性
        "名媛 闺蜜 公主 美甲 回购 护肤 断糖 发色 滤镜 身材 相亲 屁股 腿 脸 媚 吻 依偎 鼻 妃 爱 爽 哄 浪漫 眼 国货 中式 月子 造型 好看 温柔 美容 美颜",
        "强奸 猥亵 侵犯 出轨 家暴 性侵 原谅 骚扰",
        "正直 勇敢",
        # 人称
        "你 丈夫 奶 婴 爷 姐 父 儿 弟 妈 爹 老公 爸 妻 嫂 夫妇 女孩 前夫 友 男子 老人 女子 女生 小伙 宝 年轻 老头 小孩",
        # 身份
        "主人 租客 女主播 实习 司机 情侣 全职 村委 保安 开除 丁克 教练 快递 员工 导游 博主 当事人 辅警",
        # 食物
        "面包 烤肉 茶 蛋糕 粥 夜宵 良品铺子 泡面 毒",
        # 动词
        "把",
        # 学
        "大学 教授 校 清华 浙大 专家 班主任 小学 中学 同学 四六级 师 大一 大二 大三 大四 打卡 早八 迟到 简历",
        # 水
        "这 差点 没认出 再也不 告诉 偶遇 童年 证据 盘点 评论区 了解 心愿 真正 神器 社交 技巧 辨别 建议 警惕",
        "嘴真严 世上 歉 副业 仪式 江湖 人类 生日 逻辑 状态 早年 付出 反应 格局",
        # 情绪
        "担心 抑郁 情绪 骗 竟 背锅 值得 恶心 智障 离谱 太香了 杀疯了 吧 挺 却 狠狠 狂喜 意难平 悼 后悔 内耗 天塌了 又又 哭",
        # 问
        "如何 什么 怎么 原来 吗 啥 竟然 谁能 是懂 到底",
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
