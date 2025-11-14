"""
RSS 新闻抓取器
从多个新闻源获取最新新闻
"""

import feedparser
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger
import time


class RSSFetcher:
    """RSS 新闻抓取器"""
    
    # 默认新闻源（可通过配置覆盖）
    DEFAULT_SOURCES = [
        # 国际新闻
        {
            "name": "BBC News - World",
            "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
            "category": "world"
        },
        {
            "name": "Reuters - World News",
            "url": "https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best",
            "category": "world"
        },
        {
            "name": "The Guardian - World",
            "url": "https://www.theguardian.com/world/rss",
            "category": "world"
        },
        # 科技新闻
        {
            "name": "TechCrunch",
            "url": "https://techcrunch.com/feed/",
            "category": "tech"
        },
        {
            "name": "Hacker News",
            "url": "https://hnrss.org/frontpage",
            "category": "tech"
        },
        {
            "name": "Ars Technica",
            "url": "http://feeds.arstechnica.com/arstechnica/index",
            "category": "tech"
        },
        # 商业财经
        {
            "name": "Bloomberg",
            "url": "https://www.bloomberg.com/feed/podcast/bloomberg-news-now.xml",
            "category": "business"
        },
    ]
    
    def __init__(self, sources: Optional[List[Dict[str, str]]] = None):
        """
        初始化 RSS 抓取器
        
        Args:
            sources: 自定义新闻源列表，格式：[{"name": "...", "url": "...", "category": "..."}]
        """
        self.sources = sources if sources else self.DEFAULT_SOURCES
        logger.info(f"RSS 抓取器初始化，共 {len(self.sources)} 个新闻源")
    
    def fetch_from_source(self, source: Dict[str, str], hours: int = 24) -> List[Dict[str, Any]]:
        """
        从单个源抓取新闻
        
        Args:
            source: 新闻源配置
            hours: 获取最近 N 小时的新闻
        
        Returns:
            List[Dict]: 新闻列表
        """
        try:
            logger.debug(f"正在抓取: {source['name']}")
            
            # 解析 RSS
            feed = feedparser.parse(source['url'])
            
            if feed.bozo:
                logger.warning(f"RSS 解析警告 {source['name']}: {feed.bozo_exception}")
            
            # 计算时间阈值
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            stories = []
            for entry in feed.entries:
                try:
                    # 提取发布时间
                    published_time = self._parse_published_time(entry)
                    
                    # 过滤太旧的新闻
                    if published_time and published_time < cutoff_time:
                        continue
                    
                    # 构建新闻对象
                    story = {
                        "title": entry.get("title", "").strip(),
                        "url": entry.get("link", "").strip(),
                        "source": source["name"],
                        "category": source.get("category", "general"),
                        "published_at": published_time.isoformat() if published_time else datetime.now().isoformat(),
                        "snippet": self._extract_snippet(entry),
                        "id": self._generate_id(entry.get("link", "")),
                    }
                    
                    # 验证必需字段
                    if story["title"] and story["url"]:
                        stories.append(story)
                    
                except Exception as e:
                    logger.warning(f"解析单条新闻失败 ({source['name']}): {e}")
                    continue
            
            logger.info(f"从 {source['name']} 抓取 {len(stories)} 条新闻")
            return stories
            
        except Exception as e:
            logger.error(f"抓取 {source['name']} 失败: {e}")
            return []
    
    def fetch_all(self, hours: int = 24, max_per_source: int = 10) -> List[Dict[str, Any]]:
        """
        从所有源抓取新闻
        
        Args:
            hours: 获取最近 N 小时的新闻
            max_per_source: 每个源最多获取 N 条
        
        Returns:
            List[Dict]: 所有新闻列表
        """
        logger.info(f"开始从 {len(self.sources)} 个源抓取新闻（最近 {hours} 小时）")
        
        all_stories = []
        
        for source in self.sources:
            try:
                stories = self.fetch_from_source(source, hours)
                
                # 限制每个源的数量
                if len(stories) > max_per_source:
                    stories = stories[:max_per_source]
                
                all_stories.extend(stories)
                
                # 礼貌延迟，避免被封
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"处理源 {source['name']} 时出错: {e}")
                continue
        
        # 去重（基于 URL）
        unique_stories = self._deduplicate_by_url(all_stories)
        
        logger.info(f"抓取完成，共 {len(unique_stories)} 条不重复新闻")
        return unique_stories
    
    def _parse_published_time(self, entry: Any) -> Optional[datetime]:
        """
        解析发布时间
        
        Args:
            entry: RSS entry 对象
        
        Returns:
            datetime: 发布时间
        """
        # 尝试多个时间字段
        time_fields = ["published_parsed", "updated_parsed", "created_parsed"]
        
        for field in time_fields:
            if hasattr(entry, field):
                time_struct = getattr(entry, field)
                if time_struct:
                    try:
                        return datetime(*time_struct[:6])
                    except:
                        pass
        
        return None
    
    def _extract_snippet(self, entry: Any) -> str:
        """
        提取新闻摘要
        
        Args:
            entry: RSS entry 对象
        
        Returns:
            str: 摘要文本
        """
        # 尝试多个摘要字段
        for field in ["summary", "description", "content"]:
            if hasattr(entry, field):
                content = getattr(entry, field)
                
                if isinstance(content, list) and len(content) > 0:
                    content = content[0].get("value", "")
                
                if isinstance(content, str) and content:
                    # 简单清理 HTML 标签
                    import re
                    clean_text = re.sub(r'<[^>]+>', '', content)
                    # 限制长度
                    return clean_text[:500].strip()
        
        return ""
    
    def _generate_id(self, url: str) -> str:
        """
        生成新闻 ID（URL 哈希）
        
        Args:
            url: 新闻 URL
        
        Returns:
            str: ID
        """
        return hashlib.md5(url.encode("utf-8")).hexdigest()[:16]
    
    def _deduplicate_by_url(self, stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        基于 URL 去重
        
        Args:
            stories: 新闻列表
        
        Returns:
            List[Dict]: 去重后的新闻列表
        """
        seen_urls = set()
        unique = []
        
        for story in stories:
            url = story.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(story)
        
        return unique


