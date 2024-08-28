#!/bin/env python3
# -*- coding: utf-8 -*
"""
用于管理BewlyBewly:https://github.com/mgmg22/BewlyBewly扩展插件storage的工具脚本
"""
import pyperclip

titleBlackList = [
    # 专区
    "豆瓣 电影 高分 评分",
    "新车 宝马 法拉利",
    "网文 修仙",
    "摄影 翻唱",
    "舞 翻跳 健身",
    "旅行 乒乓",
    # 游戏
    "黑神话 悟空 悟能 大圣 风灵月影 二郎神 杨戬 文明 王者荣耀 氪金 私服 魔兽世界 桌游 原神",
    # 学生
    "幼儿园 小学 初中 高中 大学 硕士 毕业 应届 读博 博士 实习 面试 入职 学姐 班主任",
    # 男女
    "相亲 结婚 未婚 男朋友 舔狗 离婚 出轨 七夕 约会 小孩 表白 分手 女友 婚纱 搭讪 撩妹 猥亵",
    # 外国
    "奥运 巴黎 夺冠 韩国 德国 英国 朝鲜 首尔 非洲",
    # 二次元
    "乙女 后宫",
    # 网红
    "陈泽 张雪峰 理塘 丁真 童锦程 何同学 董宇辉 老番茄 奶茶 药水",
    # 歌手
    "雷军 张杰 法老 GAI 邓紫棋 林俊杰 陈奕迅 陶喆 方大同 张艺兴 吴彦祖 成龙 许嵩 韩红",
    # 名人
    "李云龙 蒋介石 科比 余承东",
    # 历史
    "清朝 宋 秦始皇 关羽 张角",
    # 省市
    "郑州 云南 福建",
    # 广告
    "莆田 鞋 接单 黄牛 口碑 笔记本",
    # 标题党
    "到底是 一口气 名场面 盘点 难以置信 ",
    # 水
    "关于我是 VLOG 万粉 w粉 奖牌 虎扑 彩票 刮刮乐 米其林",
]
userBlackList = [
    "豆瓣 电影 剧 梗 唱 歌",
    # 注释
    "车 房 官方",
    "同学 老师 日常 VLOG 评测"
]


def generate_pattern(item_list):
    escaped_words = [word for item in item_list for word in item.split()]
    pattern = '|'.join(escaped_words)
    return f"/{pattern}/i"


if __name__ == '__main__':
    js_code = f"""
chrome.storage.local.get(null, function(result) {{
  let storageData = result
  let settings = JSON.parse(storageData.settings)
  settings.filterByTitle = [
    {{
        "keyword": "{generate_pattern(titleBlackList)}",
        "remark": ""
    }}
  ]
  settings.filterByUser = [
    {{
        "keyword": "{generate_pattern(userBlackList)}",
        "remark": ""
    }}
  ]
  storageData.settings = JSON.stringify(settings)
  chrome.storage.local.set(storageData, function() {{
    location.reload();
  }})
}})
"""
    print(js_code)
    # 需要在chrome控制台切换到BewlyBewly扩展的上下文再运行
    pyperclip.copy(js_code)
