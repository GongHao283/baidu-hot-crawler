# baidu_crawler.py
import requests
import time
import random
from bs4 import BeautifulSoup
from mysql_helper import MySQLHelper
from typing import List, Dict, Any

class BaiduHotCrawler:
    """
    百度热搜爬虫类
    负责抓取、解析、存储百度热搜数据
    """

    # 表名和字段定义
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
        :param db_helper: MySQLHelper 实例
        :param request_delay: 请求延迟（秒），避免请求过快
        """
        self.db = db_helper
        self.delay = request_delay
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.baidu.com/',
        }
        # 初始化表结构
        self._init_table()

    def _init_table(self):
        """创建表（如果不存在）"""
        self.db.create_table(self.TABLE_NAME, self.TABLE_COLUMNS, if_not_exists=True)
        # 尝试添加索引（低版本 MySQL 可能不支持 IF NOT EXISTS，故用 try）
        try:
            self.db.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.DATE_COLUMN} ON {self.TABLE_NAME} ({self.DATE_COLUMN})")
        except Exception:
            pass

    def _fetch_html(self, url: str) -> str:
        """请求网页，返回 HTML 文本"""
        time.sleep(random.uniform(0.5, self.delay))
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            print(f"请求失败: {e}")
            return ""

    def _parse_html(self, html: str) -> List[Dict[str, Any]]:
        """
        解析 HTML，返回数据列表，每个元素包含 rank, title, heat, url
        只保留有数字排名的条目（rank >= 1）
        """
        soup = BeautifulSoup(html, 'html.parser')
        items = []

        containers = soup.find_all('div', {'class': 'category-wrap_iQLoo horizontal_1eKyQ'})
        if not containers:
            print("未找到热搜条目容器，页面结构可能已更新。")
            return items

        print(f"找到 {len(containers)} 个条目容器")

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
        """将数据存入数据库，自动添加 crawl_time（使用 NOW()）"""
        if not data_list:
            return 0
        # 使用通用批量插入，自动补充 crawl_time = NOW()
        return self.db.insert_batch_generic(
            self.TABLE_NAME,
            data_list,
            extra_columns={'crawl_time': 'NOW()'}   # 会被 SQL 函数处理，注意 insert_batch_generic 需要特殊支持
        )

    def delete_old_data(self, days: int = 1) -> int:
        """删除超过指定天数的旧数据"""
        return self.db.delete_older_than(self.TABLE_NAME, self.DATE_COLUMN, days)

    def run(self, top_n: int = 10) -> None:
        """
        执行爬虫主流程（覆盖模式：每次运行只保留最新的 top_n 条）
        """
        # 1. 清空整张表（实现覆盖）
        truncate_sql = f"TRUNCATE TABLE {self.TABLE_NAME}"
        self.db.execute(truncate_sql)
        print(f"已清空表 {self.TABLE_NAME}，准备存入最新数据。")

        # 2. 抓取
        url = "https://top.baidu.com/board?tab=realtime"
        print("开始抓取百度热搜...")
        html = self._fetch_html(url)
        if not html:
            print("获取网页内容失败，退出。")
            return

        # 3. 解析
        hot_list = self._parse_html(html)
        if not hot_list:
            print("未解析到有效热搜数据。")
            return

        print(f"成功解析 {len(hot_list)} 条有效热搜（已过滤置顶）")

        # 4. 取前 top_n 条
        top_data = hot_list[:top_n]
        print(f"准备存入前 {len(top_data)} 条：")
        for i, item in enumerate(top_data, 1):
            print(f"  {i}. 排名 {item['rank']} - {item['title']} (热度: {item['heat']})")

        # 5. 入库
        inserted = self._save_to_db(top_data)
        print(f"成功存入 {inserted} 条数据。")

    
    def _save_to_db(self, data_list: List[Dict[str, Any]]) -> int:
        """修正版：直接使用自定义 SQL，确保 crawl_time = NOW() 是函数而非字符串"""
        if not data_list:
            return 0
        valid = [(item['rank'], item['title'], item['heat'], item['url']) for item in data_list]
        sql = f"""
            INSERT INTO {self.TABLE_NAME} (`rank`, title, heat, url, crawl_time)
            VALUES (%s, %s, %s, %s, NOW())
        """
        return self.db.executemany(sql, valid)

if __name__ == "__main__":
    # 创建数据库连接对象
    from mysql_helper import MySQLHelper   # 确保 mysql_helper.py 在同一目录

    db = MySQLHelper(
        host='localhost',
        port=3306,
        user='root',
        password='gh000910',
        database='crawler_data'
    )

    # 创建爬虫实例
    crawler = BaiduHotCrawler(db, request_delay=1.0)

    # 运行爬虫（保存前10条）
    crawler.run()
