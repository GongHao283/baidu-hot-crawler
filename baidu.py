import pymysql
from dbutils.pooled_db import PooledDB
from typing import List, Dict, Any, Optional

class MySQLHelper:
    """
    使用 DBUtils 连接池封装 MySQL 操作
    """

    def __init__(self, host: str, port: int, user: str, password: str, database: str, charset: str = 'utf8mb4'):
        self.pool = PooledDB(
            creator=pymysql,
            maxconnections=5,
            mincached=2,
            maxcached=3,
            blocking=True,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset=charset,
            cursorclass=pymysql.cursors.DictCursor
        )

    def get_connection(self):
        return self.pool.connection()

    def execute(self, sql: str, params: Optional[tuple] = None) -> int:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                affected_rows = cursor.execute(sql, params)
                conn.commit()
                return affected_rows
        finally:
            conn.close()

    def executemany(self, sql: str, params_list: List[tuple]) -> int:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                affected_rows = cursor.executemany(sql, params_list)
                conn.commit()
                return affected_rows
        finally:
            conn.close()

    def query_one(self, sql: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone()
        finally:
            conn.close()

    def query_all(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
        finally:
            conn.close()

    # ========== 热搜便捷方法 ==========

    def clear_history(self):
        sql = "DELETE FROM baidu_hot_search"
        self.execute(sql)
        print("[DB] 热搜历史数据已清空。")

    def insert_batch(self, data_list: List[Dict[str, Any]]) -> int:
        """
        批量插入热搜数据，返回实际插入的行数
        """
        valid_data = []
        for item in data_list:
            # 从 JSON 中提取字段，标题字段是 'title' 或 'word'，这里我们兼容两种
            title = item.get('title') or item.get('word') or item.get('query')
            rank = item.get('rank') or item.get('index')
            heat = item.get('heat') or item.get('hotScore')
            url = item.get('url')

            # 只有标题和排名都有效时才插入
            if title is not None and rank is not None:
                valid_data.append((rank, title, heat, url))
            else:
                print(f"[DB] 跳过无效数据: rank={rank}, title={title}")

        if not valid_data:
            print("[DB] 没有有效数据可插入。")
            return 0

        sql = """
            INSERT INTO baidu_hot_search (`rank`, title, heat, url, crawl_time)
            VALUES (%s, %s, %s, %s, NOW())
        """
        affected = self.executemany(sql, valid_data)
        print(f"[DB] 成功插入 {affected} 条热搜数据。")
        return affected

    def get_latest(self) -> List[Dict[str, Any]]:
        sql = """
            SELECT `rank`, title, heat, url, crawl_time
            FROM baidu_hot_search
            WHERE crawl_time = (
                SELECT MAX(crawl_time) FROM baidu_hot_search
            )
            ORDER BY `rank`
        """
        return self.query_all(sql)