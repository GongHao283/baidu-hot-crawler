# baidu_crawler.py
import requests
import time
import random
from bs4 import BeautifulSoup
from mysql_helper import MySQLHelper
from typing import List, Dict, Any

class BaiduHotCrawler:
    """
    Baidu Hot Search crawler.
    Responsible for fetching, parsing, and storing Baidu hot search data.
    """

    # Table name and column definitions
    TABLE_NAME = "baidu_hot_search"
    TABLE_COLUMNS = """
        id INT AUTO_INCREMENT PRIMARY KEY,
        `rank` INT NOT NULL,
        title VARCHAR(255) NOT NULL,
        heat VARCHAR(50),
        url VARCHAR(500),
        crawl_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    """
    DATE_COLUMN = "crawl_time"

    def __init__(self, db_helper: MySQLHelper, request_delay: float = 1.0):
        """
        :param db_helper: MySQLHelper instance
        :param request_delay: Request delay in seconds to avoid sending requests too quickly
        """
        self.db = db_helper
        self.delay = request_delay
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.baidu.com/',
        }
        # Initialize the table structure
        self._init_table()

    def _init_table(self):
        """Create the table if it does not exist."""
        self.db.create_table(self.TABLE_NAME, self.TABLE_COLUMNS, if_not_exists=True)
        # Attempt to add an index (older MySQL versions may not support IF NOT EXISTS, so use try)
        try:
            self.db.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.DATE_COLUMN} ON {self.TABLE_NAME} ({self.DATE_COLUMN})")
        except Exception:
            pass

    def _fetch_html(self, url: str) -> str:
        """Request the webpage and return the HTML text."""
        time.sleep(random.uniform(0.5, self.delay))
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            return ""

    def _parse_html(self, html: str) -> List[Dict[str, Any]]:
        """
        Parse HTML and return a list of data items, each containing rank, title, heat, url.
        Only items with a numeric rank (rank >= 1) are kept.
        """
        soup = BeautifulSoup(html, 'html.parser')
        items = []

        containers = soup.find_all('div', {'class': 'category-wrap_iQLoo horizontal_1eKyQ'})
        if not containers:
            print("No hot search item containers found. The page structure may have changed.")
            return items

        print(f"Found {len(containers)} item containers")

        for container in containers:
            title_elem = container.find('div', {'class': 'c-single-text-ellipsis'})
            title = title_elem.get_text(strip=True) if title_elem else None
            if not title:
                continue

            heat_elem = container.find('div', {'class': 'hot-index_1Bl1a'})
            heat = heat_elem.get_text(strip=True) if heat_elem else None

            rank_elem = container.find('div', {'class': 'index_1Ew5p'})
            if not rank_elem:
                continue
            rank_text = rank_elem.get_text(strip=True)
            if not rank_text.isdigit():
                continue
            rank = int(rank_text)
            if rank < 1:
                continue

            url = f"https://www.baidu.com/s?wd={title}"

            items.append({
                'rank': rank,
                'title': title,
                'heat': heat,
                'url': url
            })

        return items

    def _save_to_db(self, data_list: List[Dict[str, Any]]) -> int:
        """
        Save data to the database using a custom SQL statement to ensure crawl_time = NOW()
        is treated as a SQL function rather than a string.
        """
        if not data_list:
            return 0
        valid = [(item['rank'], item['title'], item['heat'], item['url']) for item in data_list]
        sql = f"""
            INSERT INTO {self.TABLE_NAME} (`rank`, title, heat, url, crawl_time)
            VALUES (%s, %s, %s, %s, NOW())
        """
        return self.db.executemany(sql, valid)

    def delete_old_data(self, days: int = 1) -> int:
        """Delete old data older than the specified number of days."""
        return self.db.delete_older_than(self.TABLE_NAME, self.DATE_COLUMN, days)

    def run(self, top_n: int = 10) -> None:
        """
        Execute the main crawler workflow (overwrite mode: only the latest top_n items are kept).
        """
        # 1. Truncate the entire table to achieve overwrite
        truncate_sql = f"TRUNCATE TABLE {self.TABLE_NAME}"
        self.db.execute(truncate_sql)
        print(f"Truncated table {self.TABLE_NAME}, ready to store fresh data.")

        # 2. Fetch
        url = "https://top.baidu.com/board?tab=realtime"
        print("Starting to crawl Baidu hot search...")
        html = self._fetch_html(url)
        if not html:
            print("Failed to retrieve webpage content. Exiting.")
            return

        # 3. Parse
        hot_list = self._parse_html(html)
        if not hot_list:
            print("No valid hot search data parsed.")
            return

        print(f"Successfully parsed {len(hot_list)} valid hot search items (pinned items filtered out).")

        # 4. Take the top N items
        top_data = hot_list[:top_n]
        print(f"Preparing to store top {len(top_data)} items:")
        for i, item in enumerate(top_data, 1):
            print(f"  {i}. Rank {item['rank']} - {item['title']} (Heat: {item['heat']})")

        # 5. Insert into database
        inserted = self._save_to_db(top_data)
        print(f"Successfully inserted {inserted} records.")