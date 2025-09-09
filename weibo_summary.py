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
    title = realtime_item.get('title')
    # TODO state
    state = ""
    # for row in get_db_data():
    #     if title == row[1]:
    #         if state == row[2]:
    #             print('重复已忽略')
    #             return False
    #         if row[2] == '热':
    #             print('上过热门已忽略')
    #             return False
    #         if state == '':
    #             print('重复可忽略')
    #             return False
    print(realtime_item)
    if title.startswith("一"):
        print("startswith 一")
        return False
    if title.endswith("了"):
        print("endswith 了")
        return False
    nameBlackList = [
        # 演员
        "章子怡 肖战 严屹宽",
        # 歌手
        "华晨宇 田馥甄 萧敬腾 五月天 莫文蔚 苏打绿 陶喆 霉霉",
        # 主持人
        "撒贝宁",
        # 运动员
        "丁宁 谌龙 宁泽涛 全红婵 奥运 丁俊晖 苏炳添",
        "梅西",
        "运动 户外 篮 球 国足 曼联 湖人 法网 男单 男双 女单 决赛 女双 兴奋 跳 八段 nba cba wtt",
        # 导演
        "于正",
        # 其他
        "郎朗 檀健次 高圆圆 古天乐 余文乐 代高政 古巨基 苏有朋 海清 吉克隽逸 雷佳音",
        "那英 韦唯 阎维文 刀郎 降央卓玛 董文华 金晨 尤长靖 倪妮 井柏然 董洁 靳东 乐华 沙溢 金星",
        "羽泉 任贤齐 田曦薇 章泽天 白敬亭 宁静",
        "听泉 gigi hanni 费曼 董宇辉 景甜 权志龙 沙一汀 单依纯",
        # 二
        "柯南",
        # 姓
        "杨 汪 陈 黄 刘 杜 花 林 韩 虞 殷 崔 姚 罗 祝 张 孟 孙 孔 宋 赵 李 魏 谭 曹 郭 冯 霍 朱 蒋 谢 叶 周 邓 吴",
        "贺 柳 申 付 庞 秦 向 范 伊 唐 贾 展 沈 关 郑 曾 彭 齐 钟 蔡",
        "佘 方 许 尚 程 毛 庾 戚 阮 荀 冉 闵 朴 翁 易 卞 解 庄 黎 祁 傅 何 戴 徐 樊 窦 梁 尹 王 胡 薛 邱 欧阳 潘 袁 成",
        # 名
        "磊 祺 咪 梓 禹 楷 灿 栩 琦 毓 鑫 莹 豪 琳 帝 俊 楠 婧 娜 皓 霏 霞 惠 莎 丽 蕾 梦 昊 翔 尔 晓 嬛 玟 菲 芳 娇 嘉 毅",
        # 英文
        "chill like vivo oppo iqoo vlog cp mbti boy 强森 布朗尼 萨 姆 哈登 cos gq love vip star new baby ins ost cue 库 jennie",
    ]
    gameBlackList = [
        # 游戏
        "和平精英 光遇 荣耀 炉石 鸢 秋季赛 第五人格 星穹铁道 kpl jdg 皮肤 阵容 回归 勇士 联盟 战队 九尾 绝区零 鸣潮 剑 燕云",
        "电竞 评委 上路 下路 中路 对战 一血 mvp 传奇 国服 退 ig 复出 金克丝 双城 英雄 签 转会 加盟 队 卫冕 战士 战术",
        "gala theshy uzi mlxg blg lpl rng solo",
        "比0 比1 比2 比3 比4 比5 比6 比7 比8 比9 乒 四强 八强 战胜 vs 输",
        "0分 1分 2分 3分 4分 5分 6分 7分 8分 9分 冠 连胜 连败 田径",
        "0集 1集 2集 3集 4集 5集 6集 7集 8集 9集 一集",
        "0后 0万",
        "520 1314 521",
    ]
    countryList = [
        "东北 海洋 敦煌 灵隐 辽",
        "西藏 新疆 青海 四川 山东",
        "威海 三亚",
        "法国 土耳其 印度 中东 瑞士 印尼 埃及 缅 澳 朝鲜 迪拜 越南",
        "台积电 机器 甲骨文",
        # 天气
        "热 冷 季 秋 暖 酸 甜 苦 辣 臭 香 冬 夏 春 雨 雪 寒 星期 今天 冰 降温 天空 爽 打雷 空调",
        # 24节气
        "立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至 小寒 大寒"
        # 新闻
        "爆料 自曝 奔现 薅 有人 平均 年度 款 回应 首都 主持 歼 央视 外交 地震 溺 直播 户籍 合同",
        # 轻
        "加油 去世 怼 公交 彩蛋 索赔",
        # 负面
        "造谣 吐槽 贫 烂尾 洗白 不雅 偷 人均 诈 逮捕 人贩 双开 烈士 安检 纪委 落 套路 贷 酒后 赌 贪 市长",
        "强奸 猥亵 侵犯 出轨 性侵 淫 原谅 骚扰 屠 杀 虐 死因 刀 拐 回扣",
        "正直 勇敢 慈善 锦旗 浪费 救人 自律",
        #
        "保护 县 村 乡镇 文化 同意 丝路 官宣 间谍 国防 大使 议员 整治 声明 提高 时代 时光 国旗",
    ]
    lifeList = [
        # 人
        "你 家 丈夫 奶 婴 孩 爷 姐 妹 父 儿 嬷 弟 哥 妈 爹 老公 爸 妻 嫂 叔叔 夫妇 前夫 友 男子 老人 女子 少女 女生 小伙 宝 年轻 老头 阿姨 老外 市民 辈",
        # 身份
        "主人 租客 女主播 实习 司机 情侣 保安 教练 导游 博主 当事人 城管 物业 消防 公安 书记 顾问 警 高管 保洁",
        # 生活
        "生活 工 办公 职 副业 生日 社交 吵架 骂 转账 晒 相亲 带娃 开除 丁克 会员 地铁 澡 浴 睡 公摊 动画 流量",
        # 物
        "电话 沙发 伞 呐 杯 玩具 坟",
        # 学
        "校 清华 浙大 状元 同学 级 师 押 打卡 早八 迟到 简历 摸鱼 应届 私立 考研 面试 训 肖四 裸",
        "教授 小学 中学 初中 高中 高一 高二 高三 大学 大一 大二 大三 大四 研究生 硕 文科 理科 卷",
        "语文 数学 英语 物理 化学 高数 专业",
        # 健康
        "中医 感染 三甲 骨折 奔现 病 疱疹 癌 血压 献血 一生 卫生 拖延 炎症 症状 嘌呤 针灸 ptsd 受伤 虱 感冒 咳嗽 住院 异物 艾滋 hiv 内分泌 烧 甲醛 脊柱 减肥 肠胃 疫苗",
        # 身体
        "身 耳 眼 鼻 屁股 腿 脸 痘 腰 腹 发色 心脏 肺 肾 子宫 牙 背 体质 聋哑 尸 帅 好看 胖 瘦 肚子 手",
        # 衣
        "穿 裤 衣 戒指 镯 搭 妆 面霜 挑染 裙 羽绒 鞋 ootd",
        # 食
        "外卖 食物 面包 烤肉 茶 蛋糕 粥 夜宵 良品铺子 泡面 毒 海底捞 烟 饿 炒 蒜 笋 粮 厨 蛋挞 粽 提拉米苏 饺",
        # 水果
        "榴莲 荔枝 瓜 梨 莓",
        # 动物
        "动物 熊 柯基 鼠 虎 兔 龙 蛇 马 羊 猴 鸡 狗 野猪 猫 鸭 鹅 蜂 鹤 鸟屎 蝎 鲨鱼 海龟 蟑螂 鹿 钓鱼 宠 狼 蝶",
    ]
    otherList = [
        # 单字
        "座 骑 厕 宿 寿 爵 神 枪 瞬 个",
        # 车
        "车 皮卡 奥迪 法拉利 科三",
        # 说
        "说 对话 谈 称 聊 诉 喊 言 发文",
        # 娱乐
        "节目 团 娱 艺 剧 恋 乐 毯 逝 赛 唱 歌 舞 演 戏 幼 婚 孕 胎 飒 经纪 网红 公司 yb 维密 路透 票房 收官 钓系 镜头 亮相 海报 刊 出道 拍 秀 名人",
        "开机 追星 长得 辟谣 古装 魅 梗 女装 模仿 影 松弛 耶 顶流 表情 粉 档 照 合约 续约 资源 摄 组合 咖 幕 男主 女主 见面 素人 大片 磕 结局 白月光 番 盛典 广告 主题 宴",
        # 女性
        "名媛 闺蜜 公主 美甲 回购 护肤 糖 滤镜 媚 吻 依偎 妃 爱 哄 浪漫 国货 中式 月子 造型 温柔 美容 领证 图 颜",
        # 动词
        "把 让 为 推 吹 走 攒 裁 冲",
        # 未发生
        "呼吁 建议 永远 差点 心愿 未 可能 相信 网传 快 劝 不再 推进 疑 以为 挑衅 假 真的 明 幻 仙 魔 魂 如果 险 抽 预 命运 提名 福 不得 人鱼 看好",
        # 水
        "这 没认出 再也不 偶遇 证据 盘点 评论区 真正 技巧 辨别 正常 理由 名场面 评测 每天 节奏 规律 复盘 燃 已读 泪 班 管理",
        "嘴真严 世上 歉 仪式 江湖 人类 逻辑 状态 早年 反应 格局 发现 奇葩 态度 原因 多数 现代 心路 回忆 区别 含金量 知道 有多 高能",
        # 情绪
        "担心 抑郁 情绪 骗 值得 恶心 智障 离谱 吧 挺 却 狠狠 狂喜 后悔 内耗 又又 哭 居然 焦虑 吓 没想到 晕 笑 气 差 怒 破防 尊重",
        # 时间
        "古 童年 早期 此刻 历史",
        # 表述
        "最 才 还 仍 只 观 佩服 终于 太 配 难 一定 口碑 一起 稳健 不能 优质",
        # 问
        "什么 怎么 原来 吗 啥 竟 是懂 到底 谁 哪 答",
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
        # 'num': realtime_item['realpos'],
        'title': title,
        'state': state,
    }
    summary_list.append(item)


def get_hot_search():
    url = 'https://m.weibo.cn/api/container/getIndex?containerid=106003type%3D25%26t%3D3%26disable_hot%3D1%26filter_type%3Drealtimehot'
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    }
    resp = requests.get(url, headers=headers)
    resp.encoding = 'utf-8'

    try:
        data = resp.json()
        cards = data['data']['cards'][0]['card_group']
    except (KeyError, IndexError, requests.exceptions.JSONDecodeError) as e:
        print(f"解析错误: {e}")
        print(resp.json())
        return []

    result = []
    for i, k in enumerate(cards):
        if i == 0:
            continue
        if not k.get('desc'):
            continue

        actionlog = k.get('actionlog', {})
        if actionlog and 'ext' in actionlog and "ads_word" in actionlog['ext']:
            continue

        # 手动URL编码
        query = k['desc'].replace(' ', '%20').replace('#', '%23').replace('&', '%26')

        item = {
            'id': k['desc'],
            'title': k['desc'],
            'extra': {'icon': None},
            'url': f"https://s.weibo.com/weibo?q=%23{query}%23",  # 手动添加 # 的编码 %23
            'mobileUrl': k.get('scheme')
        }

        # TODO state
        if k.get('icon'):
            item['extra']['icon'] = {
                'url': k['icon'],
                'scale': 1.5
            }
        result.append(item)
        filter_item(item)


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
[{item['title']}](https://m.weibo.cn/search?containerid=231522type%3D1%26q%3D{quote(item['title'])}&_T_WM=16922097837&v_p=42){state_mark}
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
