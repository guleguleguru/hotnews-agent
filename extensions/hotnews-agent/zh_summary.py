"""
中文摘要生成模块
生成简洁的中文事实摘要（灵活长度控制）
"""

import re
from typing import List
from openai import OpenAI
from loguru import logger
from config import config
from newscore_adapter import NewsScoredItem


class ChineseSummaryGenerator:
    """中文摘要生成器"""
    
    def __init__(self):
        """初始化 OpenAI 客户端"""
        self.client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL
        )
        self.model = config.OPENAI_MODEL
    
    def generate_summary(
        self,
        title: str,
        title_zh: str = "",
        snippet: str = "",
        full_text: str = "",
        target_length: int = None,
        max_length: int = None
    ) -> str:
        """
        生成单个新闻的中文摘要（含容错，灵活长度控制）
        
        Args:
            title: 英文标题
            title_zh: 中文标题（可选）
            snippet: 新闻片段（RSS 摘要）
            full_text: 全文内容（可选，用于高质量摘要）
            target_length: 目标长度（建议值，LLM 会尽量接近）
            max_length: 最大长度（硬上限，超过会截断）
        
        Returns:
            str: 中文摘要（失败时返回简化版）
        """
        # 使用配置中的默认值
        if target_length is None:
            target_length = config.SUMMARY_TARGET_LENGTH
        if max_length is None:
            max_length = config.SUMMARY_MAX_LENGTH
        # 空值检查
        if not title and not title_zh:
            logger.warning("标题为空，无法生成摘要")
            return "暂无摘要"
        
        try:
            # 构建提示词（优先使用全文）
            prompt = self._build_summary_prompt(title, title_zh, snippet, full_text, target_length, max_length)
            
            # 调用 LLM（含超时）
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的新闻编辑，擅长提炼新闻核心事实，生成简洁精准的摘要。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=200,  # 增加 token 限制，支持更长的摘要
                timeout=config.MODEL_TIMEOUT
            )
            
            summary = response.choices[0].message.content.strip()
            
            # 清理格式
            summary = summary.strip('"').strip("'").strip("「」").strip("《》")
            
            # 检查重复标点
            summary = re.sub(r'[。！？]{2,}', '。', summary)
            summary = re.sub(r'[，、]{2,}', '，', summary)
            
            # 只在超过硬上限时才截断（保留完整性）
            if len(summary) > max_length:
                logger.warning(f"摘要过长 ({len(summary)} 字，超过硬上限 {max_length} 字)，截断")
                # 尝试在句号、问号、感叹号处截断，避免截断句子
                truncated = summary[:max_length]
                last_punctuation = max(
                    truncated.rfind('。'),
                    truncated.rfind('！'),
                    truncated.rfind('？'),
                    truncated.rfind('，')
                )
                if last_punctuation > max_length * 0.7:  # 如果标点位置合理（超过70%位置）
                    summary = truncated[:last_punctuation + 1]
                else:
                    summary = truncated
            
            # 如果摘要异常（过短或无中文），回退
            if len(summary) < 5 or not any('\u4e00' <= char <= '\u9fff' for char in summary):
                logger.warning(f"摘要异常: {summary}，使用标题作为摘要")
                fallback = title_zh or title
                # 标题也只在超过硬上限时才截断
                if len(fallback) > max_length:
                    return fallback[:max_length]
                return fallback
            
            logger.debug(f"摘要生成: {(title_zh or title)[:20]}... -> {summary}")
            
            return summary
            
        except TimeoutError:
            logger.error(f"摘要生成超时 ({config.MODEL_TIMEOUT}s)，使用标题作为摘要")
            fallback = title_zh or title
            if len(fallback) > max_length:
                return fallback[:max_length]
            return fallback
        except Exception as e:
            logger.error(f"摘要生成失败: {e}，使用标题作为摘要")
            fallback = title_zh or title
            if len(fallback) > max_length:
                return fallback[:max_length]
            return fallback
    
    def generate_batch(self, items: List[NewsScoredItem]) -> List[NewsScoredItem]:
        """
        批量生成摘要
        
        Args:
            items: 新闻项列表（应已包含 title_zh）
        
        Returns:
            List[NewsScoredItem]: 生成摘要后的新闻项列表
        """
        logger.info(f"开始批量生成 {len(items)} 个摘要...")
        
        for i, item in enumerate(items, 1):
            logger.info(f"生成进度: {i}/{len(items)}")
            item.summary_zh = self.generate_summary(
                title=item.title,
                title_zh=item.title_zh,
                snippet=item.snippet,
                full_text=getattr(item, 'full_text', '')  # 支持全文摘要
            )
        
        logger.info("摘要生成完成")
        return items
    
    def _build_summary_prompt(
        self,
        title: str,
        title_zh: str = "",
        snippet: str = "",
        full_text: str = "",
        target_length: int = 60,
        max_length: int = 100
    ) -> str:
        """
        构建摘要提示词（优化版，支持全文，灵活长度控制）
        
        Args:
            title: 英文标题
            title_zh: 中文标题
            snippet: RSS 摘要片段
            full_text: 全文内容（优先使用）
            target_length: 目标长度（建议值）
            max_length: 最大长度（硬上限）
        
        Returns:
            str: 提示词
        """
        base_title = title_zh or title
        
        # 优先使用全文（更高质量）
        if full_text:
            # 限制全文长度（避免 token 过多）
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
        
        return prompt

