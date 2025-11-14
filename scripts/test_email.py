#!/usr/bin/env python3
"""
邮件配置测试脚本
用于验证邮件配置是否正确
"""

import sys
import os
from pathlib import Path

# 添加 agent 目录到路径
agent_dir = Path(__file__).parent.parent / "extensions" / "hotnews-agent"
sys.path.insert(0, str(agent_dir))

from config import config
from email_push import EmailPusher
from newscore_adapter import NewsScoredItem
from loguru import logger


def create_test_news() -> list:
    """创建测试新闻数据"""
    return [
        NewsScoredItem({
            "title": "Test News 1",
            "url": "https://example.com/1",
            "source": "Test Source",
            "published_time": "2025-11-11 08:00:00",
            "snippet": "This is a test news snippet",
            "score": 0.95,
        }),
    ]


def main():
    """主测试函数"""
    logger.info("开始测试邮件配置...")
    
    # 验证配置
    if not config.validate():
        logger.error("配置验证失败")
        return False
    
    logger.info("配置验证通过")
    logger.info(config.get_summary())
    
    # 创建测试数据
    test_items = create_test_news()
    test_items[0].title_zh = "测试新闻标题"
    test_items[0].summary_zh = "这是一条测试新闻摘要，用于验证邮件推送功能是否正常。"
    
    # 发送测试邮件
    logger.info("发送测试邮件...")
    pusher = EmailPusher()
    success = pusher.send_daily_digest(test_items, "2025-11-11 (测试)")
    
    if success:
        logger.info("✅ 测试邮件发送成功！")
        logger.info(f"请检查 {config.MAIL_TO} 的收件箱")
        return True
    else:
        logger.error("❌ 测试邮件发送失败")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.exception(f"测试过程中发生错误: {e}")
        sys.exit(1)





