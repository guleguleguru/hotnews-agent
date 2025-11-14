"""
AI 新闻评分器
基于 NewsScore 的评分逻辑和标准
"""

import json
import re
from typing import Dict, Any, List
from openai import OpenAI
from loguru import logger
from config import config


class NewsScorer:
    """
    AI 新闻评分器
    完全基于 NewsScore 的评分标准和提示词
    """
    
    # NewsScore 的评分提示词（完全参考原项目）
    SCORE_PROMPT_TEMPLATE = """
You are News Rank AI, an advanced artificial intelligence system designed to evaluate and score news articles based on their quality and importance. Assign a score ranging from 0.0 (low quality) to 10.0 (high quality) to each article.

INSTRUCTIONS:
- Assess the quality of the news article by examining its content.
- High-quality articles are engaging, significant, and relevant, with long-term importance.
- Focus on surfacing news related to economics, technology, and business.
- We're generally not interested in celebrity gossip, excessive war, politics, sports, environment or other low-quality content unless it's one of the biggest stories of the year.
- Be strict in your evaluation, assigning lower scores unless an article is truly exceptional.
- Only give a score above 7 if the article is still impactful and relevant after one year.
- Less than 5% of articles should receive a score higher than 7.
- Determine the credibility of the article by considering the author, publication, and URL. Favor sources with a history of limited clickbait content.
- Lower the score for articles that lack sufficient content.
- Evaluate articles from the perspective of an early adopter, tech-savvy audience similar to Hacker News and Techmeme readers.
- Provide only a numerical score between 0.0 and 10.0, without returning a JSON object or any other text.

EXAMPLES:
"I was shot nine times in the Christchurch massacre – now I'm reclaiming the gunman's journey" -> 3.5
"How 2 Students Rescued Dozens of People from the Fighting in Sudan" -> 5.9
"The best Wi-Fi routers in 2022" -> 0.1
"Tequila is About to Become the U.S.'s Most Popular Spirit. That's Bad for the Environment" -> 2.0
"What is profit and loss (PnL) and how to calculate it" -> 2.0
"OpenAI announces ChatGPT successor GPT-4" -> 9.9
"He wrote a book on a rare subject. Then a ChatGPT replica appeared on Amazon." -> 6.3

ARTICLE DETAILS:
{article_json}

The calculated score for the article above is:
""".strip()
    
    def __init__(self):
        """初始化评分器"""
        self.client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL
        )
        self.model = config.OPENAI_MODEL
        logger.info(f"AI 评分器初始化，使用模型: {self.model}")
    
    def score_article(self, article: Dict[str, Any]) -> float:
        """
        对单篇新闻评分
        
        Args:
            article: 新闻数据字典，包含 title, url, source, snippet 等
        
        Returns:
            float: 评分 (0.0-1.0)，基于 NewsScore 的 0-10 分制转换
        """
        try:
            # 构建提示词
            article_json = json.dumps({
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "source": article.get("source", ""),
                "snippet": article.get("snippet", "")[:500],  # 限制长度
                "category": article.get("category", "general"),
            }, indent=2, ensure_ascii=False)
            
            prompt = self.SCORE_PROMPT_TEMPLATE.format(article_json=article_json)
            
            # 调用 LLM（含超时和重试）
            score = self._call_llm_with_retry(prompt)
            
            logger.debug(f"评分完成: {article.get('title', '')[:50]}... -> {score:.2f}")
            
            return score
            
        except Exception as e:
            logger.error(f"评分失败: {e}，返回默认分数 0.5")
            return 0.5
    
    def score_batch(self, articles: List[Dict[str, Any]], batch_size: int = 5) -> List[Dict[str, Any]]:
        """
        批量评分（含进度显示）
        
        Args:
            articles: 新闻列表
            batch_size: 每批次数量（用于日志显示）
        
        Returns:
            List[Dict]: 评分后的新闻列表（添加 score 字段）
        """
        logger.info(f"开始批量评分 {len(articles)} 条新闻...")
        
        for i, article in enumerate(articles, 1):
            try:
                # 评分
                score = self.score_article(article)
                article["score"] = score
                
                # 进度日志
                if i % batch_size == 0 or i == len(articles):
                    logger.info(f"评分进度: {i}/{len(articles)}")
                
            except Exception as e:
                logger.error(f"评分单篇新闻失败 (索引 {i}): {e}")
                article["score"] = 0.5  # 默认中等分数
        
        logger.info("批量评分完成")
        return articles
    
    def _call_llm_with_retry(self, prompt: str, max_retries: int = 2) -> float:
        """
        调用 LLM 并解析评分（含重试）
        
        Args:
            prompt: 提示词
            max_retries: 最大重试次数
        
        Returns:
            float: 评分 (0.0-1.0)
        """
        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are News Rank AI, a precise news scoring system. Return only a numerical score."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.3,
                    max_tokens=10,  # 只需要一个数字
                    timeout=config.MODEL_TIMEOUT
                )
                
                raw_score = response.choices[0].message.content.strip()
                
                # 🔍 调试：记录原始返回值
                logger.debug(f"LLM 原始返回: '{raw_score}'")
                
                # 解析评分
                score = self._parse_score(raw_score)
                logger.debug(f"解析后分数: {score:.4f} (原始 10分制: {score*10:.2f})")
                
                # 验证范围
                if 0.0 <= score <= 1.0:
                    return score
                else:
                    logger.warning(f"评分超出范围: {score}，尝试修正")
                    return max(0.0, min(1.0, score))
                
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"LLM 调用失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                else:
                    logger.error(f"LLM 调用失败，已达最大重试次数: {e}")
                    raise
        
        return 0.5  # 兜底分数
    
    def _parse_score(self, raw_text: str) -> float:
        """
        解析 LLM 返回的评分
        
        Args:
            raw_text: LLM 返回的原始文本
        
        Returns:
            float: 评分 (0.0-1.0)
        
        Raises:
            ValueError: 无法解析评分
        """
        try:
            # 方法 1: 直接解析数字
            # 提取所有数字（包括小数点）
            numbers = re.findall(r'\d+\.?\d*', raw_text)
            
            if numbers:
                # 取第一个数字
                score_10 = float(numbers[0])
                
                # NewsScore 使用 0-10 分制，我们转换为 0-1
                # 例如: 8.5 -> 0.85
                if score_10 > 10:
                    # 可能是 0-100 或 0-1000，归一化
                    if score_10 > 100:
                        score_10 = score_10 / 1000
                    else:
                        score_10 = score_10 / 100
                else:
                    score_10 = score_10 / 10
                
                return score_10
            
            # 方法 2: 尝试解析 JSON
            try:
                data = json.loads(raw_text)
                if isinstance(data, dict) and "score" in data:
                    return float(data["score"]) / 10
            except:
                pass
            
            # 无法解析
            raise ValueError(f"无法从文本中解析评分: {raw_text}")
            
        except Exception as e:
            logger.warning(f"评分解析失败: {e}，原文: {raw_text}")
            raise


