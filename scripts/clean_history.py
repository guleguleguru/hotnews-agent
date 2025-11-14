#!/usr/bin/env python3
"""
历史记录清理脚本
用于手动清理历史记录数据库
"""

import sys
from pathlib import Path

# 添加 agent 目录到路径
agent_dir = Path(__file__).parent.parent / "extensions" / "hotnews-agent"
sys.path.insert(0, str(agent_dir))

from storage import HistoryStorage
from loguru import logger
import argparse


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="清理历史记录")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="保留最近 N 天的记录（默认 30 天）"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="清空所有记录"
    )
    
    args = parser.parse_args()
    
    storage = HistoryStorage()
    
    # 显示当前统计
    stats = storage.get_stats()
    print(f"\n当前记录数：{stats.get('total_count', 0)}")
    
    if args.all:
        # 确认删除
        confirm = input("\n⚠️  确定要删除所有历史记录吗？(yes/no): ")
        if confirm.lower() != "yes":
            print("已取消")
            return
        
        # 删除数据库文件
        if storage.db_path.exists():
            storage.db_path.unlink()
            print("✅ 已删除所有历史记录")
        else:
            print("历史记录数据库不存在")
    else:
        # 清理旧记录
        logger.info(f"清理超过 {args.days} 天的记录...")
        storage.cleanup_old_records(days=args.days)
        
        # 显示清理后统计
        stats = storage.get_stats()
        print(f"\n清理后记录数：{stats.get('total_count', 0)}")


if __name__ == "__main__":
    main()





