#!/bin/env python3
# -*- coding: utf-8 -*
"""
cron: 1 * * * * weibo_summary.py
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
    if title.startswith("一"):
        print("startswith 一")
        return False
    nameBlackList = [
        # 演员
        "章子怡 成龙 周星驰 王一博 肖战 易烊千玺 王俊凯 王源 吴亦凡 严屹宽",
        "周冬雨 关晓彤 邓超 郑恺",
        "成毅",
        # 歌手
        "周杰伦 王菲 邓紫棋 华晨宇 周深 蔡徐坤 薛之谦 王力宏 田馥甄 萧敬腾 五月天 莫文蔚 吴克群",
        "苏打绿 陶喆 潘玮柏 蔡健雅 梁静茹 周笔畅 何洁 尚雯婕 王铮亮 许嵩 方大同 霉霉",
        # 主持人
        "何炅 撒贝宁",
        # 运动员
        "丁宁 谌龙 宁泽涛 马龙 全红婵 易建联 王楚钦 樊振东 郑钦文 王曼昱 奥运 冠军 丁俊晖 苏炳添 邓亚萍",
        "梅西",
        "运动 户外 篮 球 国足 曼联 湖人 男单 女单 决赛 女双 马拉松 兴奋 跳",
        # 导演
        "徐峥 于正",
        # 脱口秀
        "付鹏 徐志胜 庞博 付航",
        # 其他
        "郎朗 檀健次 王宝强 梁朝伟 吴谨言 高圆圆 周润发 梁家辉 古天乐 王昶 余文乐 郑伊健 代高政 古巨基",
        "关智斌 吴尊  贾静雯 周杰 苏有朋 吴奇隆 言承旭 周渝民 邓婕 海清 吉克隽逸 梁洛施",
        "那英 毛阿敏 韦唯 阎维文 刀郎 降央卓玛 董文华 王二妮 唐嫣 窦骁 邱泽 金晨 尤长靖",
        "许玮甯 吴京 倪妮 井柏然 秦海璐 董洁 王凯 靳东 乐华 沙溢 金星",
        "马天宇 王大陆 伊能静 邓伦 王子文 周也 成毅 任嘉伦",
        "吴宣仪 程潇 毛不易 周慧敏 周雨彤 周柯宇 贺峻霖 申裕斌 柳岩",
        "马伊琍 袁泉 吴彦祖 佘诗曼 王珞丹 马思纯 周华健 周传雄 羽泉 郑源 任贤齐 庾澄庆 邓为 田曦薇",
        "尹净汉 王鹤润 秦岚 范玮琪 徐若瑄 戴佩妮 关淑怡 戚薇 向佐 周扬青 章泽天 范丞丞 胡彦斌 白敬亭",
        "何猷君 徐锦江 范晓萱 听泉 gigi hanni 周震南 费曼 董宇辉 景甜 权志龙 晓华 向太 王祖贤 王鹤棣 钟楚曦",
        "钟睒睒 沙一汀 梅艳芳 周芯竹",
        # 二
        "柯南 唐三",
        # 姓
        "杨 汪 陈 朴 翁 黄 刘 杜 花 林 沈 韩 阮 曾 彭 虞 殷 崔 姚 罗 祝 冉 闵 张 孟 孙 孔 宋 赵 李 魏 谭 曹 郭 冯 霍 朱 蒋 谢 展 叶 荀",
        # 名
        "磊 祺 咪 梓 禹 楷 灿 栩 琦 毓 鑫 莹 豪 琳 帝 俊 楠 婧 娜 皓 霏 霞 惠 莎 丽 蕾 梦 昊 翔 尔",
        # 英文
        "chill belike vivo oppo iqoo vlog cp mbti boy 强森 布朗尼 萨 姆 哈登 cos gq love vip star new baby ins ost cue",
    ]
    gameBlackList = [
        # 游戏
        "和平精英 光遇 王者 荣耀 炉石 鸢 秋季赛 第五人格 星穹铁道 kpl jdg 皮肤 阵容 回归 勇士 联盟 战队 九尾 绝区零 鸣潮 剑网 方舟",
        "电竞 上路 下路 中路 对战 一血 mvp 传奇 国服 退役 ig 复出 金克丝 双城 英雄 签 转会 加盟 队 卫冕 战士",
        "gala theshy uzi mlxg blg",
        "比0 比1 比2 比3 比4 比5 比6 比7 比8 比9 乒 四强 八强 战胜 vs 晋级 输",
        "0分 1分 2分 3分 4分 5分 6分 7分 8分 9分 冠王 连胜 连败",
        "0集 1集 2集 3集 4集 5集 6集 7集 8集 9集 一集",
        "0后 0万",
    ]
    countryList = [
        "北方 南方 东北 海洋 敦煌 灵隐 辽",
        "新疆 青海",
        "中方 法国 巴黎 土耳其 印度 中东 瑞士 印尼 埃及 缅 澳 福岛",
        "台积电 机器",
        # 天气
        "热 冷 季 秋 暖 酸 甜 苦 辣 臭 香 冬 夏 春 雪 寒 太阳 星期 今天 冰 降温 天空 爽",
        # 新闻
        "爆料 自曝 奔现 薅 羊毛 有人 平均 年度 爆款 回应 首都 主持 成人礼 歼 央视",
        # 轻
        "加油 去世 截图 怼 公交 彩蛋 索赔",
        # 负面
        "造谣 吐槽 贫困 烂尾 洗白 不雅 偷 人均 诈 怒喷 逮捕 人贩 双开 烈士 安检 纪委 落 套路 贷 酒后",
        "强奸 猥亵 侵犯 出轨 家暴 性侵 原谅 骚扰 屠 杀 虐 死因 刀 拐",
        "正直 勇敢 慈善 锦旗 捐款 浪费",
        #
        "古 保护 村 乡镇 文化 同意 丝路 官宣 间谍 国防 大使 议员 整治 声明 提高",
    ]
    lifeList = [
        # 人
        "你 丈夫 奶 婴 爷 姐 父 儿 弟 妈 爹 老公 爸 妻 嫂 夫妇 女孩 前夫 友 男子 老人 女子 女生 小伙 宝 年轻 老头 小孩 阿姨 老外 家人 市民",
        # 身份
        "主人 租客 女主播 实习 司机 情侣 保安 教练 导游 博主 当事人 辅警 城管 物业 消防 公安 书记",
        # 生活
        "生活 工 兼职 全职 副业 生日 社交 吵架 骂 转账 晒 相亲 带娃 开除 丁克 会员 地铁 澡 浴 公摊",
        # 物
        "电话 沙发 伞 呐",
        # 学
        "大学 教授 校 清华 浙大 专家 班主任 小学 中学 同学 四六级 师 高一 高二 高三 大一 大二 大三 大四 硕 打卡 早八 迟到 简历 摸鱼 应届 成年 私立 考研 面试 训 肖四 求职 研究生 专业",
        # 健康
        "外卖 预制菜 救人 骨折 奔现 白血病 糖尿 疱疹 癌 血压 献血 一生 卫生 拖延 炎症 症状 嘌呤 针灸 ptsd 受伤 虱 感冒 咳嗽 睡眠 住院 异物 艾滋 hiv 内分泌",
        # 身体
        "身 耳 眼 鼻 屁股 腿 脸 痘 发色 心脏 肺 肾 子宫 牙 体质 驼背 聋哑 尸 帅 好看 胖 瘦 肚子",
        # 衣
        "穿 裤 衣 戒指 镯 搭 妆 面霜 挑染 裙 猴 羽绒 洞洞鞋",
        # 食
        "面包 烤肉 茶 蛋糕 粥 夜宵 良品铺子 泡面 毒 海底捞 烟 饿 炒 蒜 笋 粮",
        # 动物
        "动物 熊 柯基 蛇 鸡 虎 狗 猫 蜂 鼠 鹤 鸟屎 野猪 蝎 鲨鱼 海龟 蟑螂 鹿 钓鱼 羊 宠",
    ]
    otherList = [
        # 单字
        "座 骑 厕 宿 寿 爵 神 枪 瞬 个",
        # 车
        "车 皮卡 宝马 奥迪",
        # 说
        "说 对话 谈 称 聊 告诉",
        # 娱乐
        "团 娱 艺 剧 恋 乐 毯 逝 赛 唱 歌 舞 演 戏 幼 婚 孕 胎 飒 经纪 网红 公司 解约 解散 维密 生图 代言 路透 票房 预告 时尚 收官 钓系 镜头 亮相 海报 刊 出道 拍 分手 秀 名人",
        "开机 追星 长得 辟谣 古装 魅 梗 女装 模仿 影 松弛 耶 顶流 表情 粉 档 照 合约 续约 资源 摄 组合 咖 幕 男主 女主 见面 配角 素人 大片 磕 结局 白月光 番 盛典",
        # 女性
        "名媛 闺蜜 公主 美甲 回购 护肤 断糖 滤镜 媚 吻 依偎 妃 爱 哄 浪漫 国货 中式 月子 造型 温柔 美容 美颜 领证",
        # 动词
        "把 让 为 推 吹",
        # 未发生
        "呼吁 建议 警惕 背后 永远 差点 心愿 未来 可能 相信 网传 快 劝 不再 推进 疑 以为 挑衅 假 真的 明 理解 幻 仙 魂 如果 险 抽",
        # 水
        "这 没认出 再也不 偶遇 童年 证据 盘点 评论区 了解 真正 技巧 辨别 正常 理由 名场面 评测 每天",
        "嘴真严 世上 歉 仪式 江湖 人类 逻辑 状态 早年 付出 反应 格局 发现 奇葩 态度 原因 多数 现代 心路 回忆 区别 含金量",
        # 情绪
        "担心 抑郁 情绪 骗 背锅 值得 恶心 智障 离谱 吧 挺 却 狠狠 狂喜 意难平 后悔 内耗 天塌了 又又 哭 居然 焦虑 吓 没想到 晕 笑 气 差",
        # 表述
        "最 才 还 仍",
        # 问
        "如何 什么 怎么 原来 吗 啥 竟 是懂 到底 谁",
    ]
    if any(word in title for item in nameBlackList for word in item.split()):
        print("in nameBlackList")
        return False
    if any(word in title for item in gameBlackList for word in item.split()):
        print("in gameBlackList")
        return False
    if any(word in title for item in lifeList for word in item.split()):
        print("in lifeList")
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
    else:
        sendNotify.push_me(get_title(), "", "markdata")


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
