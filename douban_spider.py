# !/bin/env python3
# -*- coding: utf-8 -*
# """
# cron: 5 9 * * * weibo_summary.py
# new Env('豆瓣租房');
# """
from douban_scraper import DoubanScraper
import time

summary_list = []

# # 排除项
user_black_list = [
    "杨浦租房", "PiNa@上海直租", "沪上蜗居小豆豆",
    "🍃 🇨🇳", "豆友280014083", "瓜瓜一号的墨迹",
    "黄浦区租房",
    "娜娜小夭", "自由奔放", "江湖不良人",
    "华夏东路", "清风秀雅", "灵感之刃", "给你俩窝窝", "简单点", "忧伤的旋律", "C",
    "九头奈子", "豆友dda93.0249",
    "兔九九", "忘记了不该忘的",
    "李好闲。", "小张要增肌", "虚伪的世界",
    "森女与鹿林", "提子", "悲伤的诗篇", "相思成殇",
    "安静的等待", "-Joker",
    "豆友279607317", "豆友273774333", "旧梦乱心", "失宠的猫", "氧气柠檬红茶",
    "豆友279607320", "豆友270169870",
    "豆友279607122", "祈鹤", "可怜式.暧情", "如花美眷", "豆友279434723", "豆友279434727", "从悲伤中抽离",
    "豆友1HLEH7JXr4", "一切都挺好", "Choo", "sweet", "乐儿",
    "Foo", "克克", "稚气", "妮妮", "我装作鱼", "想当英雄小波比",
    "欣欣", "Sandra", "明明就", "荒野蛮神",
    "筑堰公寓zzlp", "一吃就胖小湛蓝", "月亮是我踹弯的",
    "上海链家小孙", "豆友UF1HJgKfBU", "野的像风", "不将就i",
    "我恨我痴心", "豆友1dyNCH3jx0",
    "北有孤酒", "不羁",
]

processed_links = set()


def filter_content(item: dict) -> bool:
    """
    过滤内容

    Args:
        item: 帖子信息字典
    Returns:
        bool: True 表示通过过滤，False 表示被过滤掉
    """
    # 检查链接是否已经处理过
    if item['link'] in processed_links:
        return False

    # 检查用户是否在黑名单中
    if item['author'] in user_black_list:
        return False

    # 排除项关键词检查
    blackList = [
        "女生", "房源", "公积金", "居住证", "钥匙", "别墅",
        "求租", "预算", "有没有",
        "4000",
        "青浦", "嘉定", "虹桥商务区",
        "浦东",
        # "静安",
        "普陀", "松江",
        "奉贤", "海湾",
    ]
    for keyword in blackList:
        if keyword in item['title']:
            # print(f"过滤：标题包含关键词 '{keyword}' - {item['link']}")
            return False
    myStations = [
        # 1号线
        "富锦路", "友谊西路", "宝安公路", "共富新村", "呼兰路", "通河新村", "共康路", "彭浦新村", "汶水路",
        "上海马戏城", "延长路", "中山北路", "上海火车站",
        # "汉中路", "新闸路", "人民广场", "黄陂南路", "陕西南路", "常熟路", "衡山路", "徐家汇", "宜山路", "漕溪路", "上海南站", "锦江乐园",
        "莲花路", "外环路", "莘庄",
        # 2号线
        "徐泾东", "虹桥火车站", "虹桥2号航站楼", "淞虹路", "北新泾", "威宁路",
        # "娄山关路", "中山公园","江苏路", "静安寺", "南京西路", "人民广场", "南京东路", "陆家嘴", "东昌路", "世纪大道","上海科技馆",
        "世纪公园", "龙阳路", "张江高科", "金科路", "广兰路", "唐镇", "创新中路",
        "华夏东路", "川沙", "凌空路", "远东大道", "海天三路", "浦东国际机场",
        # 3号线
        # "上海南站", "石龙路", "龙漕路","漕溪路", "宜山路", "虹桥路",
        "延安西路", "中山公园", "金沙江路", "曹杨路", "镇坪路", "中潭路", "上海火车站",
        # "宝山路",
        "东宝兴路", "虹口足球场", "赤峰路", "大柏树", "江湾镇", "殷高西路", "长江南路", "淞发路", "张华浜", "淞滨路",
        "水产路", "宝杨路", "友谊路", "铁力路", "江杨北路",
        # 4号线（环线）
        # "宜山路", "虹桥路",
        "延安西路", "中山公园", "金沙江路", "曹杨路", "镇坪路", "中潭路", "上海火车站",
        # "宝山路", "海伦路", "临平路", "大连路", "杨树浦路", "浦东大道", "世纪大道",
        "浦电路", "蓝村路", "塘桥", "南浦大桥",
        # "西藏南路", "鲁班路", "大木桥路", "东安路","上海体育场", "上海体育馆","宜山路",
        # 5号线
        "莘庄", "春申路", "银都路", "颛桥", "北桥", "剑川路", "东川路", "金平路", "华宁路", "文井路", "闵行开发区",
        # 6号线
        "6号线", "港城路", "外高桥保税区北", "航津路", "外高桥保税区南", "洲海路", "五洲大道", "东靖路", "巨峰路",
        "五莲路", "博兴路", "金桥路", "云山路", "德平路", "北洋泾路", "民生路", "源深体育中心", "世纪大道", "浦电路",
        "蓝村路", "儿童医学中心", "临沂新村", "高科西路", "东明路", "华夏西路", "上南路", "灵岩南路", "东方体育中心",
        # 7号线
        "7号线", "美兰湖", "罗南新村", "潘广路", "刘行", "顾村公园", "祁华路", "上海大学", "南陈路",
        "上大路", "场中路", "大场镇", "行知路", "大华三路", "新村路", "岚皋路", "镇坪路", "长寿路", "昌平路",
        # "静安寺", "常熟路","肇嘉浜路", "东安路", "龙华中路",
        "后滩", "长清路", "耀华路", "云台路", "高科西路", "杨高南路", "锦绣路", "芳华路", "龙阳路", "花木路",
        # 8号线
        "八号线", "8号线", "市光路", "嫩江路", "翔殷路", "黄兴公园", "延吉中路", "黄兴路", "江浦路", "鞍山新村",
        "四平路", "曲阳路", "虹口足球场",
        # "西藏北路", "中兴路", "曲阜路", "人民广场","大世界","老西门", "陆家浜路", "西藏南路",
        "中华艺术宫", "耀华路", "成山路", "杨思", "东方体育中心", "凌兆新村", "芦恒路", "浦江镇", "沈杜公路",
        # 9号线
        "9号线", "曹路", "民雷路", "顾唐路", "金海路", "申江路", "金桥", "台儿庄路", "蓝天路", "芳甸路",
        "杨高中路", "世纪大道", "商城路", "小南门", "陆家浜路",
        # "马当路", "打浦桥", "嘉善路","肇嘉浜路", "徐家汇", "宜山路", "桂林路",
        "漕河泾开发区", "合川路", "星中路", "七宝",
        "中春路", "九亭", "泗泾", "佘山", "洞泾", "松江大学城", "松江新城", "松江体育中心", "醉白池", "松江南站",
        # 10号线
        "基隆路", "港城路", "高桥", "高桥西", "双江路", "国帆路", "新江湾城", "殷高东路",
        "三门路", "江湾体育场", "五角场", "国权路", "同济大学", "四平路", "邮电新村",
        # "海伦路",
        # "四川北路", "天潼路", "南京东路", "豫园", "老西门", "新天地", "陕西南路", "上海图书馆",
        # "交通大学",
        "虹桥路", "宋园路", "伊犁路", "水城路", "龙溪路", "上海动物园", "虹桥1号航站楼",
        "虹桥2号航站楼", "虹桥火车站", "航中路", "龙柏新村", "紫藤路", "七莘路",
        # 11号线
        "11号线", "迪士尼", "康新公路", "秀沿路", "罗山路", "御桥", "严御路", "浦三路", "三林东", "三林",
        "东方体育中心", "龙耀路", "云锦路",
        # "龙华", "上海游泳馆", "徐家汇", "交通大学", "江苏路",
        "隆德路", "曹杨路", "枫桥路", "真如", "上海西站", "李子园", "祁连山路", "武威路", "桃浦新村", "南翔", "马陆",
        "嘉定新城", "白银路", "嘉定西", "嘉定北", "上海赛车场", "昌吉东路", "上海汽车城", "安亭", "兆丰路", "光明路",
        "花桥",
        # 12号线
        "七莘路", "虹莘路", "顾戴路", "东兰路", "虹梅路",
        # "虹漕路", "桂林公园", "漕宝路",
        # "龙漕路", "龙华", "龙华中路", "大木桥路", "嘉善路", "陕西南路", "南京西路", "汉中路",
        # "曲阜路", "天潼路", "国际客运中心", "提篮桥", "大连路", "江浦公园", "宁国路",
        "隆昌路", "爱国路", "复兴岛", "东陆路", "巨峰路", "杨高北路", "金京路", "申江路", "金海路",
        # 13号线
        "13号线", "金运路", "金沙江西路", "丰庄", "祁连山南路", "真北路", "大渡河路", "金沙江路", "隆德路", "武宁路",
        "长寿路",
        # "江宁路", "汉中路", "自然博物馆", "南京西路", "淮海中路", "新天地", "马当路",
        "世博会博物馆", "世博大道", "长清路", "成山路", "东明路", "华鹏路", "下南路", "北蔡", "陈春路", "莲溪路",
        "华夏中路", "中科路", "学林路", "张江路",
        # 14号线
        "14号线", "封浜", "乐秀路", "临洮路", "嘉怡路", "定边路", "真新新村", "真光路", "铜川路",
        "真如", "中宁路", "曹杨路", "武宁路", "武定路",
        # "静安寺", "一大会址·黄陂南路", "大世界",
        "豫园", "陆家嘴", "浦东南路", "浦东大道", "源深路", "昌邑路", "歇浦路", "龙居路", "云山路", "蓝天路", "黄杨路",
        "红枫路", "金港路", "桂桥路",
        # 15号线
        "15号线", "顾村公园", "锦秋路", "丰翔路", "南大路", "祁安路", "古浪路", "武威东路", "上海西站",
        "铜川路", "梅岭北路", "大渡河路", "长风公园",
        # "娄山关路", "红宝石路", "姚虹路","吴中路", "桂林路", "桂林公园", "上海南站",
        "华东理工大学", "罗秀路", "朱梅路", "华泾西", "虹梅南路", "景西路", "曙建路", "双柏路", "元江路", "永德路",
        "紫竹高新区",
        # 16号线
        "龙阳路", "华夏中路", "罗山路", "周浦东", "鹤沙航城", "航头东", "新场", "野生动物园", "惠南", "惠南东", "书院",
        "临港大道", "滴水湖",
        # 17号线
        "17号线", "虹桥火车站", "诸光路", "蟠龙路", "徐盈路", "徐泾北城", "嘉松中路", "赵巷", "汇金路", "青浦新城",
        "漕盈路", "淀山湖大道", "朱家角", "东方绿舟",
        # 18号线
        "18号线", "长江南路", "殷高路", "上海财经大学", "复旦大学", "国权路", "抚顺路", "江浦路",
        "江浦公园", "平凉路", "丹阳路", "昌邑路", "民生路", "杨高中路", "迎春路", "龙阳路",
        "芳芯路", "北中路", "莲溪路", "御桥", "康桥", "周浦", "繁荣路", "沈梅路", "鹤涛路", "下沙", "航头",
        # 浦江线
        "沈杜公路", "三鲁公路", "闵瑞路", "浦航路", "东城一路", "汇臻路"
    ]
    for keyword in myStations:
        if keyword in item['title']:
            # print(f"过滤：标题包含地铁 '{keyword}' - {item['link']}")
            return False
    return True


def print_discussions(discussions: list):
    """打印讨论列表"""

    for item in discussions:
        if filter_content(item):
            print(item['title'] + '\t\t' + item['time'] + '\t\t' + item['author'] + '\t\t' + item['link'])
            processed_links.add(item['link'])
            summary_list.append(item)


def get_top_summary(start: int = 0, max_items: int = 20, max_pages: int = 6):
    """
    获取租房信息摘要

    Args:
        start: 起始位置
        max_items: 最大获取条目数
        max_pages: 最大页数限制
    """
    scraper = DoubanScraper()
    try:
        current_page = start
        while len(summary_list) < max_items and current_page < max_pages * 25:
            page_num = current_page // 25
            # 获取当前页数据
            discussions = scraper.get_group_discussions('shanghaizufang', page_num)
            if not discussions:
                print("未获取到数据，可能是页面结构变化或反爬限制")
                break
            print_discussions(discussions)
            # 更新页码
            current_page += 25
            # 添加延时，避免请求过快
            time.sleep(5)

    except Exception as e:
        print(f"获取数据失败: {str(e)}")
        import traceback
        print(f"详细错误信息: {traceback.format_exc()}")
    finally:
        scraper.close()


if __name__ == '__main__':
    processed_links = set()
    summary_list = []
    get_top_summary()
