#!/usr/bin/env python3
"""
历史记录查看脚本
用于查看已推送新闻的历史记录
"""

import sys
from pathlib import Path

# 添加 agent 目录到路径
agent_dir = Path(__file__).parent.parent / "extensions" / "hotnews-agent"
sys.path.insert(0, str(agent_dir))

from storage import HistoryStorage
from loguru import logger
import sqlite3


def main():
    """主函数"""
    logger.info("查询历史记录...")
    
    storage = HistoryStorage()
    
    # 获取统计信息
    stats = storage.get_stats()
    
    print("\n" + "=" * 60)
    print("历史记录统计")
    print("=" * 60)
    print(f"总记录数：{stats.get('total_count', 0)}")
    print(f"最近7天：{stats.get('recent_7days_count', 0)}")
    print(f"最早记录：{stats.get('earliest_record', 'N/A')}")
    print(f"最新记录：{stats.get('latest_record', 'N/A')}")
    print("=" * 60)
    
    # 查询最近的记录
    try:
        with sqlite3.connect(storage.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT title, score, sent_at, url
                FROM sent_news
                ORDER BY sent_at DESC
                LIMIT 20
            """)
            
            rows = cursor.fetchall()
            
            if rows:
                print("\n最近推送的 20 条新闻：\n")
                for i, row in enumerate(rows, 1):
                    print(f"{i}. [{row['score']:.2f}] {row['title']}")
                    print(f"   时间：{row['sent_at']}")
                    print(f"   链接：{row['url']}")
                    print()
            else:
                print("\n暂无历史记录")
                
    except Exception as e:
        logger.error(f"查询历史记录失败: {e}")


if __name__ == "__main__":
    main()





