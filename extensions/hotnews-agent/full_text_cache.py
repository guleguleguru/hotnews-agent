"""
全文缓存模块
使用 SQLite 缓存抓取的全文内容，7天过期策略
"""

import sqlite3
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from loguru import logger
from storage import HistoryStorage


class FullTextCache:
    """全文缓存管理器"""
    
    def __init__(self, db_path: str = "./history/fulltext_cache.db"):
        """
        初始化缓存
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS fulltext_cache (
                        url_hash TEXT PRIMARY KEY,
                        url TEXT NOT NULL,
                        content TEXT NOT NULL,
                        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_fetched_at 
                    ON fulltext_cache(fetched_at)
                """)
                
                conn.commit()
                logger.debug("全文缓存数据库初始化完成")
                
        except Exception as e:
            logger.error(f"全文缓存数据库初始化失败: {e}")
    
    def get(self, url: str) -> Optional[str]:
        """
        获取缓存的全文内容
        
        Args:
            url: 新闻 URL
        
        Returns:
            Optional[str]: 全文内容，如果不存在或已过期返回 None
        """
        url_hash = HistoryStorage.hash_url(url)
        cutoff_date = datetime.now() - timedelta(days=7)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT content FROM fulltext_cache 
                    WHERE url_hash = ? AND fetched_at >= ?
                    LIMIT 1
                    """,
                    (url_hash, cutoff_date.isoformat())
                )
                row = cursor.fetchone()
                if row:
                    logger.debug(f"✅ 缓存命中: {url[:50]}...")
                    return row[0]
                else:
                    logger.debug(f"❌ 缓存未命中: {url[:50]}...")
                    return None
                    
        except Exception as e:
            logger.error(f"获取缓存失败: {e}")
            return None
    
    def set(self, url: str, content: str):
        """
        设置缓存
        
        Args:
            url: 新闻 URL
            content: 全文内容
        """
        url_hash = HistoryStorage.hash_url(url)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO fulltext_cache (url_hash, url, content, fetched_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (url_hash, url, content, datetime.now().isoformat())
                )
                conn.commit()
                logger.debug(f"✅ 缓存已保存: {url[:50]}... ({len(content)} 字符)")
                
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
    
    def cleanup_old(self, days: int = 7):
        """
        清理过期缓存
        
        Args:
            days: 保留天数
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM fulltext_cache WHERE fetched_at < ?",
                    (cutoff_date.isoformat(),)
                )
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"已清理 {deleted_count} 条过期缓存（超过 {days} 天）")
                
        except Exception as e:
            logger.error(f"清理缓存失败: {e}")

