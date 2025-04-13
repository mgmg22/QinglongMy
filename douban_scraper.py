from playwright.sync_api import sync_playwright
import time
import json
from typing import Dict, List


class DoubanScraper:
    def __init__(self):
        """初始化爬虫"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)

    def get_group_discussions(self, group_id: str, page: int = 0) -> List[Dict]:
        """获取豆瓣小组讨论列表"""
        try:
            context = self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            )

            browser_page = context.new_page()
            url = f'https://www.douban.com/group/{group_id}/discussion?start={page * 25}'

            # 设置超时和请求头
            browser_page.set_default_timeout(30000)
            browser_page.set_default_navigation_timeout(30000)
            browser_page.set_extra_http_headers({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
                'Cache-Control': 'max-age=0',
            })

            # 加载页面
            response = browser_page.goto(url, wait_until='domcontentloaded')
            if not response or response.status != 200:
                print(f"页面响应异常: status={response.status if response else 'None'}")
                print(f"响应头: {response.headers if response else 'None'}")
                return []

            # 等待页面加载并处理验证
            try:
                browser_page.wait_for_selector('body', timeout=11000)
            except Exception as e:
                print(f"等待body元素超时: {e}")
                print("当前页面内容:")
                print(browser_page.content())
                return []

            self._handle_verification(browser_page)

            # 尝试不同的选择器
            selectors = [
                '.article .topic-item',  # 新版布局
                'table.olt tr',  # 旧版布局
                '#content table tr'  # 备用选择器
            ]
            for selector in selectors:
                try:
                    if browser_page.wait_for_selector(selector, timeout=11000):
                        if 'topic-item' in selector:
                            # 新版布局
                            discussions = browser_page.evaluate("""
                                () => {
                                    const items = document.querySelectorAll('.article .topic-item');
                                    return Array.from(items).map(item => {
                                        const titleLink = item.querySelector('.title a');
                                        return {
                                            title: (titleLink?.getAttribute('title') || titleLink?.textContent)?.trim().replace(/\s/g, ''),
                                            link: titleLink?.href,
                                            author: item.querySelector('.user-info a')?.textContent?.trim(),
                                            time: item.querySelector('.time')?.textContent?.trim()
                                        };
                                    });
                                }
                            """)
                        else:
                            # 旧版布局
                            discussions = browser_page.evaluate("""
                                () => {
                                    const rows = document.querySelectorAll('table.olt tr');
                                    return Array.from(rows).slice(1).map(row => {
                                        const titleLink = row.querySelector('td.title a');
                                        return {
                                            title: (titleLink?.getAttribute('title') || titleLink?.textContent)?.trim().replace(/\s/g, ''),
                                            link: titleLink?.href,
                                            author: row.querySelector('td:nth-child(2) a')?.textContent?.trim(),
                                            time: row.querySelector('td:nth-child(4)')?.textContent?.trim()
                                        };
                                    });
                                }
                            """)

                        if discussions and len(discussions) > 0:
                            return discussions
                except:
                    continue

            return []

        except Exception as e:
            print(f"爬取失败: {str(e)}")
            return []
        finally:
            try:
                context.close()
            except:
                pass

    def _handle_verification(self, page) -> None:
        """处理反爬虫验证"""
        try:
            if page.query_selector('#sub'):
                page.wait_for_selector('#sub', state='visible', timeout=11000)
                page.click('#sub')
                page.wait_for_load_state('networkidle')
                time.sleep(2)
        except:
            pass

    def close(self):
        """关闭浏览器"""
        self.browser.close()
        self.playwright.stop()


if __name__ == '__main__':
    scraper = DoubanScraper()
    try:
        results = scraper.get_group_discussions('shanghaizufang')
        with open('discussions.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    finally:
        scraper.close()
