"""
HotNews Agent - 基于 NewsScore 的热点新闻推送系统

这是一个在 NewsScore 项目基础上构建的每日新闻推送系统：
- 复用 NewsScore 的评分逻辑（不改其算法）
- 按阈值过滤高分新闻
- 生成中文标题和摘要
- 通过邮件推送每日简报
"""

__version__ = "1.0.0"
__author__ = "HotNews Agent Team"
__license__ = "MIT"

from .config import config
from .newscore_adapter import NewsScoreAdapter, NewsScoredItem, fetch_and_score_real_news
from .rss_fetcher import RSSFetcher
from .news_scorer import NewsScorer
from .zh_rewrite import ChineseTitleRewriter
from .zh_summary import ChineseSummaryGenerator
from .email_push import EmailPusher
from .storage import HistoryStorage
from .full_text_extractor import FullTextExtractor

__all__ = [
    "config",
    "NewsScoreAdapter",
    "NewsScoredItem",
    "fetch_and_score_real_news",
    "RSSFetcher",
    "NewsScorer",
    "ChineseTitleRewriter",
    "ChineseSummaryGenerator",
    "EmailPusher",
    "HistoryStorage",
    "FullTextExtractor",
]

