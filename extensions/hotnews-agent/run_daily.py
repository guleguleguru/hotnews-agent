"""
主执行入口
串联整个流程：NewsScore 评分 → 过滤 → 中文化 → 推送
"""

import sys
import re
from datetime import datetime
from difflib import SequenceMatcher
from loguru import logger
from config import config
from newscore_adapter import NewsScoreAdapter, NewsScoredItem, generate_mock_scored_news, fetch_and_score_real_news
from zh_rewrite import ChineseTitleRewriter
from zh_summary import ChineseSummaryGenerator
from email_push import EmailPusher
from storage import HistoryStorage
from full_text_extractor import FullTextExtractor


# 配置日志
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO"
)
logger.add(
    "logs/hotnews_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
    level="DEBUG"
)


def filter_by_score(items: list[NewsScoredItem], threshold: float) -> list[NewsScoredItem]:
    """
    按分数阈值过滤新闻
    
    Args:
        items: 新闻列表
        threshold: 分数阈值
    
    Returns:
        list: 过滤后的新闻列表
    """
    filtered = [item for item in items if item.score >= threshold]
    logger.info(f"分数过滤: {len(items)} -> {len(filtered)} (阈值 >= {threshold})")
    return filtered


def normalize_title(title: str) -> str:
    """
    归一化标题：去除标点、转小写、去除多余空格
    
    Args:
        title: 原始标题
    
    Returns:
        str: 归一化后的标题
    """
    if not title:
        return ""
    
    # 转小写
    normalized = title.lower()
    
    # 去除标点符号（保留字母、数字、空格）
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    
    # 去除多余空格
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


def title_similarity(title1: str, title2: str) -> float:
    """
    计算两个标题的相似度（0.0-1.0）
    
    使用 SequenceMatcher 计算相似度，并考虑关键词重叠
    
    Args:
        title1: 标题1
        title2: 标题2
    
    Returns:
        float: 相似度分数（0.0-1.0）
    """
    if not title1 or not title2:
        return 0.0
    
    # 归一化标题
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)
    
    if not norm1 or not norm2:
        return 0.0
    
    # 使用 SequenceMatcher 计算相似度
    similarity = SequenceMatcher(None, norm1, norm2).ratio()
    
    # 额外检查：如果标题长度差异过大，降低相似度
    len_ratio = min(len(norm1), len(norm2)) / max(len(norm1), len(norm2))
    if len_ratio < 0.5:  # 长度差异超过50%
        similarity *= 0.7
    
    return similarity


def deduplicate_by_title_similarity(items: list[NewsScoredItem], similarity_threshold: float = 0.75) -> list[NewsScoredItem]:
    """
    基于标题相似度去重（去除不同来源的同一条新闻）
    
    如果发现相似标题，保留分数更高的版本
    
    Args:
        items: 新闻列表
        similarity_threshold: 相似度阈值（默认0.75，即75%相似）
    
    Returns:
        list: 去重后的新闻列表
    """
    if len(items) <= 1:
        return items
    
    # 按分数降序排序，优先保留高分新闻
    sorted_items = sorted(items, key=lambda x: x.score, reverse=True)
    
    unique_items = []
    
    for item in sorted_items:
        is_duplicate = False
        
        # 检查是否与已保留的新闻标题相似
        for seen_item in unique_items:
            similarity = title_similarity(item.title, seen_item.title)
            
            if similarity >= similarity_threshold:
                is_duplicate = True
                logger.debug(
                    f"发现相似标题（相似度 {similarity:.2f}）:\n"
                    f"  保留: {seen_item.title[:60]}... (分数: {seen_item.score:.2f}, 来源: {seen_item.source})\n"
                    f"  丢弃: {item.title[:60]}... (分数: {item.score:.2f}, 来源: {item.source})"
                )
                break
        
        if not is_duplicate:
            unique_items.append(item)
    
    return unique_items


def deduplicate_news(items: list[NewsScoredItem], storage: HistoryStorage) -> list[NewsScoredItem]:
    """
    去除已发送的新闻和重复新闻（基于URL和标题相似度）
    
    Args:
        items: 新闻列表
        storage: 历史存储
    
    Returns:
        list: 去重后的新闻列表
    """
    if not config.ENABLE_DEDUP:
        logger.info("去重功能已禁用")
        return items
    
    # 第一步：去除已发送的新闻（基于URL）
    deduped_by_url = [item for item in items if not storage.is_sent(item.url)]
    logger.info(f"URL去重: {len(items)} -> {len(deduped_by_url)}")
    
    # 第二步：去除标题相似的重复新闻（不同来源的同一条新闻）
    deduped_by_title = deduplicate_by_title_similarity(
        deduped_by_url, 
        similarity_threshold=config.TITLE_SIMILARITY_THRESHOLD
    )
    
    removed_count = len(deduped_by_url) - len(deduped_by_title)
    if removed_count > 0:
        logger.info(f"标题相似度去重: {len(deduped_by_url)} -> {len(deduped_by_title)} (移除 {removed_count} 条重复新闻)")
    
    return deduped_by_title


def sort_and_limit(items: list[NewsScoredItem], topk: int, max_items: int = None) -> list[NewsScoredItem]:
    """
    按分数排序并限制数量（二级排序：score desc → published_time desc）
    
    Args:
        items: 新闻列表
        topk: 保留前 K 条（用户可见数）
        max_items: 最大处理数（费用控制）
    
    Returns:
        list: 排序和截取后的新闻列表
    """
    # 二级排序：分数降序 → 发布时间降序
    sorted_items = sorted(
        items, 
        key=lambda x: (x.score, x.published_time or ""), 
        reverse=True
    )
    
    # 费用控制：最多处理 MAX_ITEMS 条
    if max_items:
        sorted_items = sorted_items[:max_items]
        logger.info(f"费用控制：限制为前 {max_items} 条进行 LLM 处理")
    
    # 最终输出限制为 topk 条
    final_items = sorted_items[:topk]
    logger.info(f"排序并限制为前 {topk} 条（从 {len(sorted_items)} 条中筛选）")
    return final_items


def main(use_mock_data: bool = False):
    """
    主执行函数
    
    Args:
        use_mock_data: 是否使用模拟数据（用于测试）
    """
    logger.info("=" * 60)
    logger.info("HotNews Agent 开始执行")
    logger.info("=" * 60)
    
    # 1. 验证配置
    logger.info("步骤 1/8: 验证配置")
    if not config.validate():
        logger.error("配置验证失败，退出")
        sys.exit(1)
    logger.info(config.get_summary())
    
    # 2. 获取评分结果（RSS + AI 评分）
    logger.info("\n步骤 2/8: 获取新闻并进行 AI 评分")
    
    if use_mock_data:
        logger.info("使用模拟数据模式")
        scored_items = generate_mock_scored_news()
    else:
        logger.info("使用真实新闻模式（RSS + AI 评分）")
        # 获取最近 48 小时的新闻，最多 50 条
        scored_items = fetch_and_score_real_news(hours=48, max_stories=50)
    
    if not scored_items:
        logger.warning("没有获取到任何新闻，退出")
        sys.exit(0)
    
    logger.info(f"获取到 {len(scored_items)} 条评分新闻")
    
    # 3. 按分数过滤
    logger.info("\n步骤 3/8: 按分数阈值过滤")
    filtered_items = filter_by_score(scored_items, config.SCORE_THRESHOLD)
    
    # 保存 Top 3（用于空结果回退）
    fallback_items = sorted(scored_items, key=lambda x: x.score, reverse=True)[:3]
    
    # 4. 去重（可选）
    logger.info("\n步骤 4/8: 去重过滤")
    storage = HistoryStorage()
    
    if filtered_items:
        deduped_items = deduplicate_news(filtered_items, storage)
    else:
        deduped_items = []
        logger.warning(f"没有新闻满足阈值 >= {config.SCORE_THRESHOLD}")
    
    # 5. 排序并限制数量（含费用控制）
    logger.info("\n步骤 5/8: 排序并限制数量")
    
    if deduped_items:
        # 费用控制：最多处理 MAX_ITEMS 条
        final_items = sort_and_limit(deduped_items, config.TOPK, config.MAX_ITEMS)
    else:
        final_items = []
        logger.warning("所有新闻均已发送过或无符合条件的新闻")
    
    # 6. 分层处理：只对最终要发送的新闻抓取全文并生成高质量摘要
    logger.info("\n步骤 6/8: 分层处理（抓取全文 + 生成中文标题和摘要）")
    
    if final_items:
        # final_items 已经是最终要发送的新闻（最多 TOPK 条）
        # 只对最终要发送的新闻抓取全文（如果配置了 FULL_TEXT_TOP_N，则只抓取前 N 条）
        items_to_fetch = final_items
        if config.FULL_TEXT_TOP_N > 0 and config.FULL_TEXT_TOP_N < len(final_items):
            items_to_fetch = final_items[:config.FULL_TEXT_TOP_N]
            logger.info(f"最终将发送 {len(final_items)} 条新闻，对前 {len(items_to_fetch)} 条抓取全文...")
        else:
            logger.info(f"最终将发送 {len(final_items)} 条新闻，对所有 {len(final_items)} 条抓取全文...")
        
        # 6.1 对选定的新闻抓取全文
        extractor = FullTextExtractor()
        urls = [item.url for item in items_to_fetch]
        full_texts = extractor.extract_batch(
            urls, 
            max_paragraphs=config.FULL_TEXT_MAX_PARAGRAPHS,
            delay=1.0  # 请求间隔1秒，避免被封
        )
        
        # 将全文内容附加到新闻项
        success_count = 0
        for item in items_to_fetch:
            item.full_text = full_texts.get(item.url, "")
            if item.full_text:
                success_count += 1
                logger.debug(f"✓ 全文抓取成功: {item.title[:50]}... ({len(item.full_text)} 字符)")
            else:
                logger.warning(f"✗ 全文抓取失败: {item.title[:50]}...，将使用 snippet")
        
        logger.info(f"全文抓取完成: {success_count}/{len(items_to_fetch)} 成功")
        
        # 6.2 改写标题（所有新闻）
        logger.info("开始生成中文标题...")
        rewriter = ChineseTitleRewriter()
        final_items = rewriter.rewrite_batch(final_items)
        
        # 6.3 生成摘要（分层处理：有全文的用全文，没有的用 snippet）
        logger.info("开始生成中文摘要...")
        summarizer = ChineseSummaryGenerator()
        final_items = summarizer.generate_batch(final_items)
        
        # 统计
        fulltext_count = sum(1 for item in final_items if item.full_text)
        logger.info(f"成功处理 {len(final_items)} 条新闻（其中 {fulltext_count} 条使用全文摘要）")
    else:
        logger.warning("没有新闻需要处理，将发送空结果邮件")
    
    # 7. 邮件推送（含空结果处理）
    logger.info("\n步骤 7/8: 邮件推送")
    pusher = EmailPusher()
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # 发送邮件（如果为空，会自动发送空结果邮件）
    success = pusher.send_daily_digest(
        items=final_items, 
        date=date_str,
        fallback_items=fallback_items if not final_items else None
    )
    
    if success:
        logger.info("✅ 邮件推送成功！")
        
        # 标记为已发送
        if final_items:
            for item in final_items:
                storage.mark_as_sent(item.url, item.title_zh or item.title, item.score)
        
        # 清理旧记录（90天）
        storage.prune()
        
        # 打印统计信息
        stats = storage.get_stats()
        logger.info(f"\n运行摘要:")
        logger.info(f"- 总抓取数: {len(scored_items)}")
        logger.info(f"- 过阈值数: {len(filtered_items)}")
        logger.info(f"- 成功发送数: {len(final_items)}")
        logger.info(f"- 历史记录数: {stats.get('total_count', 0)}")
        
    else:
        logger.error("❌ 邮件推送失败")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("HotNews Agent 执行完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="HotNews Agent - 每日热点新闻推送")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="使用模拟数据（用于测试，不获取真实新闻）"
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="使用真实新闻（RSS + AI 评分）"
    )
    
    args = parser.parse_args()
    
    # 默认使用真实新闻，除非明确指定 --mock
    use_mock = args.mock and not args.real
    
    try:
        main(use_mock_data=use_mock)
    except KeyboardInterrupt:
        logger.warning("用户中断执行")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"执行过程中发生错误: {e}")
        sys.exit(1)

