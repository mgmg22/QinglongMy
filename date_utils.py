import datetime
from datetime import date

today = date.today()


def get_day_string(date=None):
    """
    返回给定日期或当前日期的 "日" 字符串 (DD)。

    Args:
        date (datetime.date, optional): 要格式化的日期对象。默认为 None，表示使用当前日期。

    Returns:
        str: 格式为 "DD" 的日期字符串。
    """
    if date is None:
        date = datetime.date.today()

    return date.strftime("%d")


def get_today() -> str:
    weekday = today.weekday()
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    day_name = days[weekday]
    return str(today) + " " + day_name


# 判断报价日期是否是今天
def is_today(timestamp):
    return today == datetime.datetime.fromtimestamp(timestamp).date()
