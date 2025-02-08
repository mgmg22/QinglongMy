from pytrends.request import TrendReq
import time

# 初始化 TrendReq 对象
pytrends = TrendReq(hl='en-US', tz=360)

# 获取多重搜索词的兴趣度比较
multi_trend_payload = ['GPTs', 'ChatGPT', 'AI']
pytrends.build_payload(multi_trend_payload, cat=0, timeframe='today 3-m', geo='', gprop='')
multi_trend_df = pytrends.interest_over_time()
print("\n多重搜索词的兴趣度比较:")
print(multi_trend_df)
