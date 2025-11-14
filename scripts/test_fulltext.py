"""
测试全文抓取功能
"""

import sys
from pathlib import Path

# 添加 agent 目录到路径
agent_dir = Path(__file__).parent.parent / "extensions" / "hotnews-agent"
sys.path.insert(0, str(agent_dir))

from full_text_extractor import FullTextExtractor
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO")

def test_single_url():
    """测试单个 URL"""
    extractor = FullTextExtractor()
    
    # 测试 URL（选择一个常见的新闻网站）
    test_url = "https://www.bbc.com/news/technology"
    
    logger.info(f"测试 URL: {test_url}")
    text = extractor.extract(test_url, max_paragraphs=3)
    
    if text:
        logger.info(f"✓ 提取成功！")
        logger.info(f"正文长度: {len(text)} 字符")
        logger.info(f"\n正文预览:\n{text[:500]}...")
    else:
        logger.error("✗ 提取失败")

def test_batch_urls():
    """测试批量 URL"""
    extractor = FullTextExtractor()
    
    # 测试多个 URL
    test_urls = [
        "https://www.bbc.com/news/technology",
        "https://techcrunch.com/",
    ]
    
    logger.info(f"测试批量提取: {len(test_urls)} 个 URL")
    results = extractor.extract_batch(test_urls, max_paragraphs=2, delay=1.0)
    
    for url, text in results.items():
        if text:
            logger.info(f"✓ {url}: {len(text)} 字符")
        else:
            logger.warning(f"✗ {url}: 提取失败")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="测试全文抓取功能")
    parser.add_argument("--batch", action="store_true", help="测试批量提取")
    parser.add_argument("--url", type=str, help="测试单个 URL")
    
    args = parser.parse_args()
    
    if args.url:
        extractor = FullTextExtractor()
        text = extractor.extract(args.url, max_paragraphs=3)
        if text:
            logger.info(f"✓ 提取成功！")
            logger.info(f"正文长度: {len(text)} 字符")
            logger.info(f"\n正文预览:\n{text[:500]}...")
        else:
            logger.error("✗ 提取失败")
    elif args.batch:
        test_batch_urls()
    else:
        test_single_url()

