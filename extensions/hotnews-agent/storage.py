"""
存储模块
管理已推送新闻的历史记录，实现去重功能
"""

import hashlib
import sqlite3
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Set
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from loguru import logger
from config import config


class HistoryStorage:
    """历史记录存储"""
    
    def __init__(self, db_path: str = None):
        """
        初始化存储
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path or config.HISTORY_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sent_news (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url_hash TEXT NOT NULL,
                        date TEXT NOT NULL,
                        url TEXT NOT NULL,
                        title TEXT,
                        score REAL,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(url_hash, date)
                    )
                """)
                
                # 创建索引
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_url_hash_date 
                    ON sent_news(url_hash, date)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sent_at 
                    ON sent_news(sent_at)
                """)
                
                conn.commit()
                logger.debug("历史记录数据库初始化完成")
                
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
    
    @staticmethod
    def normalize_url(url: str) -> str:
        """
        URL 归一化：去除 utm_*、锚点、尾斜杠等
        
        Args:
            url: 原始 URL
        
        Returns:
            str: 归一化后的 URL
        """
        try:
            # 解析 URL
            parsed = urlparse(url)
            
            # 去除 fragment（锚点）
            parsed = parsed._replace(fragment="")
            
            # 解析查询参数
            query_params = parse_qs(parsed.query)
            
            # 过滤掉跟踪参数
            tracking_prefixes = ["utm_", "fbclid", "gclid", "mc_", "ref", "_ga"]
            filtered_params = {
                k: v for k, v in query_params.items()
                if not any(k.startswith(prefix) for prefix in tracking_prefixes)
            }
            
            # 重建查询字符串
            new_query = urlencode(filtered_params, doseq=True) if filtered_params else ""
            parsed = parsed._replace(query=new_query)
            
            # 去除路径末尾的斜杠
            path = parsed.path.rstrip("/") if parsed.path != "/" else parsed.path
            parsed = parsed._replace(path=path)
            
            # 统一小写域名
            parsed = parsed._replace(netloc=parsed.netloc.lower())
            
            return urlunparse(parsed)
            
        except Exception as e:
            logger.warning(f"URL 归一化失败: {url}, 错误: {e}")
            return url
    
    @staticmethod
    def hash_url(url: str) -> str:
        """
        计算 URL 的 MD5 哈希（归一化后）
        
        Args:
            url: 新闻 URL
        
        Returns:
            str: MD5 哈希值
        """
        normalized_url = HistoryStorage.normalize_url(url)
        return hashlib.md5(normalized_url.encode("utf-8")).hexdigest()
    
    def is_sent(self, url: str, days: int = 7) -> bool:
        """
        检查 URL 是否在最近 N 天内已发送
        
        Args:
            url: 新闻 URL
            days: 检查最近N天内的记录（默认7天）
        
        Returns:
            bool: 是否在最近N天内已发送
        """
        url_hash = self.hash_url(url)
        cutoff_date = datetime.now() - timedelta(days=days)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT 1 FROM sent_news 
                    WHERE url_hash = ? AND sent_at >= ?
                    LIMIT 1
                    """,
                    (url_hash, cutoff_date.isoformat())
                )
                return cursor.fetchone() is not None
                
        except Exception as e:
            logger.error(f"查询历史记录失败: {e}")
            return False
    
    def mark_as_sent(self, url: str, title: str = "", score: float = 0.0):
        """
        标记 URL 为已发送（含日期幂等）
        
        Args:
            url: 新闻 URL
            title: 新闻标题
            score: 新闻分数
        """
        url_hash = self.hash_url(url)
        date = datetime.now().strftime("%Y-%m-%d")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sent_news (url_hash, date, url, title, score)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (url_hash, date, url, title, score)
                )
                conn.commit()
                logger.debug(f"已标记为已发送: {url} (日期: {date})")
                
        except Exception as e:
            logger.error(f"标记已发送失败: {e}")
    
    def get_sent_urls(self, days: int = 7) -> Set[str]:
        """
        获取最近 N 天已发送的 URL 集合
        
        Args:
            days: 天数
        
        Returns:
            Set[str]: URL 哈希集合
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT url_hash FROM sent_news 
                    WHERE sent_at >= ?
                    """,
                    (cutoff_date.isoformat(),)
                )
                return {row[0] for row in cursor.fetchall()}
                
        except Exception as e:
            logger.error(f"获取已发送 URL 失败: {e}")
            return set()
    
    def cleanup_old_records(self, days: int = 90):
        """
        清理超过指定天数的旧记录（默认 90 天）
        
        Args:
            days: 保留天数
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM sent_news WHERE sent_at < ?",
                    (cutoff_date.isoformat(),)
                )
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"已清理 {deleted_count} 条超过 {days} 天的旧记录")
                
        except Exception as e:
            logger.error(f"清理旧记录失败: {e}")
    
    def prune(self):
        """自动清理 90 天前的记录（快捷方法）"""
        self.cleanup_old_records(days=90)
    
    def get_stats(self) -> dict:
        """
        获取统计信息
        
        Returns:
            dict: 统计数据
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 总记录数
                cursor = conn.execute("SELECT COUNT(*) FROM sent_news")
                total_count = cursor.fetchone()[0]
                
                # 最近7天记录数
                cutoff_date = datetime.now() - timedelta(days=7)
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM sent_news WHERE sent_at >= ?",
                    (cutoff_date.isoformat(),)
                )
                recent_count = cursor.fetchone()[0]
                
                # 最早和最晚记录
                cursor = conn.execute(
                    "SELECT MIN(sent_at), MAX(sent_at) FROM sent_news"
                )
                min_date, max_date = cursor.fetchone()
                
                return {
                    "total_count": total_count,
                    "recent_7days_count": recent_count,
                    "earliest_record": min_date,
                    "latest_record": max_date,
                }
                
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}

