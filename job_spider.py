#!/bin/env python3
# -*- coding: utf-8 -*
"""
cron: 1 * * * * job_spider.py
new Env('远程工作');
"""
import requests
from sendNotify import is_product_env, dingding_bot_with_key
import sqlite3
from dotenv import load_dotenv

key_name = "job"
summary_list = []
conn = sqlite3.connect(f'{key_name}.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS titles (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        state TEXT NOT NULL
    )
    ''')
load_dotenv()


def filter_item(job_item):
    # print(job_item)
    title = f'''[{job_item['postTitle'].lower().strip()}]({job_item['url']})'''
    state = f'''{job_item['descContent']}
{job_item['source']} {job_item['salary']} {job_item['jobType']}
'''
    for row in get_db_data():
        if title == row[1]:
            print('重复已忽略')
            return False
    keywordList = [
        "android 安卓 客户端 app",
    ]
    if any(word in title for item in keywordList for word in item.split()):
        print(job_item)
        print(title)
        print(state)
        item = {
            'title': title,
            'state': state,
        }
        summary_list.append(item)
    else:
        return False


def get_hot_search():
    url = 'https://easynomad.cn/api/posts/list?limit=15&page=1&jobCategory=%E5%BC%80%E5%8F%91&contractType='
    resp = requests.get(url)
    resp.encoding = 'utf-8'
    elements = resp.json()['data']
    for job_item in elements:
        filter_item(job_item)


def notify_markdown():
    if summary_list:
        markdown_text = ''
        for item in summary_list:
            markdown_text += f'''{item['title']}
            
{item["state"]}
'''
        if is_product_env():
            insert_db(summary_list)
        dingding_bot_with_key("job", markdown_text, f"{key_name.upper()}_BOT_TOKEN")
        with open(f"log_{key_name}.md", 'w', encoding='utf-8') as f:
            f.write(markdown_text)
    else:
        print("暂无job！！")


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
