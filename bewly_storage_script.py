#!/bin/env python3
# -*- coding: utf-8 -*
"""
用于管理BewlyBewly:https://github.com/mgmg22/BewlyBewly扩展插件storage的工具脚本
"""
import pyperclip

titleBlackList = [
    # 专区
    "豆瓣 电影 高分 评分 台词 合集",
    "车 宝马 法拉利 充电",
    "网文 修仙",
    "摄影 翻唱 PS",
    "舞 翻跳 健身 KPOP 身材",
    "旅行 乒乓 美食 护肤",
    # 游戏
    "黑神话 悟空 悟能 大圣 风灵月影 修改器 二郎神 杨戬 虎先锋 天命 文明 王者荣耀 氪 私服 魔兽世界 桌游 原神 尘白 dota 网易 米哈游 模拟器",
    # 学生
    "幼儿园 小学 初中 高中 大学 硕士 毕业 应届 读博 博士 实习 面试 入职 学姐 班主任 就业 学妹 女大 二本 985",
    # 男女
    "相亲 结婚 未婚 男 舔狗 离婚 出轨 七夕 约会 小孩 表白 分手 女友 婚纱 搭讪 撩妹 猥亵 彩礼 老公 老婆 恋爱 同居 弟弟 好人",
    # 外国
    "奥运 巴黎 夺冠 韩国 德国 英国 朝鲜 首尔 非洲 马尔代夫 希腊 纽约 马来西亚",
    # 二次元
    "乙女 后宫 硬控 虎视眈眈 火影 痴女 鸣人",
    # 网红
    "陈泽 张雪峰 理塘 丁真 童锦程 何同学 董宇辉 老番茄 奶茶 药水",
    # 歌手
    "华语乐坛 张杰 法老 GAI 邓紫棋 林俊杰 陈奕迅 陶喆 方大同 张艺兴 吴彦祖 成龙 许嵩 韩红 孙燕姿 薛之谦",
    # 名人
    "蒋介石 科比 余承东 马云 刘强东 马斯克 雷军",
    # 影视
    "李云龙 武林外传 军队 爱情公寓",
    # 历史
    "清朝 宋 秦始皇 关羽 张角 武松 年前",
    # 省市
    "郑州 云南 福建 江西 重庆 台湾 河北",
    # 广告
    "莆田 鞋 接单 黄牛 口碑 笔记本 信用卡 程序员 拼多多",
    # 标题党
    "到底是 一口气 名场面 盘点 难以置信 快乐源泉 史上 前方高能 分钟 的神 天才 元买 建议 不只是 有这样的 如何判断 全网最",
    # 水
    "关于我是 VLOG 万粉 w粉 奖牌 虎扑 彩票 刮刮乐 米其林 外卖 探店 小丑 麻辣 警察 duang 流氓 网吧 今日 反诈 亖 小时候 僵尸",
]
userBlackList = [
    "豆瓣 电影 剧 梗 唱 歌",
    # 注释
    "车 房 官方",
    "同学 老师 日常 VLOG 评测 外卖"
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
