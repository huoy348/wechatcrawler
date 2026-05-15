# -*- coding: utf-8 -*-
"""
Database Operations Module - Optimized Edition
Focuses on cookie management and basic data operations
"""
import pymysql
from config import DB_CONFIG
import json
from datetime import datetime


class WeChatDB:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Connect to the database"""
        try:
            self.conn = pymysql.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            print(f"✅ Database connected successfully: {DB_CONFIG['host']}/{DB_CONFIG['database']}")
        except pymysql.MySQLError as e:
            print(f"❌ Database connection failed: {e}")
            raise

    def create_tables(self):
        """Create required tables"""
        tables = [
            # Cookie cache table
            """CREATE TABLE IF NOT EXISTS wechat_cookies (
                id INT AUTO_INCREMENT PRIMARY KEY,
                cookie_data JSON NOT NULL,
                token VARCHAR(50) NOT NULL,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                is_valid TINYINT(1) DEFAULT 1
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            
            # Official Account info table
            """CREATE TABLE IF NOT EXISTS wechat_accounts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                account_name VARCHAR(100) NOT NULL,
                fakeid VARCHAR(50) UNIQUE NOT NULL,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            
            # Articles table
            """CREATE TABLE IF NOT EXISTS wechat_articles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                account_id INT NOT NULL,
                title VARCHAR(200) NOT NULL,
                publish_time DATETIME NULL,
                link VARCHAR(500) UNIQUE NOT NULL,
                content TEXT NULL,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                KEY idx_account_id (account_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            
            # Article statistics table
            """CREATE TABLE IF NOT EXISTS wechat_article_stats (
                id INT AUTO_INCREMENT PRIMARY KEY,
                article_id INT NOT NULL UNIQUE,
                read_num INT DEFAULT 0,
                like_num INT DEFAULT 0,
                share_num INT DEFAULT 0,
                recommend_num INT DEFAULT 0,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            
            # Comments table
            """CREATE TABLE IF NOT EXISTS wechat_comments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                article_id INT NOT NULL,
                nickname VARCHAR(100),
                content TEXT,
                comment_time DATETIME,
                is_top TINYINT DEFAULT 0,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                KEY idx_article_id (article_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            
            # Crawl tasks table
            """CREATE TABLE IF NOT EXISTS crawl_tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                gzh_name VARCHAR(100) NOT NULL UNIQUE,
                type TINYINT DEFAULT 1 COMMENT '1=OEM 2=Customer 3=Competitor',
                status TINYINT DEFAULT 1 COMMENT '1=Enabled 0=Disabled'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        ]
        
        try:
            for sql in tables:
                self.cursor.execute(sql)
            self.conn.commit()
            print("✅ Database tables initialized")
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Failed to create tables: {e}")

    # ====================== Cookie Operations ======================
    
    def has_cookie(self):
        """Check if a cookie exists in the database"""
        try:
            self.cursor.execute("SELECT COUNT(*) as cnt FROM wechat_cookies WHERE is_valid=1")
            result = self.cursor.fetchone()
            return result['cnt'] > 0 if result else False
        except Exception as e:
            print(f"❌ Failed to check cookie: {e}")
            return False

    def save_cookie(self, cookie_data, token):
        """Save cookie to the database"""
        try:
            # Mark the old cookie as invalid
            self.cursor.execute("UPDATE wechat_cookies SET is_valid=0 WHERE is_valid=1")
            # Insert new cookie
            sql = "INSERT INTO wechat_cookies (cookie_data, token, is_valid) VALUES (%s, %s, 1)"
            self.cursor.execute(sql, (json.dumps(cookie_data), token))
            self.conn.commit()
            print("✅ Cookie saved to database")
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Failed to save cookie: {e}")

    def get_latest_valid_cookie(self):
        """Retrieve the latest valid cookie"""
        try:
            self.cursor.execute(
                "SELECT cookie_data, token FROM wechat_cookies WHERE is_valid=1 ORDER BY update_time DESC LIMIT 1"
            )
            res = self.cursor.fetchone()
            if res:
                return json.loads(res['cookie_data']), res['token']
            return None, None
        except Exception as e:
            print(f"❌ Failed to retrieve cookie: {e}")
            return None, None

    # ====================== Official Account Operations ======================
    
    def get_account_info(self, account_name):
        """Retrieve Official Account info (id, fakeid) from the database; returns None if not found"""
        try:
            self.cursor.execute("SELECT id, fakeid FROM wechat_accounts WHERE account_name=%s", (account_name,))
            row = self.cursor.fetchone()
            return row  # {'id': ..., 'fakeid': ...} or None
        except Exception as e:
            print(f"❌ Failed to query Official Account info: {e}")
            return None

    def save_account(self, account_name, fakeid):
        """Save Official Account info and return account_id"""
        try:
            sql = """INSERT INTO wechat_accounts (account_name, fakeid) VALUES (%s, %s)
                     ON DUPLICATE KEY UPDATE fakeid=VALUES(fakeid)"""
            self.cursor.execute(sql, (account_name, fakeid))
            self.conn.commit()
            self.cursor.execute("SELECT id FROM wechat_accounts WHERE account_name=%s", (account_name,))
            return self.cursor.fetchone()['id']
        except Exception as e:
            print(f"❌ Failed to save Official Account: {e}")
            return None

    # ====================== Article Operations ======================
    
    def save_article(self, account_id, title, create_time, link, content):
        """Save an article and return article_id"""
        try:
            if isinstance(create_time, int):
                create_time = datetime.fromtimestamp(create_time)
            sql = """INSERT INTO wechat_articles (account_id, title, publish_time, link, content)
                     VALUES (%s, %s, %s, %s, %s)
                     ON DUPLICATE KEY UPDATE title=VALUES(title), content=VALUES(content)"""
            self.cursor.execute(sql, (account_id, title, create_time, link, content))
            self.conn.commit()
            self.cursor.execute("SELECT id FROM wechat_articles WHERE link=%s", (link,))
            return self.cursor.fetchone()['id']
        except Exception as e:
            print(f"❌ Failed to save article: {e}")
            return None

    def article_exists(self, link):
        """Check if an article already exists; returns article_id or None"""
        try:
            self.cursor.execute("SELECT id FROM wechat_articles WHERE link=%s", (link,))
            row = self.cursor.fetchone()
            return row['id'] if row else None
        except Exception as e:
            print(f"❌ Failed to check article existence: {e}")
            return None

    def save_article_stats(self, article_id, read_num, like_num, share_num, recommend_num):
        """Save article statistics"""
        try:
            sql = """INSERT INTO wechat_article_stats (article_id, read_num, like_num, share_num, recommend_num)
                     VALUES (%s, %s, %s, %s, %s)
                     ON DUPLICATE KEY UPDATE read_num=VALUES(read_num), like_num=VALUES(like_num),
                     share_num=VALUES(share_num), recommend_num=VALUES(recommend_num)"""
            self.cursor.execute(sql, (article_id, read_num, like_num, share_num, recommend_num))
            self.conn.commit()
        except Exception as e:
            print(f"❌ Failed to save statistics: {e}")

    def save_comment(self, article_id, nickname, content, comment_time, is_top=0):
        """Save a comment"""
        try:
            sql = """INSERT IGNORE INTO wechat_comments (article_id, nickname, content, comment_time, is_top)
                     VALUES (%s, %s, %s, %s, %s)"""
            self.cursor.execute(sql, (article_id, nickname, content, comment_time, is_top))
            self.conn.commit()
        except Exception as e:
            print(f"❌ Failed to save comment: {e}")

    # ====================== Crawl Task Operations ======================
    
    def get_crawl_tasks(self):
        """Get the list of enabled crawl tasks"""
        try:
            self.cursor.execute("SELECT gzh_name FROM crawl_tasks WHERE status=1")
            return [row['gzh_name'] for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"❌ Failed to retrieve tasks: {e}")
            return []

    def add_task(self, gzh_name, task_type=1):
        """Add a crawl task"""
        try:
            sql = """INSERT INTO crawl_tasks (gzh_name, type, status) VALUES (%s, %s, 1)
                     ON DUPLICATE KEY UPDATE status=1"""
            self.cursor.execute(sql, (gzh_name, task_type))
            self.conn.commit()
            print(f"✅ Crawl task added: {gzh_name}")
        except Exception as e:
            print(f"❌ Failed to add task: {e}")

    def close(self):
        """Close the database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()