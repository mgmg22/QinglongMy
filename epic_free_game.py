#!/bin/env python3
# -*- coding: utf-8 -*
"""
cron: 2 0 0 * * 6 epic_free_game.py
new Env('Epic每周限免');
"""
import json
import requests
import sendNotify
from datetime import datetime


def get_free_games() -> dict:
    timestamp = datetime.timestamp(datetime.now())
    games = {'timestamp': timestamp, 'free_now': [], 'free_next': []}
    base_store_url = 'https://store.epicgames.com'
    api_url = 'https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?country=CN'
    resp = requests.get(api_url)
    for element in resp.json()['data']['Catalog']['searchStore']['elements']:
        if promotions := element['promotions']:
            game = {}
            game['title'] = element['title']
            game['images'] = element['keyImages']
            game['origin_price'] = element['price']['totalPrice']['fmtPrice']['originalPrice']
            game['discount_price'] = element['price']['totalPrice']['fmtPrice']['discountPrice']
            game['store_url'] = f"{base_store_url}/p/{element['catalogNs']['mappings'][0]['pageSlug']}" if \
                element['catalogNs']['mappings'] else base_store_url
            if offers := promotions['promotionalOffers']:
                game['start_date'] = offers[0]['promotionalOffers'][0]['startDate']
                game['end_date'] = offers[0]['promotionalOffers'][0]['endDate']
                games['free_now'].append(game)
            if offers := promotions['upcomingPromotionalOffers']:
                game['start_date'] = offers[0]['promotionalOffers'][0]['startDate']
                game['end_date'] = offers[0]['promotionalOffers'][0]['endDate']
                games['free_next'].append(game)
    return games


def generate_json(games: dict, filename: str):
    with open(filename, 'w') as f:
        json.dump(games, f)
        # json.dump(obj=games, fp=f, ensure_ascii=False, indent=4)


def notify_markdown(games: dict):
    images = {}
    data = games['free_now'] + games['free_next']
    for game in data:
        for image in game['images']:
            if image['type'] in ['OfferImageWide', 'VaultClosed']:
                images[game['title']] = image['url']
                break

    content = '''# Epic 每周限免

- ## 本周限免

'''

    for game in games['free_now']:
        content += f'''
  - ### [{game['title']}]({game['store_url']} "{game['title']}")

    原价: {game['origin_price']}

    购买链接: [{game['store_url']}]({game['store_url']} "{game['title']}")

    ![{game['title']}]({images[game['title']]})

'''

    content += f'''
- ## 下周限免

'''

    for game in games['free_next']:
        content += f'''
  - ### [{game['title']}]({game['store_url']} "{game['title']}")

    原价: {game['origin_price']}

    购买链接: [{game['store_url']}]({game['store_url']} "{game['title']}")

    ![{game['title']}]({images[game['title']]})

'''
    sendNotify.serverJMy("Epic 每周限免", content)
    # with open(filename, 'w', encoding='utf-8') as f:
    #     f.write(content)


if __name__ == '__main__':
    games = get_free_games()
    # generate_json(games, './epic_free_games.json')
    notify_markdown(games)
