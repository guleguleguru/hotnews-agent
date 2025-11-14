#!/usr/bin/env python3
"""
真实新闻测试脚本
测试 RSS 抓取和 AI 评分功能
"""

import sys
from pathlib import Path

# 添加 agent 目录到路径
agent_dir = Path(__file__).parent.parent / "extensions" / "hotnews-agent"
sys.path.insert(0, str(agent_dir))

from loguru import logger
from newscore_adapter import fetch_and_score_real_news


def main():
    """主测试函数"""
    logger.info("=" * 60)
    logger.info("开始测试真实新闻获取和评分")
    logger.info("=" * 60)
    
    # 获取最近 24 小时的新闻，最多 10 条用于测试
    logger.info("\n正在抓取新闻...")
    scored_items = fetch_and_score_real_news(hours=24, max_stories=10)
    
    if not scored_items:
        logger.error("❌ 未获取到任何新闻")
        return False
    
    logger.info(f"\n✅ 成功获取并评分 {len(scored_items)} 条新闻\n")
    
    # 显示结果
    logger.info("=" * 60)
    logger.info("新闻列表（按评分排序）：")
    logger.info("=" * 60)
    
    # 按分数排序
    sorted_items = sorted(scored_items, key=lambda x: x.score, reverse=True)
    
    for i, item in enumerate(sorted_items, 1):
        logger.info(f"\n{i}. [{item.score:.2f}] {item.title}")
        logger.info(f"   来源：{item.source}")
        logger.info(f"   链接：{item.url}")
        if item.snippet:
            logger.info(f"   摘要：{item.snippet[:100]}...")
    
    logger.info("\n" + "=" * 60)
    logger.info("测试完成！✅")
    logger.info("=" * 60)
    
    # 统计信息
    avg_score = sum(item.score for item in scored_items) / len(scored_items)
    high_score_count = sum(1 for item in scored_items if item.score >= 0.7)
    
    logger.info(f"\n统计信息：")
    logger.info(f"- 平均分：{avg_score:.2f}")
    logger.info(f"- 高分新闻（≥0.7）：{high_score_count} 条")
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.exception(f"测试过程中发生错误: {e}")
        sys.exit(1)


