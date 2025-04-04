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

            # 修改加载策略
            browser_page.set_default_timeout(30000)  # 保持30秒超时
            browser_page.set_default_navigation_timeout(30000)

            # 设置请求头
            browser_page.set_extra_http_headers({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
                'Cache-Control': 'max-age=0',
            })

            # 修改加载策略，不等待网络空闲
            response = browser_page.goto(url, wait_until='domcontentloaded')

            if response is None:
                print("页面响应为空")
                return []

            try:
                content = browser_page.content()

            except Exception as e:
                print(f"获取页面内容失败: {e}")

            if response.status != 200:
                print(f"页面加载失败: status={response.status}")
                print(f"响应URL: {response.url}")
                try:
                    print(f"页面文本: {content[:500]}...")  # 只打印前500个字符
                except:
                    pass
                return []

            # 先等待页面基本元素加载
            try:
                browser_page.wait_for_selector('body', timeout=5000)
            except Exception as e:
                print(f"等待body元素失败: {e}")
                return []

            # 处理可能的验证
            self._handle_verification(browser_page)

            # 尝试不同的选择器
            selectors = [
                '.article .topic-item',  # 新版布局
                'table.olt tr',  # 旧版布局
                '#content table tr'  # 备用选择器
            ]

            for selector in selectors:
                try:
                    if browser_page.wait_for_selector(selector, timeout=5000):
                        if 'topic-item' in selector:
                            # 新版布局
                            discussions = browser_page.evaluate("""
                                () => {
                                    const items = document.querySelectorAll('.article .topic-item');
                                    return Array.from(items).map(item => ({
                                        title: item.querySelector('.title a')?.textContent?.trim(),
                                        link: item.querySelector('.title a')?.href,
                                        author: item.querySelector('.user-info a')?.textContent?.trim(),
                                        time: item.querySelector('.time')?.textContent?.trim()
                                    }));
                                }
                            """)
                        else:
                            # 旧版布局
                            discussions = browser_page.evaluate("""
                                () => {
                                    const rows = document.querySelectorAll('table.olt tr');
                                    return Array.from(rows).slice(1).map(row => ({
                                        title: row.querySelector('td.title a')?.textContent?.trim(),
                                        link: row.querySelector('td.title a')?.href,
                                        author: row.querySelector('td:nth-child(2) a')?.textContent?.trim(),
                                        time: row.querySelector('td:nth-child(4)')?.textContent?.trim()
                                    }));
                                }
                            """)

                        if discussions and len(discussions) > 0:
                            context.close()
                            return discussions
                except Exception as e:
                    # print(f"选择器 {selector} 失败: {str(e)}")
                    continue

            print("所有选择器都失败了")
            return []

        except Exception as e:
            print(f"爬取失败: {str(e)}")
            import traceback
            print(f"详细错误信息: {traceback.format_exc()}")
            return []
        finally:
            try:
                context.close()
            except:
                pass

    def _handle_verification(self, page) -> None:
        """处理反爬虫验证"""
        try:
            # 检查是否存在验证按钮
            if page.query_selector('#sub'):
                print("发现验证按钮，等待处理...")
                # 等待按钮可点击
                page.wait_for_selector('#sub', state='visible', timeout=10000)
                # 点击验证按钮
                page.click('#sub')
                # 等待页面加载完成
                page.wait_for_load_state('networkidle')
                print("验证处理完成")

                # 额外等待一下，确保页面完全加载
                time.sleep(2)

        except Exception as e:
            print(f"处理验证失败: {str(e)}")

    def close(self):
        """关闭浏览器"""
        self.browser.close()
        self.playwright.stop()


if __name__ == '__main__':
    scraper = DoubanScraper()
    try:
        # 爬取上海租房小组第一页数据
        results = scraper.get_group_discussions('shanghaizufang')
        # 保存结果
        with open('discussions.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"成功爬取 {len(results)} 条数据")
    finally:
        scraper.close()
