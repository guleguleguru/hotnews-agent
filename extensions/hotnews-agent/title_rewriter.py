"""
标题改写模块（支持中英文）
使用 LLM 对标题进行改写，支持中文和英文两种语言
"""

import re
from typing import List
from openai import OpenAI
from loguru import logger
from config import config
from newscore_adapter import NewsScoredItem


class TitleRewriter:
    """标题改写器（支持中英文）"""
    
    def __init__(self, language: str = None):
        """
        初始化标题改写器
        
        Args:
            language: 目标语言 ("zh" 或 "en")，默认使用配置中的语言
        """
        self.client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL
        )
        self.model = config.OPENAI_MODEL
        self.language = language or config.LANGUAGE
    
    def rewrite_title(self, title: str, source: str = "", snippet: str = "") -> str:
        """
        改写单个标题（含容错）
        
        Args:
            title: 原始标题
            source: 新闻来源
            snippet: 新闻摘要片段（可选，提供更多上下文）
        
        Returns:
            str: 改写后的标题（失败时返回原标题）
        """
        # 空值检查
        if not title or not title.strip():
            logger.warning("标题为空，跳过改写")
            return "[No Title]" if self.language == "en" else "[无标题]"
        
        try:
            # 构建提示词
            prompt = self._build_rewrite_prompt(title, source, snippet)
            
            # 调用 LLM（含超时）
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_message()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # 降低随机性，保持客观
                max_tokens=100,
                timeout=config.MODEL_TIMEOUT
            )
            
            rewritten_title = response.choices[0].message.content.strip()
            
            # 移除可能的引号和多余标点
            rewritten_title = rewritten_title.strip('"').strip("'").strip("「」").strip("《》")
            
            # 检查长度
            max_length = 60 if self.language == "en" else 40
            if len(rewritten_title) > max_length:
                logger.warning(f"标题过长 ({len(rewritten_title)} 字符)，截断")
                rewritten_title = rewritten_title[:max_length]
            
            # 检查重复标点
            if self.language == "zh":
                rewritten_title = re.sub(r'[。！？]{2,}', '。', rewritten_title)
                rewritten_title = re.sub(r'[，、]{2,}', '，', rewritten_title)
            else:
                rewritten_title = re.sub(r'[.!?]{2,}', '.', rewritten_title)
                rewritten_title = re.sub(r'[,]{2,}', ',', rewritten_title)
            
            # 如果改写结果异常，回退原标题
            if self.language == "zh":
                if len(rewritten_title) < 5 or not any('\u4e00' <= char <= '\u9fff' for char in rewritten_title):
                    logger.warning(f"改写结果异常: {rewritten_title}，回退原标题")
                    return title[:max_length]
            else:
                if len(rewritten_title) < 5:
                    logger.warning(f"改写结果异常: {rewritten_title}，回退原标题")
                    return title[:max_length]
            
            logger.debug(f"标题改写: {title[:30]}... -> {rewritten_title}")
            
            return rewritten_title
            
        except TimeoutError:
            logger.error(f"标题改写超时 ({config.MODEL_TIMEOUT}s)，回退原标题")
            max_length = 60 if self.language == "en" else 40
            return title[:max_length]
        except Exception as e:
            logger.error(f"标题改写失败: {e}，回退原标题")
            max_length = 60 if self.language == "en" else 40
            return title[:max_length]
    
    def rewrite_batch(self, items: List[NewsScoredItem]) -> List[NewsScoredItem]:
        """
        批量改写标题
        
        Args:
            items: 新闻项列表
        
        Returns:
            List[NewsScoredItem]: 改写后的新闻项列表
        """
        logger.info(f"开始批量改写 {len(items)} 个标题（语言: {self.language}）...")
        
        for i, item in enumerate(items, 1):
            logger.info(f"改写进度: {i}/{len(items)}")
            if self.language == "zh":
                item.title_zh = self.rewrite_title(
                    title=item.title,
                    source=item.source,
                    snippet=item.snippet
                )
            else:
                # 英文模式：改写为更清晰的英文标题
                item.title_en = self.rewrite_title(
                    title=item.title,
                    source=item.source,
                    snippet=item.snippet
                )
        
        logger.info("标题改写完成")
        return items
    
    def _get_system_message(self) -> str:
        """获取系统消息"""
        if self.language == "zh":
            return "你是一个专业的新闻编辑，擅长将英文新闻标题改写成简洁、客观、准确的中文标题。"
        else:
            return "You are a professional news editor, skilled at rewriting news headlines to be clear, objective, and accurate in English."
    
    def _build_rewrite_prompt(self, title: str, source: str = "", snippet: str = "") -> str:
        """
        构建改写提示词
        
        Args:
            title: 原始标题
            source: 新闻来源
            snippet: 摘要片段
        
        Returns:
            str: 提示词
        """
        if self.language == "zh":
            prompt = f"""请将以下新闻标题改写为客观、简洁的中文，避免夸张或评价性词汇，控制在15–30字：

「{title}」

仅输出改写后的标题。"""
            
            if snippet:
                prompt = f"""请根据以下信息改写为客观、简洁的中文标题（15–30字）：

标题：{title}
片段：{snippet[:100]}...

仅输出改写后的标题。"""
        else:
            prompt = f"""Rewrite the following news headline to be clear, objective, and concise in English (15-40 words):

"{title}"

Output only the rewritten headline."""
            
            if snippet:
                prompt = f"""Rewrite the following news headline to be clear, objective, and concise in English (15-40 words):

Headline: {title}
Snippet: {snippet[:100]}...

Output only the rewritten headline."""
        
        return prompt

