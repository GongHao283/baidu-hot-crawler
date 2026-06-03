# run.py
from mysql_helper import MySQLHelper
from crawl_baidu_hot import BaiduHotCrawler

if __name__ == "__main__":
    # 数据库配置
    db = MySQLHelper(
        host='localhost',
        port=3306,
        user='root',
        password='gh000910',
        database='crawler_data'
    )

    # 创建爬虫实例（可设置延迟和保存条数）
    crawler = BaiduHotCrawler(db, request_delay=1.0)

    # 运行爬虫，保存前10条
    crawler.run(top_n=10)