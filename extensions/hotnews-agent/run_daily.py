"""
主执行入口
串联整个流程：NewsScore 评分 → 过滤 → 中文化 → 推送
"""

import sys
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import List
from loguru import logger
from config import config
from newscore_adapter import NewsScoreAdapter, NewsScoredItem, generate_mock_scored_news, fetch_and_score_real_news
from title_rewriter import TitleRewriter
from summary_generator import SummaryGenerator
from email_push import EmailPusher
from storage import HistoryStorage
from full_text_extractor import FullTextExtractor
from run_artifact import RunArtifact
from news_scorer import NewsScorer


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


def title_similarity(title1: str, title2: str, use_tfidf: bool = True) -> float:
    """
    计算两个标题的相似度（0.0-1.0）
    
    优先使用 TF-IDF cosine 相似度，回退到 SequenceMatcher
    
    Args:
        title1: 标题1
        title2: 标题2
        use_tfidf: 是否使用 TF-IDF（需要 sklearn）
    
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
    
    # 尝试使用 TF-IDF cosine 相似度
    if use_tfidf:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            
            vectorizer = TfidfVectorizer()
            tfidf_matrix = vectorizer.fit_transform([norm1, norm2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            
            # 额外检查：如果标题长度差异过大，降低相似度
            len_ratio = min(len(norm1), len(norm2)) / max(len(norm1), len(norm2))
            if len_ratio < 0.5:  # 长度差异超过50%
                similarity *= 0.7
            
            return float(similarity)
        except ImportError:
            logger.debug("sklearn 未安装，回退到 SequenceMatcher")
        except Exception as e:
            logger.debug(f"TF-IDF 计算失败: {e}，回退到 SequenceMatcher")
    
    # 回退到 SequenceMatcher
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
    
    # 第一步：去除已发送的新闻（基于URL，只检查最近N天内的记录）
    deduped_by_url = [
        item for item in items 
        if not storage.is_sent(item.url, days=config.DEDUP_WINDOW_DAYS)
    ]
    logger.info(f"URL去重（最近{config.DEDUP_WINDOW_DAYS}天）: {len(items)} -> {len(deduped_by_url)}")
    
    # 第二步：去除标题相似的重复新闻（不同来源的同一条新闻）
    deduped_by_title = deduplicate_by_title_similarity(
        deduped_by_url, 
        similarity_threshold=config.TITLE_SIMILARITY_THRESHOLD
    )
    
    removed_count = len(deduped_by_url) - len(deduped_by_title)
    if removed_count > 0:
        logger.info(f"标题相似度去重: {len(deduped_by_url)} -> {len(deduped_by_title)} (移除 {removed_count} 条重复新闻)")
    
    return deduped_by_title


def _log_score_distribution(items: List[NewsScoredItem], stage: str = ""):
    """
    输出分数分布统计
    
    Args:
        items: 新闻列表
        stage: 阶段名称（用于日志）
    """
    if not items:
        logger.info(f"{stage}分布统计: 无数据")
        return
    
    import statistics
    
    scores = [item.score for item in items]
    mean_score = statistics.mean(scores)
    std_score = statistics.stdev(scores) if len(scores) > 1 else 0.0
    
    sorted_scores = sorted(scores)
    p10 = sorted_scores[int(len(sorted_scores) * 0.1)] if len(sorted_scores) > 0 else 0
    p50 = sorted_scores[int(len(sorted_scores) * 0.5)] if len(sorted_scores) > 0 else 0
    p90 = sorted_scores[int(len(sorted_scores) * 0.9)] if len(sorted_scores) > 0 else 0
    
    # Tier 统计
    tier_counts = {'S': 0, 'A': 0, 'B': 0, 'C': 0}
    for item in items:
        structured = getattr(item, "structured_data", {})
        tier = structured.get("tier", "C").upper() if structured else "C"
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    # Top 5 / Bottom 5
    sorted_items = sorted(items, key=lambda x: x.score, reverse=True)
    top5 = [(item.title[:50], item.score) for item in sorted_items[:5]]
    bottom5 = [(item.title[:50], item.score) for item in sorted_items[-5:]]
    
    logger.info(f"\n{stage}分布统计:")
    logger.info(f"  Mean: {mean_score:.2f}, Std: {std_score:.2f}")
    logger.info(f"  P10: {p10:.2f}, P50: {p50:.2f}, P90: {p90:.2f}")
    logger.info(f"  Tier分布: S={tier_counts.get('S', 0)}, A={tier_counts.get('A', 0)}, "
               f"B={tier_counts.get('B', 0)}, C={tier_counts.get('C', 0)}")
    logger.info(f"  Top 5:")
    for title, score in top5:
        logger.info(f"    - {title}... ({score:.2f})")
    logger.info(f"  Bottom 5:")
    for title, score in bottom5:
        logger.info(f"    - {title}... ({score:.2f})")


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
    
    # 保存原始新闻（用于 artifact）
    raw_articles = []
    
    if use_mock_data:
        logger.info("使用模拟数据模式")
        scored_items = generate_mock_scored_news()
        raw_articles = [item.to_dict() for item in scored_items]
    else:
        logger.info("使用真实新闻模式（RSS + AI 评分）")
        # 获取最近 48 小时的新闻，最多 50 条
        from rss_fetcher import RSSFetcher
        fetcher = RSSFetcher()
        articles = fetcher.fetch_all(hours=48, max_per_source=15)
        raw_articles = articles.copy()
        
        # AI 评分（使用结构化评分）
        scorer = NewsScorer()
        scoring_limit = 75  # 评分更多新闻，确保有足够候选
        articles_to_score = articles[:scoring_limit]
        scored_articles = scorer.score_batch(articles_to_score)
        
        # 批处理校准
        scored_articles = scorer.calibrate_batch(scored_articles)
        
        # 转换为 NewsScoredItem
        scored_items = []
        for article in scored_articles:
            item = NewsScoredItem(article)
            # 保存结构化数据
            if "structured_data" in article:
                item.structured_data = article["structured_data"]
                # 提取 reasons 用于邮件显示
                item.reasons = article.get("structured_data", {}).get("reasons", [])
            scored_items.append(item)
    
    if not scored_items:
        logger.warning("没有获取到任何新闻，退出")
        sys.exit(0)
    
    logger.info(f"获取到 {len(scored_items)} 条评分新闻")
    
    # 输出分布统计
    _log_score_distribution(scored_items, "评分后")
    
    # 3. 按分数过滤（含动态阈值调整）
    logger.info("\n步骤 3/8: 按分数阈值过滤")
    
    # 初始阈值
    current_threshold = config.SCORE_THRESHOLD
    filtered_items = filter_by_score(scored_items, current_threshold)
    
    # 记录阈值调整历史
    threshold_history = [
        {"threshold": current_threshold, "count": len(filtered_items), "step": "initial"}
    ]
    
    # 动态阈值调整：如果过滤后新闻少于 TOPK，逐步降低阈值
    # 但最低不低于 30（避免质量过低的新闻）
    min_threshold = max(30.0, config.SCORE_THRESHOLD - 10.0)  # 最低阈值：30 或 原阈值-10，取较大值
    
    if len(filtered_items) < config.TOPK and current_threshold > min_threshold:
        logger.warning(f"过滤后只有 {len(filtered_items)} 条新闻（需要 {config.TOPK} 条），尝试降低阈值...")
        
        # 逐步降低阈值（每次降 5 分），直到有足够新闻或达到最低阈值
        for adjusted_threshold in [current_threshold - 5, current_threshold - 10, min_threshold]:
            if adjusted_threshold < min_threshold:
                break
            
            adjusted_items = filter_by_score(scored_items, adjusted_threshold)
            threshold_history.append({
                "threshold": adjusted_threshold,
                "count": len(adjusted_items),
                "step": "adjusted"
            })
            
            if len(adjusted_items) >= config.TOPK:
                filtered_items = adjusted_items
                current_threshold = adjusted_threshold
                logger.info(f"✅ 阈值已调整为 {adjusted_threshold}，获得 {len(filtered_items)} 条新闻")
                break
            elif len(adjusted_items) > len(filtered_items):
                # 即使不够 TOPK，也比之前多，就采用
                filtered_items = adjusted_items
                current_threshold = adjusted_threshold
                logger.info(f"⚠️ 阈值已调整为 {adjusted_threshold}，获得 {len(filtered_items)} 条新闻（仍少于 {config.TOPK} 条）")
    
    # 保存 Top 3（用于空结果回退）
    fallback_items = sorted(scored_items, key=lambda x: x.score, reverse=True)[:3]
    
    # 输出分布统计
    _log_score_distribution(filtered_items, "过滤后")
    
    # 4. 去重（可选）
    logger.info("\n步骤 4/8: 去重过滤")
    storage = HistoryStorage()
    
    if filtered_items:
        deduped_items = deduplicate_news(filtered_items, storage)
    else:
        deduped_items = []
        logger.warning(f"没有新闻满足阈值 >= {current_threshold}")
    
    # 4.5 智能回退：如果去重后新闻少于 TOPK，尝试使用更多候选
    if len(deduped_items) < config.TOPK and len(filtered_items) > len(deduped_items):
        # 如果去重导致新闻减少，尝试从所有评分新闻中选择（即使低于阈值）
        logger.warning(f"去重后只有 {len(deduped_items)} 条新闻（需要 {config.TOPK} 条），尝试补充候选...")
        
        # 从所有评分新闻中选择 Top N（N = TOPK * 2），然后去重
        all_candidates = sorted(scored_items, key=lambda x: x.score, reverse=True)[:config.TOPK * 2]
        additional_deduped = deduplicate_news(all_candidates, storage)
        
        # 合并去重后的结果（优先使用高分的）
        combined_items = deduped_items + [item for item in additional_deduped if item not in deduped_items]
        combined_items = sorted(combined_items, key=lambda x: x.score, reverse=True)[:config.TOPK * 2]
        
        if len(combined_items) > len(deduped_items):
            deduped_items = combined_items
            logger.info(f"✅ 补充候选后获得 {len(deduped_items)} 条新闻")
    
    # 5. 排序并限制数量（含费用控制）
    logger.info("\n步骤 5/8: 排序并限制数量")
    
    if deduped_items:
        # 费用控制：最多处理 MAX_ITEMS 条
        final_items = sort_and_limit(deduped_items, config.TOPK, config.MAX_ITEMS)
        
        # 如果最终新闻少于 TOPK，记录警告但继续处理
        if len(final_items) < config.TOPK:
            logger.warning(f"⚠️ 最终只有 {len(final_items)} 条新闻（目标 {config.TOPK} 条），将发送 {len(final_items)} 条")
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
        
        # 6.2 改写标题（所有新闻，根据语言配置）
        lang = config.LANGUAGE
        logger.info(f"开始生成标题（语言: {lang}）...")
        rewriter = TitleRewriter(language=lang)
        final_items = rewriter.rewrite_batch(final_items)
        
        # 6.3 生成摘要（分层处理：有全文的用全文，没有的用 snippet）
        logger.info(f"开始生成摘要（语言: {lang}）...")
        summarizer = SummaryGenerator(language=lang)
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
        fallback_items=fallback_items if not final_items else None,
        language=config.LANGUAGE
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
        storage_stats = storage.get_stats()
        
        # 计算运行统计
        run_stats = {
            "total_fetched": len(raw_articles),
            "total_scored": len(scored_items),
            "filtered_count": len(filtered_items),
            "deduped_count": len(deduped_items),
            "final_sent": len(final_items),
            "threshold_used": current_threshold,
            "history_count": storage_stats.get('total_count', 0)
        }
        
        logger.info(f"\n运行摘要:")
        logger.info(f"- 总抓取数: {run_stats['total_fetched']}")
        logger.info(f"- 总评分数: {run_stats['total_scored']}")
        logger.info(f"- 过阈值数: {run_stats['filtered_count']}")
        logger.info(f"- 去重后数: {run_stats['deduped_count']}")
        logger.info(f"- 成功发送数: {run_stats['final_sent']}")
        logger.info(f"- 使用阈值: {run_stats['threshold_used']}")
        logger.info(f"- 历史记录数: {run_stats['history_count']}")
        
        # 保存运行 Artifact
        artifact = RunArtifact()
        artifact.save_run(
            date=date_str,
            raw_articles=raw_articles,
            scored_items=scored_items,
            filtered_items=filtered_items,
            deduped_items=deduped_items,
            final_items=final_items,
            threshold_history=threshold_history,
            stats=run_stats
        )
        
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

