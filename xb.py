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
    if title.endswith("？" or "?"):
        return False
    if tr['href'].startswith("http"):
        return False
    href = 'http://www.0818tuan.com' + tr['href']
    cxkWhiteList = ["中国银行", "中行", "农业银行", "农行", "交通银行", "交行", "浦发", "邮储", "光大", "兴业",
                    "平安", "浙商", "杭州银行", "北京银行", "宁波银行"]
    xykNameList = ["xing/用卡", "信用卡", "心用卡", "性用卡", "xyk"]
    if any(sub in title.lower() for sub in xykNameList) and any(sub in title.lower() for sub in cxkWhiteList):
        print("----无该行信用卡，已忽略" + '\t\t' + href)
        return False
    commonBlackList = [
        "定位", "部分", "东北", "徽", "限上海", "北京", "天津", "重庆", "深圳地区", "老家",
        "山东", "福建", "江苏", "云南", "江西", "河北", "广东", "吉林", "湖北", "河南", "陕西", "湖南", "四川", "宁夏",
        "广西", "辽宁", "甘肃", "内蒙古", "青海",
        "厦门", "南京", "东莞", "广州", "南海", "苏州", "中山", "常州", "青岛", "成都", "武汉", "合肥", "揭阳", "无锡",
        "济南", "大连", "石家庄", "泉州", "丹东",
        # ----卡----
        "万事达", "visa", "刷卡达标", "北分",
        "陆金所",
        "缤纷生活",
        "浦大喜奔",
        "邮储联名", "美团联名", "闪光卡", "联名卡",
        "农行刷卡金",
        "兴业生活",
        "交通银行数币", "交行数币",
        "光大麦当劳", "阳光惠生活", "光大石化",
        "广发", "恒丰", "汇丰", "农商", "苏银", "善融", "百信",
        "宝石山", "众邦", "兴农通",
        # ----无效----
        "特邀", "受邀", "瘦腰", "收腰", "临期", "值得买",
        # ----超链接----
        "vip.iqiyi.com",
        "music.163.com/prime/m/gift-receive",
        "ump.cmpay.com/info",
        # ----问题----
        "么", "问题", "问问", "问下", "谢谢", "请问", "问一下", "请教", "求", "咋", "怎样", "咨询", "赐教", "啥",
        "有问", "行不", "何解", "不行", "原因", "帮忙看", "哪来的", "都多少", "是多少", "是不是", "有谁", "大佬",
        "果熟", "有果", "油果", "彦祖", "多不", "谁有", "有没", "如何", "预算", "你们都", "几号", "到底",
        # ----数码----
        "华为", "huawei", "荣耀手机", "mipay", "果子", "苹果", "iphone", "airpods", "pm", "亚瑟", "大疆", "数据",
        # ----生活居家----
        "內衣", "拖鞋", "洞洞鞋", "购物袋", "布袋", "婴儿", "小孩", "孩子", "辣妈", "无线", "牙膏", "拉拉裤",
        "杯", "椅", "清风", "纸", "菌", "石头", "奥妙", "家政", "冈本", "南极人", "巾", "染", "一次性", "蚊香",
        # ----风险----
        "风险", "美元", "提额", "保险", "开通", "境外", "秒批", "下卡", "开户", "贷", "征信",
    ]
    highBlackList = [
        "【顶】",
        # ----玩法----
        "需要邀请", "助力", "人团", "拼团", "调研", "申请x", "互助", "攒能量",
        "首单", "盲盒", "月黑风高", "互换", "入会", "买1送1", "买一送一",
        # ----网购----
        "件", "/袋", "/盒", "/斤", "箱", "罐", "xl",
        "降", "9.9",
        "如有", "折合", "到手", "买家", "小法庭", "单号", "预售", "客服", "话术", "拆单",
        "查询", "高佣", "想买", "尾款", "小黄鱼",
        # ----形容词----
        "限量", "健康", "地道", "进口", "真诚", "厉害", "有点6", "骚", "不要脸", "蛋疼", "奇怪", "大事",
        # "瓶",
        # "返",
        # "凑",
        # ----语气符号----
        "呢", "呀!", "啦 ！", "了。。", "了啊", "啊~", "。。。",
        # ----情绪----
        "卧槽", "牛逼", "牛b", "还好", "根本", "有点东西", "感觉", "居然", "感谢", "心态", "无语", "毛线",
        "无耻", "便宜啊", "麻烦", "不如不", "狗了", "差了", "终于", "太次了", "不想搞", "只有", "不服", "见过",
        "太难", "看到", "发财", "咱", "口感", "妥妥", "死活", "就这", "狗屁", "感受", "没想到", "兄弟们",
        # ----负面----
        "不能", "删了", "续费", "限制使用", "被盗", "差评", "监控", "套牢", "猫饼", "怀疑", "不知道", "真的假的",
        "没有", "想法", "网友", "挤", "上科技", "不友好", "骗", "返买", "反买", "关闭", "闲谈", "投诉", "虚假", "进群",
        "被封", "禁", "修复", "盾", "砍", "赔", "秒退", "限额",
        # ----时效----
        "以后", "即将", "过期", "长期出", "逾期", "发货", "退货", "防身", "前10", "前年", "收到短信", "上个月",
        "改规则", "几秒", "忘记", "想起", "明天",
        # ----end----
        "黄了", "没了", "下线", "凉了", "领不了", "领完", "我才", "没抢到", "没到", "未到账", "不到账", "凉凉",
        "抢不到", "上限", "退款", "不给", "砍单", "抢光", "不可用", "审核",
        "翻车", "失败", "崩溃", "崩了", "黑号", "号黑", "拦截", "卸载", "火爆", "销户", "垃圾", "风控", "不玩了",
        # ----虚拟----
        "工行码", "吧码", "迅雷", "电子书",
        # ----不符合预期的词语----
        "的水", "漏水", "纯水", "碱水", "水果", "水雾", "酒水", "吸水", "精萃水", "精华水", "净水", "补水", "花露水",
        "热水", "玻璃水", "口水", "缩水", "水龙", "水润", "水牛", "水枪", "香水", "水壶", "水蜜",
        "沥水", "水乳", "卸妆水", "防水", "饮水", "水泡", "水感", "水饺", "水杨",
        "签到红包", "返红包", "返虹包", "游戏私服", "游戏账号",
        "朋友圈",
        "cm", "ml",
    ]
    lowBlackList = [
        "多拍", "券包", "免单", "预售", "试用", "点秒杀", "以旧换新", "小程序下单", "直播间下单",
        # ----食品----
        "三只松鼠", "海底捞", "火锅", "烧烤", "麻辣烫", "馋嘴", "卤", "炖", "火腿",
        "蛋白", "豆浆", "维生素", "麦片", "飞鹤", "粥", "面粉", "小麦", "米线",
        # ----生鲜----
        "巧乐兹", "梦龙", "可生食", "羊肉", "虾", "粽", "笋",
        "榴莲", "梨", "柠檬", "香菇", "鲜花", "莓", "玫瑰", "酸菜", "雪糕", "冰淇淋",
        # ----饮料----
        "饮料", "奶茶", "果汁", "奈雪", "蜜雪", "农夫山泉", "矿泉水", "茅台", "五粮液", "习酒", "窖", "特仑苏", "椰子",
        "观音",
        # ----美妆个护----
        "珀莱雅", "雅诗兰黛", "毛戈平", "屈臣氏", "大宝", "金纺", "立白", "科颜氏", "林清轩", "欧莱雅",
        "洁面", "洗", "眉", "唇", "泥", "日抛", "护理", "采销", "面膜", "卫生", "敏感肌", "美妆蛋", "保湿",
        # ----其他实物----
        "佛", "机油", "猫粮", "宠物", "翡翠",
        # ----品牌----
        "第三方", "京造", "京东买药", "东方甄选",
        # "喵满分",
        # ----虚拟卡券----
        "火车", "电影", "门票", "打车", "顺风车", "单车", "流量", "gb", "出行优惠券", "网盘", "地铁", "网易云", "机票",
        "顺丰", "快递", "充电", "民宿", "芒果", "年卡", "腾讯视频", "体检",
        # ----线下门店----
        "老乡鸡", "沪上阿姨", "永和大王", "沃尔玛", "永辉", "盒马", "联华",
        # ----无效----
        "plus", "yzf", "翼支付", "svip", "联通", "移动套餐", "美团圈圈", "王卡", "钻石会员", "铂金",
        "元梦之星", "腾讯vip", "胡姬花",
    ]
    if any(sub in title.lower() for sub in commonBlackList):
        return False
    if any(sub in title.lower() for sub in highBlackList):
        return False
    if any(sub in title.lower() for sub in lowBlackList):
        return False
    whiteList = [
        "云闪付", "ysf",
        "xyk", "性用卡", "还款",
        "工商银行", "工商", "工行", "工银", "e生活",
        "建设银行", "建行", "建融",
        "招商银行", "招行", "掌上生活", "体验金",
        "中信", "动卡空间",
        "淘宝", "tb", "手淘", "天猫", "猫超", "闲鱼", "高德",
        "支付宝", "zfb", "转账", "网商", "某付宝",
        "微信", "wx", "vx", "v.x", "小程序", "立减金", "ljj", "公众号", "原文", "推文",
        "京东", "狗东", "jd", "京豆", "e卡",
        "抖音", "dy",
        "美团", "elm",
        "红包", "虹包", "抽奖", "秒到", "保底", "游戏", "下载",
        "水", "必中",
        # "同程", "携程", "途牛",
        "话费", "移动", "和包", "电信", "q币", "扣币",
        "麦当劳", "肯德基", "必胜客", "星巴克", "瑞幸", "朴朴", "喜茶", "霸王茶姬", "百果园", "茶百道", "库迪",
        "礼品卡", "星礼卡",
        "深圳通", "网上国网",
    ]
    if not any(sub in title.lower() for sub in whiteList) and not any(sub in title.lower() for sub in cxkWhiteList):
        return False
    content = get_content(href)
    # todo 评论回复
    # print(content)
    for checkItem in commonBlackList:
        if content and checkItem in content.get_text():
            print(f"{checkItem}\t\t----关键字不合法，已忽略\t\t{href}")
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
        markdown_text = ''
        for item in xb_list:
            markdown_text += f'''
##### [{item['title']}]({item['href']})
{item['content']}
'''
        sendNotify.pushplus_bot_my(xb_list[0]["title"], markdown_text)
        with open("log_xb.md", 'w', encoding='utf-8') as f:
            f.write(markdown_text)
    else:
        print("暂无线报！！")


if __name__ == '__main__':
    get_top_summary()
    notify_markdown()
