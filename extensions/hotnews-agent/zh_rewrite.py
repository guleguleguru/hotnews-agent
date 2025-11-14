"""
中文标题改写模块
使用 LLM 对英文标题进行客观、简洁的中文改写
"""

import re
from typing import List
from openai import OpenAI
from loguru import logger
from config import config
from newscore_adapter import NewsScoredItem


class ChineseTitleRewriter:
    """中文标题改写器"""
    
    def __init__(self):
        """初始化 OpenAI 客户端"""
        self.client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL
        )
        self.model = config.OPENAI_MODEL
    
    def rewrite_title(self, title: str, source: str = "", snippet: str = "") -> str:
        """
        改写单个标题为中文（含容错）
        
        Args:
            title: 英文标题
            source: 新闻来源
            snippet: 新闻摘要片段（可选，提供更多上下文）
        
        Returns:
            str: 中文标题（失败时返回原标题）
        """
        # 空值检查
        if not title or not title.strip():
            logger.warning("标题为空，跳过改写")
            return "[无标题]"
        
        try:
            # 构建提示词
            prompt = self._build_rewrite_prompt(title, source, snippet)
            
            # 调用 LLM（含超时）
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的新闻编辑，擅长将英文新闻标题改写成简洁、客观、准确的中文标题。"
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
            
            zh_title = response.choices[0].message.content.strip()
            
            # 移除可能的引号和多余标点
            zh_title = zh_title.strip('"').strip("'").strip("「」").strip("《》")
            
            # 检查长度
            if len(zh_title) > 40:
                logger.warning(f"标题过长 ({len(zh_title)} 字)，截断")
                zh_title = zh_title[:40]
            
            # 检查重复标点
            zh_title = re.sub(r'[。！？]{2,}', '。', zh_title)
            zh_title = re.sub(r'[，、]{2,}', '，', zh_title)
            
            # 如果改写结果异常（如全英文、过短），回退原标题
            if len(zh_title) < 5 or not any('\u4e00' <= char <= '\u9fff' for char in zh_title):
                logger.warning(f"改写结果异常: {zh_title}，回退原标题")
                return title[:40]
            
            logger.debug(f"标题改写: {title[:30]}... -> {zh_title}")
            
            return zh_title
            
        except TimeoutError:
            logger.error(f"标题改写超时 ({config.MODEL_TIMEOUT}s)，回退原标题")
            return title[:40]
        except Exception as e:
            logger.error(f"标题改写失败: {e}，回退原标题")
            return title[:40]
    
    def rewrite_batch(self, items: List[NewsScoredItem]) -> List[NewsScoredItem]:
        """
        批量改写标题
        
        Args:
            items: 新闻项列表
        
        Returns:
            List[NewsScoredItem]: 改写后的新闻项列表
        """
        logger.info(f"开始批量改写 {len(items)} 个标题...")
        
        for i, item in enumerate(items, 1):
            logger.info(f"改写进度: {i}/{len(items)}")
            item.title_zh = self.rewrite_title(
                title=item.title,
                source=item.source,
                snippet=item.snippet
            )
        
        logger.info("标题改写完成")
        return items
    
    def _build_rewrite_prompt(self, title: str, source: str = "", snippet: str = "") -> str:
        """
        构建改写提示词（优化版）
        
        Args:
            title: 英文标题
            source: 新闻来源
            snippet: 摘要片段
        
        Returns:
            str: 提示词
        """
        prompt = f"""请将以下新闻标题改写为客观、简洁的中文，避免夸张或评价性词汇，控制在15–30字：

「{title}」

仅输出改写后的标题。"""
        
        if snippet:
            prompt = f"""请根据以下信息改写为客观、简洁的中文标题（15–30字）：

标题：{title}
片段：{snippet[:100]}...

仅输出改写后的标题。"""
        
        return prompt

