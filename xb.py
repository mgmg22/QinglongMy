#!/bin/env python3
# -*- coding: utf-8 -*
"""
cron: 3 8/1 * * * xb.py
new Env('线报0818');
"""
from bs4 import BeautifulSoup
import requests
import sendNotify

xb_list = []


def filter_list(tr):
    title = tr.get_text()
    href = 'http://www.0818tuan.com' + tr['href']
    commonBlackList = [
        "定位", "部分", "东北", "徽", "限上海", "北京", "天津", "重庆", "深圳地区",
        "山东", "福建", "江苏", "云南", "江西", "河北", "广东", "吉林", "湖北", "河南", "陕西", "湖南", "四川", "宁夏",
        "广西", "辽宁", "甘肃", "内蒙古",
        "厦门", "南京", "东莞", "广州", "南海", "苏州", "中山", "常州", "青岛", "成都", "武汉", "合肥", "揭阳", "无锡",
        "济南", "大连", "石家庄", "泉州",
        # ----卡----
        "万事达", "visa", "刷卡达标", "北分",
        "平安X", "平安x", "平安银行X", "平安信", "平安心", "平安银行信", "平安银行x", "陆金所",
        "中行x", "中行信", "中行心", "中国银行信", "中国银行x", "缤纷生活",
        "浦发x", "浦发信", "浦发银行x", "浦大喜奔",
        "浙商x", "浙商信", "浙商银行x",
        "邮储x", "邮储X", "邮储信", "邮储联名", "美团联名", "闪光卡", "联名卡",
        "农行x", "农行信", "农业银行信", "农业银行x", "农行刷卡金",
        "兴业银行x", "兴业x", "兴业生活",
        "交行x", "交行信", "交通银行x", "交通银行数币", "交行数币",
        "光大x", "光大信", "光大银行x", "光大心用卡", "光大麦当劳", "阳光惠生活",
        "广发", "恒丰", "汇丰", "农商", "苏银",
        "宝石山", "众邦",
        # ----无效----
        "特邀", "受邀", "瘦腰", "收腰",
        # ----超链接----
        "vip.iqiyi.com",
        "music.163.com/prime/m/gift-receive",
        "marketing/2023/bir",
    ]
    highBlackList = [
        "【顶】",
        # ----玩法----
        "需要邀请", "助力", "人团", "拼团", "调研", "申请x",
        "首单", "盲盒", "月黑风高", "互换", "入会", "买1送1", "买一送一",
        # ----网购----
        "件", "/袋", "/盒", "/斤", "箱", "罐", "XXL", "XL",
        "降", "9.9",
        "限量", "如有", "折合", "到手", "进口", "买家", "小法庭", "单号", "预售", "客服", "拆单",
        "健康", "查询", "高佣", "想买", "尾款", "临期",
        # "瓶",
        # "返",
        # "凑",
        # ----问题----
        "么",  # "么？","什么","怎么","饿了么",
        "问题", "问问", "问下", "谢谢", "请问", "问一下", "请教", "求", "咋", "怎样", "咨询", "赐教",
        "有问", "行不", "何解", "不行", "原因", "帮忙看", "哪来的", "都多少", "是多少", "是不是",
        "果熟", "有果", "油果", "彦祖", "多不", "谁有", "有没", "如何", "预算",
        # ----符号----
        "吗？", "吧？", "啥", "呢", "链接？", "呀!", "啊？", "啦 ！", "用？", "？？", "不？", "次？", "准？",
        "了？", "了?", "了。。", "了啊", "啊~", "。。。", "是？",
        # ----情绪----
        "卧槽", "牛逼", "牛B", "还好", "根本", "有点东西", "感觉", "居然", "感谢", "心态", "无语", "奇怪", "毛线",
        "无耻", "便宜啊", "麻烦", "不如不", "狗了", "差了", "终于", "太次了", "不想搞", "只有", "不服", "见过", "蛋疼",
        "太难",
        # ----负面----
        "不能", "删了", "续费", "限制使用", "被盗", "差评", "监控", "套牢", "猫饼", "怀疑", "不知道", "真的假的",
        "没有", "想法", "网友", "挤", "上科技", "不友好", "骗", "返买", "反买", "关闭", "闲谈", "投诉", "虚假", "进群",
        # ----时效----
        "以后", "即将", "过期", "长期出", "逾期", "发货", "退货", "防身", "前10", "前年", "收到短信", "上个月",
        "改规则",
        # ----end----
        "黄了", "没了", "下线", "凉了", "领不了", "领完了", "我才", "没抢到", "没到", "未到账", "不到账", "凉凉",
        "抢不到", "上限", "退款", "不给", "砍单",
        "翻车", "失败", "崩溃", "崩了", "黑号", "号黑", "拦截", "卸载", "火爆", "销户", "垃圾", "风控", "不玩了",
        # ----虚拟----
        "风险", "美元", "提额", "保险", "开通", "境外", "秒批", "下卡", "工行码", "吧码",
        "迅雷", "唯品会小程序", "电子书", "贷", "征信", "限额",
        # ----不符合预期的词语----
        "漏水", "纯水", "碱水", "水果", "水雾", "酒水", "吸水", "精萃水", "净水", "补水", "花露水", "热水",
        "玻璃水", "口水", "缩水", "水龙", "水润", "水牛", "水枪", "香水", "水壶",
        "沥水", "水乳", "卸妆水", "防水", "饮水", "水泡", "水感", "水饺",
        "签到红包", "游戏私服", "游戏账号",
        "朋友圈",
        "cm", "ml", "ML",
    ]
    lowBlackList = [
        "多拍", "返红包", "券包", "免单", "预售", "试用", "点秒杀", "以旧换新", "小程序下单", "直播间下单",
        # ----生活居家----
        "內衣", "拖鞋", "洞洞鞋", "购物袋", "婴儿", "小孩", "孩子", "辣妈", "无线", "牙膏", "拉拉裤",
        "杯", "椅", "清风", "纸", "菌", "石头", "湿巾", "奥妙", "家政", "冈本",
        # ----食品生鲜----
        "巧乐兹", "三只松鼠",
        "奶茶", "果汁", "奈雪", "蜜雪", "农夫山泉", "矿泉水", "茅台", "五粮液", "习酒", "窖", "特仑苏", "可生食",
        "海底捞", "火锅", "羊肉", "虾", "烧烤", "麻辣烫", "馋嘴", "卤", "炖", "粽", "火腿",
        "榴莲", "梨", "柠檬", "香菇", "鲜花", "椰子", "莓", "玫瑰", "酸菜", "梦龙", "雪糕",
        "蛋白", "豆浆", "维生素", "麦片", "飞鹤", "粥", "笋",
        # ----美妆个护----
        "珀莱雅", "雅诗兰黛", "毛戈平", "屈臣氏", "大宝", "金纺", "立白",
        "洁面", "洗", "眉", "日抛", "护理", "采销", "面膜", "卫生", "敏感肌", "美妆蛋",
        # ----其他实物----
        "佛", "机油", "猫粮", "宠物", "翡翠",
        # ----品牌----
        "第三方", "京造", "京东买药", "东方甄选", "亚瑟",
        # "喵满分",
        # ----虚拟----
        "华为", "HUAWEI", "荣耀手机", "MiPay", "yzf", "翼支付", "SVIP",
        "火车", "电影", "门票", "打车", "顺风车", "单车", "流量", "GB", "出行优惠券", "网盘", "地铁", "网易云", "机票",
        "顺丰", "快递", "充电", "民宿", "芒果", "年卡",
        # ----无效----
        "京东plus", "PLUS会员", "Plus拍下", "PLUS 拍下", "plus领", "联通", "移动套餐", "美团圈圈", "王卡", "钻石会员",
        "元梦之星", "老乡鸡", "沪上阿姨", "永和大王", "沃尔玛", "永辉", "盒马",
    ]
    if any(sub in title for sub in commonBlackList):
        return False
    if any(sub in title for sub in highBlackList):
        return False
    if any(sub in title for sub in lowBlackList):
        return False
    whiteList = [
        "云闪付", "ysf",
        "xyk", "性用卡", "还款",
        "中国银行", "中行", "农业银行", "农行", "交通银行", "交行", "浦发", "邮储", "光大", "兴业",
        "平安", "浙商", "杭州银行", "北京银行", "宁波银行",
        "工商银行", "工商", "工行", "工银", "e生活",
        "建设银行", "建行", "建融", "善融",
        "招商银行", "招行", "掌上生活", "体验金",
        "中信", "动卡空间",
        "淘宝", "tb", "手淘", "天猫", "猫超", "闲鱼", "高德",
        "支付宝", "zfb", "转账", "网商", "某付宝",
        "微信", "wx", "vx", "v.x", "V.x", "小程序", "立减金", "ljj", "公众号", "原文", "推文",
        "京东", "狗东", "JD", "京豆", "e卡",
        "抖音", "dy",
        "美团", "elm",
        "红包", "抽奖", "秒到", "保底", "游戏", "下载",
        "水", "必中",
        # "同程", "携程", "途牛",
        "话费", "移动", "和包", "电信", "Q币", "扣币",
        "麦当劳", "肯德基", "必胜客", "星巴克", "瑞幸", "朴朴", "喜茶", "霸王茶姬", "百果园", "茶百道",
        "礼品卡", "星礼卡", "苹果卡",
        "深圳通", "网上国网",
    ]
    if not any(sub in title for sub in whiteList):
        return False
    content = get_content(href)
    # todo 评论回复
    # print(content)
    for checkItem in commonBlackList:
        if content and checkItem in content.get_text():
            print(checkItem + "----关键字不合法，已忽略" + '\t\t' + href)
            return False
    print(title + '\t\t' + href)
    item = {
        'title': title,
        'href': href,
        'content': content
    }
    xb_list.append(item)


def get_content(href):
    data = requests.get(href)
    data.encoding = 'utf-8'
    soup = BeautifulSoup(data.text, 'html.parser')
    xb_content = soup.select('div.genxin')
    if not xb_content:
        xb_content = soup.select('#xbcontent > p')
    if not xb_content:
        print("获取不到帖子内容")
        return ''
    return xb_content[0]


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
        content = ''
        for item in xb_list:
            content += f'''
##### [{item['title']}]({item['href']})
{item['content']}
'''
        sendNotify.pushplus_bot_my(xb_list[0]["title"], content)
        with open("log_xb.md", 'w', encoding='utf-8') as f:
            f.write(content)
    else:
        print("暂无线报！！")


if __name__ == '__main__':
    get_top_summary()
    notify_markdown()
