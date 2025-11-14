"""
全文抓取模块
从 URL 抓取 HTML，提取正文前几段用于高质量摘要生成
"""

import re
import time
from typing import Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from loguru import logger
from config import config


class FullTextExtractor:
    """全文提取器"""
    
    # 用户代理（模拟浏览器）
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    # 请求超时（秒）
    REQUEST_TIMEOUT = 15
    
    def __init__(self):
        """初始化提取器"""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
    
    def extract(self, url: str, max_paragraphs: int = 3) -> Optional[str]:
        """
        从 URL 提取正文前几段
        
        Args:
            url: 新闻 URL
            max_paragraphs: 最多提取段落数（默认3段）
        
        Returns:
            Optional[str]: 提取的正文文本（失败返回 None）
        """
        try:
            logger.info(f"开始抓取全文: {url}")
            
            # 1. 发送请求
            response = self.session.get(url, timeout=self.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # 2. 解析 HTML
            soup = BeautifulSoup(response.content, "html.parser")
            
            # 3. 移除脚本和样式
            for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                script.decompose()
            
            # 4. 尝试多种方法提取正文
            text = self._extract_main_content(soup)
            
            if not text:
                logger.warning(f"无法提取正文，尝试备用方法: {url}")
                text = self._extract_fallback(soup)
            
            if not text:
                logger.warning(f"全文提取失败: {url}")
                return None
            
            # 5. 清理和截取段落
            paragraphs = self._clean_and_split(text, max_paragraphs)
            
            if paragraphs:
                result = "\n\n".join(paragraphs)
                logger.info(f"成功提取 {len(paragraphs)} 段正文（共 {len(result)} 字符）")
                return result
            else:
                logger.warning(f"提取的正文为空: {url}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"请求超时: {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败: {url}, 错误: {e}")
            return None
        except Exception as e:
            logger.error(f"全文提取异常: {url}, 错误: {e}")
            logger.exception(e)
            return None
    
    def _extract_main_content(self, soup: BeautifulSoup) -> Optional[str]:
        """
        提取主要内容（优先方法）
        
        尝试常见的正文容器标签：
        - article
        - main
        - [role="main"]
        - .content, .article-content, .post-content
        """
        # 方法1: article 标签
        article = soup.find("article")
        if article:
            text = article.get_text(separator=" ", strip=True)
            if len(text) > 200:  # 确保有足够内容
                return text
        
        # 方法2: main 标签
        main = soup.find("main")
        if main:
            text = main.get_text(separator=" ", strip=True)
            if len(text) > 200:
                return text
        
        # 方法3: role="main"
        main_role = soup.find(attrs={"role": "main"})
        if main_role:
            text = main_role.get_text(separator=" ", strip=True)
            if len(text) > 200:
                return text
        
        # 方法4: 常见内容类名
        content_classes = [
            "content", "article-content", "post-content", "entry-content",
            "article-body", "post-body", "story-body", "article-text"
        ]
        for class_name in content_classes:
            content = soup.find(class_=re.compile(class_name, re.I))
            if content:
                text = content.get_text(separator=" ", strip=True)
                if len(text) > 200:
                    return text
        
        return None
    
    def _extract_fallback(self, soup: BeautifulSoup) -> Optional[str]:
        """
        备用提取方法（提取所有段落）
        """
        # 提取所有 <p> 标签
        paragraphs = soup.find_all("p")
        if not paragraphs:
            return None
        
        # 合并段落文本
        texts = []
        for p in paragraphs:
            text = p.get_text(strip=True)
            if text and len(text) > 50:  # 过滤太短的段落
                texts.append(text)
        
        if texts:
            return " ".join(texts)
        
        return None
    
    def _clean_and_split(self, text: str, max_paragraphs: int) -> list[str]:
        """
        清理文本并分割为段落
        
        Args:
            text: 原始文本
            max_paragraphs: 最多段落数
        
        Returns:
            list[str]: 清理后的段落列表
        """
        # 清理多余空白
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # 按句号、问号、感叹号分割（简单方法）
        sentences = re.split(r'[.!?]\s+', text)
        
        # 合并句子为段落（每段约150-300字符）
        paragraphs = []
        current_para = []
        current_length = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_length = len(sentence)
            
            # 如果当前段落已有足够内容，或达到最大段落数，开始新段落
            if (current_length > 200 and current_para) or len(paragraphs) >= max_paragraphs:
                if current_para:
                    paragraphs.append(" ".join(current_para))
                    current_para = []
                    current_length = 0
                
                if len(paragraphs) >= max_paragraphs:
                    break
            
            current_para.append(sentence)
            current_length += sentence_length
        
        # 添加最后一段
        if current_para and len(paragraphs) < max_paragraphs:
            paragraphs.append(" ".join(current_para))
        
        return paragraphs[:max_paragraphs]
    
    def extract_batch(self, urls: list[str], max_paragraphs: int = 3, delay: float = 1.0) -> dict[str, Optional[str]]:
        """
        批量提取全文（含延迟，避免被封）
        
        Args:
            urls: URL 列表
            max_paragraphs: 每篇最多段落数
            delay: 请求间隔（秒）
        
        Returns:
            dict[str, Optional[str]]: URL -> 正文文本的映射
        """
        results = {}
        
        for i, url in enumerate(urls, 1):
            logger.info(f"全文提取进度: {i}/{len(urls)}")
            results[url] = self.extract(url, max_paragraphs)
            
            # 延迟（最后一条不需要延迟）
            if i < len(urls):
                time.sleep(delay)
        
        success_count = sum(1 for v in results.values() if v)
        logger.info(f"批量提取完成: {success_count}/{len(urls)} 成功")
        
        return results

