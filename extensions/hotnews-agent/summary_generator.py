"""
摘要生成模块（支持中英文）
生成简洁的事实摘要，支持中文和英文两种语言
"""

import re
from typing import List
from openai import OpenAI
from loguru import logger
from config import config
from newscore_adapter import NewsScoredItem


class SummaryGenerator:
    """摘要生成器（支持中英文）"""
    
    def __init__(self, language: str = None):
        """
        初始化摘要生成器
        
        Args:
            language: 目标语言 ("zh" 或 "en")，默认使用配置中的语言
        """
        self.client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL
        )
        self.model = config.OPENAI_MODEL
        self.language = language or config.LANGUAGE
    
    def generate_summary(
        self,
        title: str,
        title_translated: str = "",
        snippet: str = "",
        full_text: str = "",
        target_length: int = None,
        max_length: int = None
    ) -> str:
        """
        生成单个新闻的摘要（含容错，灵活长度控制）
        
        Args:
            title: 原始标题
            title_translated: 翻译后的标题（可选）
            snippet: 新闻片段（RSS 摘要）
            full_text: 全文内容（可选，用于高质量摘要）
            target_length: 目标长度（建议值，LLM 会尽量接近）
            max_length: 最大长度（硬上限，超过会截断）
        
        Returns:
            str: 摘要（失败时返回简化版）
        """
        # 使用配置中的默认值
        if target_length is None:
            target_length = config.SUMMARY_TARGET_LENGTH
        if max_length is None:
            max_length = config.SUMMARY_MAX_LENGTH
        
        # 空值检查
        if not title and not title_translated:
            logger.warning("标题为空，无法生成摘要")
            return "No summary available" if self.language == "en" else "暂无摘要"
        
        try:
            # 构建提示词（优先使用全文）
            prompt = self._build_summary_prompt(
                title, title_translated, snippet, full_text, target_length, max_length
            )
            
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
                temperature=0.3,
                max_tokens=200,
                timeout=config.MODEL_TIMEOUT
            )
            
            summary = response.choices[0].message.content.strip()
            
            # 清理格式
            summary = summary.strip('"').strip("'").strip("「」").strip("《》")
            
            # 检查重复标点
            if self.language == "zh":
                summary = re.sub(r'[。！？]{2,}', '。', summary)
                summary = re.sub(r'[，、]{2,}', '，', summary)
            else:
                summary = re.sub(r'[.!?]{2,}', '.', summary)
                summary = re.sub(r'[,]{2,}', ',', summary)
            
            # 只在超过硬上限时才截断（保留完整性）
            if len(summary) > max_length:
                logger.warning(f"摘要过长 ({len(summary)} 字符，超过硬上限 {max_length} 字符)，截断")
                # 尝试在句号、问号、感叹号处截断，避免截断句子
                truncated = summary[:max_length]
                if self.language == "zh":
                    last_punctuation = max(
                        truncated.rfind('。'),
                        truncated.rfind('！'),
                        truncated.rfind('？'),
                        truncated.rfind('，')
                    )
                else:
                    last_punctuation = max(
                        truncated.rfind('.'),
                        truncated.rfind('!'),
                        truncated.rfind('?'),
                        truncated.rfind(',')
                    )
                if last_punctuation > max_length * 0.7:  # 如果标点位置合理（超过70%位置）
                    summary = truncated[:last_punctuation + 1]
                else:
                    summary = truncated
            
            # 如果摘要异常（过短或无对应语言字符），回退
            if self.language == "zh":
                if len(summary) < 5 or not any('\u4e00' <= char <= '\u9fff' for char in summary):
                    logger.warning(f"摘要异常: {summary}，使用标题作为摘要")
                    fallback = title_translated or title
                    if len(fallback) > max_length:
                        return fallback[:max_length]
                    return fallback
            else:
                if len(summary) < 5:
                    logger.warning(f"摘要异常: {summary}，使用标题作为摘要")
                    fallback = title_translated or title
                    if len(fallback) > max_length:
                        return fallback[:max_length]
                    return fallback
            
            logger.debug(f"摘要生成: {(title_translated or title)[:20]}... -> {summary}")
            
            return summary
            
        except TimeoutError:
            logger.error(f"摘要生成超时 ({config.MODEL_TIMEOUT}s)，使用标题作为摘要")
            fallback = title_translated or title
            if len(fallback) > max_length:
                return fallback[:max_length]
            return fallback
        except Exception as e:
            logger.error(f"摘要生成失败: {e}，使用标题作为摘要")
            fallback = title_translated or title
            if len(fallback) > max_length:
                return fallback[:max_length]
            return fallback
    
    def generate_batch(self, items: List[NewsScoredItem]) -> List[NewsScoredItem]:
        """
        批量生成摘要
        
        Args:
            items: 新闻项列表（应已包含翻译后的标题）
        
        Returns:
            List[NewsScoredItem]: 生成摘要后的新闻项列表
        """
        logger.info(f"开始批量生成 {len(items)} 个摘要（语言: {self.language}）...")
        
        for i, item in enumerate(items, 1):
            logger.info(f"生成进度: {i}/{len(items)}")
            title_translated = item.title_zh if self.language == "zh" else getattr(item, 'title_en', item.title)
            
            summary = self.generate_summary(
                title=item.title,
                title_translated=title_translated,
                snippet=item.snippet,
                full_text=getattr(item, 'full_text', '')
            )
            
            if self.language == "zh":
                item.summary_zh = summary
            else:
                item.summary_en = summary
        
        logger.info("摘要生成完成")
        return items
    
    def _get_system_message(self) -> str:
        """获取系统消息"""
        if self.language == "zh":
            return "你是一个专业的新闻编辑，擅长提炼新闻核心事实，生成简洁精准的摘要。"
        else:
            return "You are a professional news editor, skilled at extracting core facts from news and generating concise, accurate summaries."
    
    def _build_summary_prompt(
        self,
        title: str,
        title_translated: str = "",
        snippet: str = "",
        full_text: str = "",
        target_length: int = 60,
        max_length: int = 100
    ) -> str:
        """
        构建摘要提示词（优化版，支持全文，灵活长度控制）
        
        Args:
            title: 原始标题
            title_translated: 翻译后的标题
            snippet: RSS 摘要片段
            full_text: 全文内容（优先使用）
            target_length: 目标长度（建议值）
            max_length: 最大长度（硬上限）
        
        Returns:
            str: 提示词
        """
        base_title = title_translated or title
        
        if self.language == "zh":
            # 优先使用全文（更高质量）
            if full_text:
                text_preview = full_text[:800] if len(full_text) > 800 else full_text
                prompt = f"""基于以下新闻全文，用中文总结核心事实，不包含主观观点或营销语。

标题：{base_title}

正文：
{text_preview}

要求：
- 摘要长度建议控制在 {target_length} 字左右，但可以根据内容需要适当调整
- 如果内容重要且需要更多字数才能说清楚，可以适当延长，但不要超过 {max_length} 字
- 聚焦核心事实，客观准确，避免冗余和重复
- 确保摘要完整，不要截断句子"""
            elif snippet:
                prompt = f"""用中文总结该新闻的核心事实，不包含主观观点或营销语。

标题：{base_title}
片段：{snippet[:200]}...

要求：
- 摘要长度建议控制在 {target_length} 字左右，但可以根据内容需要适当调整
- 如果内容重要且需要更多字数才能说清楚，可以适当延长，但不要超过 {max_length} 字
- 确保摘要完整，不要截断句子"""
            else:
                prompt = f"""用中文总结该新闻的核心事实：

{base_title}

要求：
- 摘要长度建议控制在 {target_length} 字左右，但可以根据内容需要适当调整
- 如果内容重要且需要更多字数才能说清楚，可以适当延长，但不要超过 {max_length} 字
- 确保摘要完整，不要截断句子"""
        else:
            # 英文模式
            if full_text:
                text_preview = full_text[:800] if len(full_text) > 800 else full_text
                prompt = f"""Summarize the core facts of the following news article in English, without subjective opinions or marketing language.

Title: {base_title}

Content:
{text_preview}

Requirements:
- Summary length should be around {target_length} words, but can be adjusted based on content needs
- If the content is important and requires more words to explain clearly, you can extend it, but do not exceed {max_length} words
- Focus on core facts, be objective and accurate, avoid redundancy and repetition
- Ensure the summary is complete, do not truncate sentences"""
            elif snippet:
                prompt = f"""Summarize the core facts of this news in English, without subjective opinions or marketing language.

Title: {base_title}
Snippet: {snippet[:200]}...

Requirements:
- Summary length should be around {target_length} words, but can be adjusted based on content needs
- If the content is important and requires more words to explain clearly, you can extend it, but do not exceed {max_length} words
- Ensure the summary is complete, do not truncate sentences"""
            else:
                prompt = f"""Summarize the core facts of this news in English:

{base_title}

Requirements:
- Summary length should be around {target_length} words, but can be adjusted based on content needs
- If the content is important and requires more words to explain clearly, you can extend it, but do not exceed {max_length} words
- Ensure the summary is complete, do not truncate sentences"""
        
        return prompt


