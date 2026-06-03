import requests
import time
import random
from bs4 import BeautifulSoup
from baidu import MySQLHelper

def fetch_html(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://www.baidu.com/',
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"请求网页失败: {e}")
        return None

def parse_hot_data(html_content):
    """从HTML中解析热搜数据，只保留有数字排名的条目（rank >= 1）"""
    soup = BeautifulSoup(html_content, 'html.parser')
    items = []

    containers = soup.find_all('div', {'class': 'category-wrap_iQLoo horizontal_1eKyQ'})
    if not containers:
        print("未找到热搜条目容器，页面结构可能已更新。")
        return items

    print(f"找到 {len(containers)} 个热搜条目容器。")

    for container in containers:
        # 提取标题
        title_elem = container.find('div', {'class': 'c-single-text-ellipsis'})
        title = title_elem.get_text(strip=True) if title_elem else None
        if not title:
            continue

        # 提取热度值（可以为 None）
        heat_elem = container.find('div', {'class': 'hot-index_1Bl1a'})
        heat = heat_elem.get_text(strip=True) if heat_elem else None

        # 提取排名 —— 关键：必须存在且为数字
        rank_elem = container.find('div', {'class': 'index_1Ew5p'})
        if not rank_elem:
            continue  # 没有排名元素（可能是置顶或其他特殊条目），跳过

        rank_text = rank_elem.get_text(strip=True)
        if not rank_text or not rank_text.isdigit():
            continue  # 排名文本不是纯数字，跳过

        rank = int(rank_text)
        # 确保 rank >= 1（理论上已经是）
        if rank < 1:
            continue

        # 构造链接
        url = f"https://www.baidu.com/s?wd={title}"

        items.append({
            'rank': rank,
            'title': title,
            'heat': heat,
            'url': url
        })

    return items

def crawl_baidu_hot():
    db = MySQLHelper(
        host='localhost',
        port=3306,
        user='root',
        password='gh000910',
        database='crawler_data'
    )
    db.clear_history()

    url = 'https://top.baidu.com/board?tab=realtime'

    try:
        time.sleep(random.uniform(0.5, 2))
        html = fetch_html(url)
        if not html:
            print("无法获取网页内容，程序退出。")
            return

        hot_list = parse_hot_data(html)
        if not hot_list:
            print("未能解析出任何有效数据。")
            return

        # 额外安全过滤：确保每条数据的 rank 都是整数，且不为 None
        valid_data = [item for item in hot_list if isinstance(item.get('rank'), int)]
        if len(valid_data) != len(hot_list):
            print(f"警告：过滤掉了 {len(hot_list) - len(valid_data)} 条 rank 无效的数据")

        top_10 = valid_data[:10]
        print(f"成功解析到 {len(valid_data)} 条有效热搜数据，准备存入前 {len(top_10)} 条。")

        if top_10:
            inserted_count = db.insert_batch(top_10)
            print(f"成功将 {inserted_count} 条数据存入数据库。")
        else:
            print("没有有效数据可存入。")

    except Exception as e:
        print(f"程序执行过程中发生未预期的错误: {e}")

if __name__ == "__main__":
    crawl_baidu_hot()