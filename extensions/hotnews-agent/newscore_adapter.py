"""
NewsScore 适配器模块
负责与 NewsScore 项目集成，获取评分结果
"""

import json
import subprocess
import os
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from loguru import logger
from config import config


# NewsScore JSON Schema 定义
NEWSSCORE_SCHEMA = {
    "title": str,
    "url": str,
    "source": str,
    "published_at": str,  # ISO8601
    "score": (float, int),
    "snippet": (str, type(None)),
    "id": (str, type(None))
}


class NewsScoredItem:
    """
    NewsScore 评分后的新闻项
    """
    
    def __init__(self, data: Dict[str, Any]):
        """
        初始化新闻项
        
        Args:
            data: 包含新闻数据的字典
        """
        self.title: str = data.get("title", "")
        self.url: str = data.get("url", "")
        self.source: str = data.get("source", "Unknown")
        # 兼容 published_at 和 published_time
        self.published_time: str = data.get("published_at", "") or data.get("published_time", "")
        self.snippet: str = data.get("snippet") or ""
        self.score: float = float(data.get("score", 0.0))
        self.id: str = data.get("id", "")
        
        # Agent 层新增字段
        self.title_zh: str = ""
        self.summary_zh: str = ""
        self.full_text: str = ""  # 全文内容（用于高质量摘要）
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            Dict: 新闻项数据
        """
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published_time": self.published_time,
            "snippet": self.snippet,
            "score": self.score,
            "title_zh": self.title_zh,
            "summary_zh": self.summary_zh,
            "full_text": self.full_text,
        }
    
    def __repr__(self) -> str:
        return f"<NewsScoredItem score={self.score:.2f} title={self.title[:50]}...>"


def validate_news_item(data: Dict[str, Any]) -> bool:
    """
    验证新闻项是否符合 Schema
    
    Args:
        data: 新闻数据字典
    
    Returns:
        bool: 是否有效
    """
    # 必需字段检查
    required_fields = ["title", "url", "source", "score"]
    for field in required_fields:
        if field not in data:
            logger.warning(f"缺少必需字段: {field}")
            return False
        
        # 检查是否为空
        if data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
            logger.warning(f"字段 {field} 为空")
            return False
    
    # score 类型检查
    score = data.get("score")
    if not isinstance(score, (int, float)):
        logger.warning(f"score 类型错误: {type(score)}, 期望 int/float")
        return False
    
    if score < 0 or score > 1:
        logger.warning(f"score 超出范围 [0, 1]: {score}")
        return False
    
    # published_at 格式检查（如果存在）
    published_at = data.get("published_at") or data.get("published_time")
    if published_at:
        try:
            # 尝试解析 ISO8601 格式
            datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            logger.warning(f"published_at 格式错误: {published_at}")
            # 不阻止，仅警告
    
    return True


class NewsScoreAdapter:
    """
    NewsScore 适配器
    负责调用 NewsScore 并获取评分结果
    """
    
    def __init__(self, newscore_path: str = "./newsscore"):
        """
        初始化适配器
        
        Args:
            newscore_path: NewsScore 项目的路径
        """
        self.newscore_path = Path(newscore_path)
        self.output_file = self.newscore_path / "output" / "scored_news.json"
    
    def run_newscore(self) -> bool:
        """
        运行 NewsScore 评分流程
        
        Returns:
            bool: 是否成功执行
        """
        logger.info("开始运行 NewsScore 评分...")
        
        try:
            # 检查 NewsScore 项目是否存在
            if not self.newscore_path.exists():
                logger.error(f"NewsScore 项目路径不存在: {self.newscore_path}")
                logger.info("请先克隆 NewsScore 项目: git clone https://github.com/themaximalist/newsscore.git")
                return False
            
            # 设置环境变量
            env = os.environ.copy()
            env.update({
                "NEWSSCORE_MODEL_API_KEY": config.NEWSSCORE_MODEL_API_KEY,
                "NEWSSCORE_MODEL_NAME": config.NEWSSCORE_MODEL_NAME,
                "NEWSSCORE_DATA_SOURCES": config.NEWSSCORE_DATA_SOURCES,
            })
            
            # 调用 NewsScore 的执行脚本
            # 注意：这里假设 NewsScore 提供了一个可执行的脚本或 CLI
            # 实际集成时需要根据 NewsScore 的真实接口调整
            
            # 方式1: 通过 CLI 执行
            result = subprocess.run(
                ["python", "newscore_cli.py", "--output", str(self.output_file)],
                cwd=str(self.newscore_path),
                env=env,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode != 0:
                logger.error(f"NewsScore 执行失败: {result.stderr}")
                return False
            
            logger.info("NewsScore 评分完成")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("NewsScore 执行超时")
            return False
        except Exception as e:
            logger.error(f"运行 NewsScore 时出错: {e}")
            return False
    
    def load_scored_results(self, json_path: Optional[str] = None) -> List[NewsScoredItem]:
        """
        加载 NewsScore 的评分结果（含 Schema 校验）
        
        Args:
            json_path: JSON 文件路径（如果不指定则使用默认路径）
        
        Returns:
            List[NewsScoredItem]: 评分后的新闻列表
        """
        if json_path is None:
            json_path = self.output_file
        else:
            json_path = Path(json_path)
        
        logger.info(f"加载评分结果: {json_path}")
        
        try:
            if not json_path.exists():
                logger.error(f"评分结果文件不存在: {json_path}")
                return []
            
            # 读取文件（强制 UTF-8）
            with open(json_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 处理空文件
            if not content.strip():
                logger.warning("JSON 文件为空")
                return []
            
            data = json.loads(content)
            
            # 解析 JSON 数据
            # 根据 NewsScore 的实际输出格式调整
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict) and "items" in data:
                items = data["items"]
            else:
                logger.error(f"未知的 JSON 格式: {type(data)}")
                return []
            
            # 处理空数组
            if not items:
                logger.warning("JSON 中没有新闻项")
                return []
            
            # Schema 校验并创建对象
            scored_items = []
            invalid_count = 0
            
            for i, item in enumerate(items):
                if validate_news_item(item):
                    try:
                        scored_items.append(NewsScoredItem(item))
                    except Exception as e:
                        logger.error(f"创建新闻项失败 (索引 {i}): {e}")
                        invalid_count += 1
                else:
                    logger.warning(f"新闻项校验失败 (索引 {i}): {item}")
                    invalid_count += 1
            
            logger.info(f"成功加载 {len(scored_items)} 条新闻，丢弃 {invalid_count} 条")
            
            return scored_items
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析错误: {e}")
            logger.error(f"文件内容前 200 字符: {content[:200]}")
            return []
        except UnicodeDecodeError as e:
            logger.error(f"UTF-8 解码错误: {e}")
            return []
        except Exception as e:
            logger.error(f"加载评分结果时出错: {e}")
            return []
    
    def get_scored_news(self, run_scoring: bool = True) -> List[NewsScoredItem]:
        """
        获取评分后的新闻（完整流程）
        
        Args:
            run_scoring: 是否执行评分流程（False 表示直接读取已有结果）
        
        Returns:
            List[NewsScoredItem]: 评分后的新闻列表
        """
        if run_scoring:
            success = self.run_newscore()
            if not success:
                logger.warning("NewsScore 执行失败，尝试读取已有结果...")
        
        return self.load_scored_results()


# 真实新闻获取和评分（基于 RSS + AI）
def fetch_and_score_real_news(hours: int = 24, max_stories: int = 50) -> List[NewsScoredItem]:
    """
    获取真实新闻并进行 AI 评分
    
    Args:
        hours: 获取最近 N 小时的新闻
        max_stories: 最多获取 N 条新闻
    
    Returns:
        List[NewsScoredItem]: 评分后的真实新闻列表
    """
    from rss_fetcher import RSSFetcher
    from news_scorer import NewsScorer
    
    logger.info(f"开始获取真实新闻（最近 {hours} 小时）")
    
    try:
        # 1. 抓取新闻
        fetcher = RSSFetcher()
        articles = fetcher.fetch_all(hours=hours, max_per_source=10)
        
        if not articles:
            logger.warning("未抓取到任何新闻")
            return []
        
        logger.info(f"抓取到 {len(articles)} 条新闻")
        
        # 2. AI 评分
        scorer = NewsScorer()
        scored_articles = scorer.score_batch(articles[:max_stories])
        
        # 3. 转换为 NewsScoredItem
        scored_items = [NewsScoredItem(article) for article in scored_articles]
        
        logger.info(f"评分完成，共 {len(scored_items)} 条新闻")
        
        return scored_items
        
    except Exception as e:
        logger.error(f"获取真实新闻失败: {e}")
        logger.exception(e)
        return []


# 模拟数据生成器（用于测试，无 NewsScore 时使用）
def generate_mock_scored_news() -> List[NewsScoredItem]:
    """
    生成模拟评分数据（仅用于开发测试）
    
    Returns:
        List[NewsScoredItem]: 模拟新闻列表
    """
    logger.warning("使用模拟数据模式（仅供测试）")
    
    mock_data = [
        {
            "title": "Major Climate Summit Reaches Historic Agreement",
            "url": "https://example.com/climate-summit",
            "source": "Reuters",
            "published_at": "2025-11-11T07:52:00",
            "snippet": "World leaders agree on ambitious carbon reduction targets...",
            "score": 0.92
        },
        {
            "title": "Tech Giant Announces Revolutionary AI Chip",
            "url": "https://example.com/ai-chip",
            "source": "Bloomberg",
            "published_at": "2025-11-11T06:30:00",
            "snippet": "New chip promises 10x performance improvement...",
            "score": 0.89
        },
        {
            "title": "Breaking: Global Markets Rally on Economic Data",
            "url": "https://example.com/markets",
            "source": "Financial Times",
            "published_at": "2025-11-11T05:15:00",
            "snippet": "Stocks surge as inflation data beats expectations...",
            "score": 0.85
        },
    ]
    
    return [NewsScoredItem(item) for item in mock_data]

