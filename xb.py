#!/bin/env python3
# -*- coding: utf-8 -*-
"""
cron: 3/30 8/1 * * * xb.py
new Env('线报0818');
"""
from bs4 import BeautifulSoup
import requests
from date_utils import get_day_string
from sendNotify import is_product_env, dingding_bot_with_key, send_wx_push
import sqlite3
import re
import asyncio
from openai_utils import AIHelper
from dotenv import load_dotenv
import json

key_name = "xb"
xb_list = []


class DBHelper:
    def __init__(self, db_name):

        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS titles (
            id INTEGER PRIMARY KEY,
            path INTEGER,
            name TEXT UNIQUE NOT NULL,
            href TEXT NOT NULL
        )
        ''')

    def insert_many(self, items):
        tuples_list = [(x['path'], x['title'], x['href']) for x in items]
        self.cursor.executemany('INSERT OR IGNORE INTO titles (path,name, href) VALUES (?, ?, ?)', tuples_list)
        self.conn.commit()

    def fetch_all(self):
        self.cursor.execute('SELECT * FROM titles')
        return self.cursor.fetchall()

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    conn = sqlite3.connect(f'{key_name}.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS titles (
        id INTEGER PRIMARY KEY,
        path INTEGER,
        name TEXT UNIQUE NOT NULL,
        href TEXT NOT NULL
    )
    ''')


db = DBHelper(f'{key_name}.db')
load_dotenv()

cxkWhiteList = ["中国银行", "中行", "农业银行", "农行", "交通银行", "交行", "浦发", "邮储", "邮政", "光大", "兴业",
                "平安", "浙商", "杭州银行", "北京银行", "宁波银行"]


def has_white_bank_name(content):
    return any(sub in content for sub in cxkWhiteList)


whiteWordList = [word for item in [
    "云闪付 ysf xyk 性用卡 还款 工商银行 工商 工行 工银 e生活 建设银行 建行 建融 招商银行 招行 掌上生活 体验金 中信 动卡空间",
    "手淘 天猫 猫超 支付宝 zfb 转账 某付宝 微信 wx vx v.x 小程序 立减金 ljj 公众号 原文 推文 京东 狗东 jd 京豆 e卡 美团 elm",
    # "淘宝 tb 抖音 dy 闲鱼 同程 携程 途牛 霸王茶姬",
    "水 必中 红包 虹包 抽奖 秒到 保底 游戏 下载 话费 移动 和包 电信 q币 扣币 麦当劳 肯德基 必胜客 星巴克 瑞幸 朴朴 喜茶 礼品卡 星礼卡 深圳通 网上国网",
    "国补",
] for word in item.split()]


def has_white_word(content):
    return any(sub in content for sub in whiteWordList)


def has_black_xyk_name(content):
    xykNameList = ["xing/用卡", "信用卡", "xing用卡", "信用k", "心用卡", "性用卡", "xyk", "信y卡", "深圳"]
    return any(sub in content for sub in xykNameList) and has_white_bank_name(content)


def get_complete_content(content):
    # print(content)
    # Replace <br/> tags with newline characters before getting text
    for br in content.find_all('br'):
        br.replace_with('\n')
    text = content.get_text()
    # Find all 'a' tags in the content
    a_tags = content.find_all('a')
    for a_tag in a_tags:
        href = a_tag.get('href')
        if href:
            # Get the original text that contains this link
            original_text = a_tag.get_text()
            if re.search(r'http[s]?://\S+', original_text):
                # Replace the original text with markdown format
                markdown_link = f'[{href}]({href})'
                text = text.replace(original_text, markdown_link)
    return text


commonBlackList = [word for item in [
    "定位 部分 东北 徽 限深圳 北京 天津 重庆 深圳地区 山东 福建 江苏 云南 江西 河北 广东 吉林 湖北 河南 陕西 湖南 四川 宁夏 广西 辽宁 甘肃 内蒙古 青海 贵州 山西 新疆",
    "厦门 南京 东莞 广州 南海 苏州 中山 常州 青岛 成都 武汉 合肥 揭阳 无锡 济南 大连 石家庄 泉州 丹东 茂名 长沙 泰州 郑州 惠州 威海 绍兴 哈尔滨 贵阳",
    # ----卡----
    "万事达 visa 车主 刷卡达标 北分 陆金所 缤纷生活 浦大喜奔 邮储联名 美团联名 闪光卡 联名卡 邮政数币 农行刷卡金 农行数币 会员返现 兴业生活 农信 颜卡",
    "交通银行数币 交行数币 交通数币 光大麦当劳 阳光惠生活 光大石化 广发 恒丰 汇丰 农商 苏银 善融 百信 宝石山 众邦 兴农通 黑卡",
    # ----无效----
    "特邀 受邀 瘦腰 收腰 临期 值得买",
    # ----超链接----
    "vip.iqiyi.com 出门靠朋友 深i工 今天多少 55618 【888】",
    # ----问题----
    "么 问题 问问 问下 谢谢 请问 问一下 别问 请教 求 咋 怎样 咨询 赐教 啥 有问 行不 何解 不行 原因 帮忙看 哪来的 都多少 是多少 是不是 有谁 大佬",
    "果熟 有果 油果 彦祖 亦菲 多不 谁有 有没 如何 预算 你们都 几号 到底 多少出 哥哥们",
    # ----数码----
    "华为 huawei 荣耀手机 mipay 果子 苹果 iphone airpods pm 亚瑟 大疆 数据 k70",
    # ----生活居家----
    "內衣 拖鞋 洞洞鞋 购物袋 布袋 婴 童装 小孩 孩子 辣妈 无线 牙膏 拉拉裤 伞 锅 电动车 盔 清风 纸 维达 杯 椅 菌 石头 奥妙 家政 冈本 南极人 巾 染 一次性 蚊香 容声 沐浴 力士",
    # ----风险----
    "风险 美元 提额 保险 开通 境外 秒批 下卡 开户 贷 征信 费率 pos 人脸 审批 黄牛 客服 天天基金 东方财富",
] for word in item.split()]
highBlackList = [word for item in [
    # ----玩法----
    "【顶】 需要邀请 助力 人团 拼团 调研 申请x 互助 攒能量 组队 组团 首单 盲盒 月黑风高 互换 入会 买1送1 买一送一 蒸蒸日上 淘宝秒杀 必免 膨胀",
    # ----网购----
    "00g 支 件 /袋 /盒 /斤 箱 罐 xl 货 瓶 降 9.9 如有 折合 到手 买家 小法庭 单号 预售 话术 拆单 查询 高佣 想买 尾款 小黄鱼 放量 dy商城 二手 出售",
    # ----形容词----
    "限量 健康 地道 进口 真诚 厉害 有点6 骚 不要脸 蛋疼 奇怪 大事 谱 恶心 太乱 太贵 真的 好玩",
    # "瓶 返 凑",
    # ----语气符号----
    "呢 呀! 吧？ 啦 ！ 了。。 了吧 了啊 啊~ 。。。",
    # ----情绪----
    "卧槽 逼 牛b 还好 根本 有点东西 感觉 居然 感谢 心态 无语 毛线 怨 真是 无耻 便宜啊 麻烦 不如不 狗了 差了 终于 太次了 不想搞 只有 不服 见过 竟然",
    "太难 看到 发财 咱 口感 妥妥 死活 就这 狗屁 感受 没想到 兄弟们 后悔 吐槽",
    # ----负面----
    "不能 删了 续费 限制使用 冻结 被盗 差评 监控 套牢 猫饼 怀疑 不知道 黑心 没有 想法 网友 公司 挤 上科技 不友好 骗 返买 反买 关闭 闲谈 投诉 虚假 进群",
    "被封 禁 修复 盾 砍 赔 秒退 限额 吧里 赖 水贴 吐了 真的假的 妹 聊 惨 起诉 粪 女生 感冒",
    # ----时效----
    "以后 即将 过期 长期出 逾期 防身 前10 前年 收到短信 上个月 改规则 几秒 忘记 想起 明天 变了 删除 最近 上次 可是 老",
    # ----end----
    "黄了 没了 下线 凉了 领不了 领完 我才 没抢到 没到 未到账 不到账 凉凉 抢不到 上限 退款 不给 砍单 抢光 不可用 审核 捡漏 领不到",
    "翻车 失败 崩溃 崩了 黑号 号黑 拦截 卸载 火爆 销户 垃圾 风控 不玩了 来电",
    # ----虚拟----
    "高德 工行码 吧码 迅雷 电子书 车险 模板 etc",
    # ----不符合预期的词语----
    "没水 的水 漏水 纯水 碱水 水果 水雾 吸水 精萃水 精华水 净水 补水 花露水 热水 玻璃水 口水 缩水 水龙 水润 水牛 水枪 香水 水壶 水蜜 沥水 水乳 卸妆水 防水 饮水 水泡 水感 水饺 水杨 水器 水卫",
    "签到红包 返红包 返虹包 游戏私服 游戏账号 朋友圈 转网 cm ml",
] for word in item.split()]
lowBlackList = [word for item in [
    "多拍 券包 免单 预售 试用 点秒杀 以旧换新 小程序下单 直播间下单 折券 津贴",
    # ----食品----
    "三只松鼠 百草味 海底捞 认养一头牛 火锅 烧烤 麻辣烫 馋 卤 炖 火腿 爪 蛋白 豆浆 维生素 麦片 飞鹤 粥 面 小麦 米线 粉 粮 裙带菜 蒜 阿胶 巧克力 糖 蛋挞",
    # ----生鲜----
    "巧乐兹 梦龙 可生食 羊肉 虾 粽 笋 大闸蟹 海参 榴莲 梨 柠檬 香菇 鲜花 莓 玫瑰 酸菜 雪糕 冰淇淋 柿 脐橙 瓜",
    # ----饮料----
    "饮料 果汁 百岁山 农夫 矿泉水 茅台 酒 窖 特仑苏 椰子 茶叶 观音 奶茶 coco 奈雪 蜜雪 茶百道 古茗 库迪 口服",
    # ----美妆个护----
    "美妆 珀莱雅 雅诗兰黛 毛戈平 潘婷 屈臣氏 大宝 金纺 立白 科颜氏 林清轩 欧莱雅 苏菲 蔻 洗 眉 唇 泥 日抛 护理 采销 卫生 敏感肌 保湿 美白 防晒 精粹 海蓝 口罩 olay 薇 美瞳",
    # ----其他实物----
    "佛 机油 宠物 翡翠 轮胎 图书 小家电",
    # ----品牌----
    "第三方 京造 京东买药 严选 喵满分 李佳琦 工厂 宇辉",
    # ----虚拟卡券----
    "火车 电影 门票 打车 顺风车 养车 流量 gb 出行优惠券 网盘 地铁 网易云 机票 别墅 顺丰 快递 充电 民宿 芒果 年卡 腾讯视频 体检",
    # ----线下门店----
    "沪上阿姨 永和大王 沃尔玛 永辉 盒马 联华 costa 桌游 米其林 奥特莱斯 试驾",
    # ----无效----
    "plus yzf 翼支付 svip 联通 移动套餐 美团圈圈 王卡 钻石会员 铂金 黑金 腾讯vip 聚惠出行 凡科",
] for word in item.split()]


def filter_list(tr):
    title = tr.get_text().lower().strip()
    if title.endswith("？" or "?"):
        return False
    if tr['href'].startswith("http"):
        return False
    if "618.html" in tr['href']:
        return False
    href = 'http://www.0818tuan.com' + tr['href']
    match = re.search(r'/xbhd/(\d+)\.html', href)
    path_id = int(match.group(1))
    if has_black_xyk_name(title):
        print("----无该行信用卡，已忽略" + '\t\t' + href)
        return False
    all_blacklist = set(commonBlackList) | set(highBlackList) | set(lowBlackList)
    if any(sub in title for sub in all_blacklist):
        return False
    if not has_white_word(title) and not has_white_bank_name(title):
        return False
    for row in db.fetch_all():
        if path_id == row[1]:
            print('重复已忽略')
            return False
    content = get_content(href)
    # print(content)
    for checkItem in commonBlackList:
        if content and checkItem in content.get_text():
            print(f"{checkItem}\t\t----关键字不合法，已忽略\t\t{href}")
            return False
    text = get_complete_content(content).strip()
    img_tags = content.find_all('img')
    src_list = []
    for img in img_tags:
        img_url = img.get('src')
        src_list.append(img_url)
    print(title + '\t\t' + href)
    item = {
        'title': title,
        'path': path_id,
        'href': href,
        'text': text,
        'src_list': src_list,
        'score': '',
    }
    xb_list.append(item)


def get_content(href):
    data = requests.get(href, proxies={})
    data.encoding = 'utf-8'
    soup = BeautifulSoup(data.text, 'html.parser')
    xb_content = soup.find('div', id='xbcontent')
    if not xb_content:
        print("获取不到帖子内容")
        return ''
    first_p = xb_content.find('p')
    # print(first_p)
    if first_p:
        return first_p
    return xb_content


def get_top_summary():
    url = 'http://www.0818tuan.com/list-1-0.html'
    data = requests.get(url)
    data.encoding = 'utf-8'
    soup = BeautifulSoup(data.text, 'html.parser')
    tr_elements = soup.select('#redtag>.list-group-item')
    for tr in tr_elements:
        filter_list(tr)


def notify_markdown():
    if xb_list:
        if is_product_env():
            db.insert_many(xb_list)
        helper = AIHelper()
        prompt = f'''请分析以下内容的价值，并返回符合预期的内容。

输出要求：
1. 必须返回标准的 JSON 数组
2. 不要返回任何其他内容（如 ```json 标记）
3. 每个对象必须包含以下字段：title, href, src_list, text, score
4. score 字段格式为：「评分1-5分」一句话简要总结的理由

示例输出格式：
[
    {{
        "title": "示例标题",
        "href": "示例链接",
        "src_list": ["图片链接1", "图片链接2"],
        "text": "示例文本内容",
        "score": "4分」优惠力度大，活动简单"
    }}
]

筛选规则：
符合预期的内容包括：
1. 羊毛活动
2. 优惠活动
3. 红包或现金活动
4. 虚拟卡券
5. 便宜商品
6. 京东活动
7. 这些银行的无地区限制活动(
仅限借记卡["中国银行","中行","农业银行","交通银行","浦发","邮储","邮政","光大","兴业","平安","浙商","杭州银行","北京银行", "宁波银行"],
借记卡和信用卡[工商银行 工行 工银 e生活 建设银行 建融 招商银行 掌上生活 中信])
8. 带有二维码的图片
9. 浙江地区的活动

不符合预期的内容包括：
1. 闲聊,水贴
2. 吐槽
3. 美妆个护商品
4. 女装商品
5. 限定这些地区的活动（深圳、北京、天津、重庆）注意"上海交通卡"是全国通用的活动
6. 提问或求助帖(买什么 买那个)
7. 部分银行信用卡活动["中国银行","农业银行","交通银行","浦发", "邮储", "邮政", "光大", "兴业","平安", "浙商","杭州银行","北京银行","宁波银行"]
8. 这些银行的数字人民币活动("农业银行","交通银行","浦发","邮储","邮政","光大","兴业","平安","浙商","杭州银行","北京银行", "宁波银行" 工商银行 招商银行 中信)

处理要求：
1. 不符合预期的内容不要返回
2. 自动纠正title中的错别字或字母缩写（如 zfb->支付宝, vx->微信, dy->抖音）
3. 保持原有数据结构，仅在 score 字段中添加评分和理由

待分析内容：
{xb_list}'''

        json_response = asyncio.run(helper.analyze_content(xb_list, prompt))
        json_data = json.loads(json_response)

        markdown_text = ''
        for item in json_data:
            markdown_text += f'''
##### 📌[{item['title']}🌟{item['score']}]({item['href']})
{item['text']}
'''
            for img in item['src_list']:
                markdown_text += f'![]({img})'
        summary = json_data[0]['title']
        # 发送通知
        markdown_text += send_wx_push(summary, markdown_text, 37188)
        dingding_bot_with_key(summary, markdown_text, f"{key_name.upper()}_BOT_TOKEN")
        if is_product_env():
            dingding_bot_with_key(summary, markdown_text, "FLN_BOT_TOKEN")
        else:
            md_name = f"log_{key_name}_{get_day_string()}.md"
            with open(md_name, 'a', encoding='utf-8') as f:
                f.write("\n============================处理后数据===========================================\n")
                f.write(markdown_text)
    else:
        print("暂无线报！！")


def print_db():
    for row in db.fetch_all():
        print(row)


if __name__ == '__main__':
    try:
        # print_db()
        get_top_summary()
        notify_markdown()
    finally:
        db.close()
