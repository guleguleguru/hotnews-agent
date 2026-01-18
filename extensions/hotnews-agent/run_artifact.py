"""
运行 Artifact 保存模块
每天保存完整的运行数据，用于可回测和可观测性
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from loguru import logger
from newscore_adapter import NewsScoredItem


class RunArtifact:
    """运行 Artifact 管理器"""
    
    def __init__(self, base_dir: str = "./history/runs"):
        """
        初始化
        
        Args:
            base_dir: 保存目录
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def save_run(
        self,
        date: str,
        raw_articles: List[Dict[str, Any]],
        scored_items: List[NewsScoredItem],
        filtered_items: List[NewsScoredItem],
        deduped_items: List[NewsScoredItem],
        final_items: List[NewsScoredItem],
        threshold_history: List[Dict[str, Any]],
        stats: Dict[str, Any]
    ):
        """
        保存完整运行数据
        
        Args:
            date: 日期字符串 (YYYY-MM-DD)
            raw_articles: 原始抓取的新闻
            scored_items: 评分后的新闻
            filtered_items: 过滤后的新闻
            deduped_items: 去重后的新闻
            final_items: 最终发送的新闻
            threshold_history: 动态阈值调整历史
            stats: 统计信息
        """
        artifact = {
            "date": date,
            "timestamp": datetime.now().isoformat(),
            "raw_articles": [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source": item.get("source", ""),
                    "snippet": item.get("snippet", "")[:500],
                    "published_time": item.get("published_time", ""),
                }
                for item in raw_articles
            ],
            "scored_items": [
                {
                    "title": item.title,
                    "url": item.url,
                    "source": item.source,
                    "snippet": item.snippet[:500] if item.snippet else "",
                    "published_time": item.published_time,
                    "score": item.score,
                    "structured_data": getattr(item, "structured_data", {})
                }
                for item in scored_items
            ],
            "filtered_items": [
                {
                    "title": item.title,
                    "url": item.url,
                    "source": item.source,
                    "score": item.score,
                }
                for item in filtered_items
            ],
            "deduped_items": [
                {
                    "title": item.title,
                    "url": item.url,
                    "source": item.source,
                    "score": item.score,
                }
                for item in deduped_items
            ],
            "final_items": [
                {
                    "title": item.title,
                    "url": item.url,
                    "source": item.source,
                    "score": item.score,
                    "title_zh": item.title_zh,
                    "summary_zh": item.summary_zh[:500] if item.summary_zh else "",
                }
                for item in final_items
            ],
            "threshold_history": threshold_history,
            "stats": stats
        }
        
        # 保存到文件
        file_path = self.base_dir / f"{date}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(artifact, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ 运行 Artifact 已保存: {file_path}")
        except Exception as e:
            logger.error(f"保存运行 Artifact 失败: {e}")
    
    def load_run(self, date: str) -> Dict[str, Any]:
        """
        加载历史运行数据
        
        Args:
            date: 日期字符串 (YYYY-MM-DD)
        
        Returns:
            Dict: 运行数据
        """
        file_path = self.base_dir / f"{date}.json"
        try:
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                logger.warning(f"运行 Artifact 不存在: {file_path}")
                return {}
        except Exception as e:
            logger.error(f"加载运行 Artifact 失败: {e}")
            return {}



