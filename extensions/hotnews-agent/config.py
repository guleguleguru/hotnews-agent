"""
配置管理模块
从环境变量读取所有配置项
"""

import os
from typing import Optional
from dotenv import load_dotenv
from loguru import logger

# 加载环境变量
load_dotenv()


class Config:
    """配置类，统一管理所有配置项"""
    
    # ========================================
    # NewsScore 原项目配置
    # ========================================
    NEWSSCORE_MODEL_API_KEY: str = os.getenv("NEWSSCORE_MODEL_API_KEY", "")
    NEWSSCORE_MODEL_NAME: str = os.getenv("NEWSSCORE_MODEL_NAME", "gpt-4")
    NEWSSCORE_DATA_SOURCES: str = os.getenv("NEWSSCORE_DATA_SOURCES", "")
    
    # ========================================
    # HotNews Agent 层配置
    # ========================================
    
    # LLM 配置（支持 OpenAI / DeepSeek / 其他兼容 API）
    # 使用 DeepSeek: OPENAI_BASE_URL=https://api.deepseek.com, OPENAI_MODEL=deepseek-chat
    # 使用 OpenAI: OPENAI_BASE_URL=https://api.openai.com/v1, OPENAI_MODEL=gpt-4-turbo-preview
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "deepseek-chat")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    
    # 邮件配置
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASS: str = os.getenv("SMTP_PASS", "")
    # 收件人邮箱（多个用逗号分隔，如：email1@qq.com,email2@163.com）
    MAIL_TO: str = os.getenv("MAIL_TO", "")
    MAIL_FROM: str = os.getenv("MAIL_FROM", "")
    
    # SendGrid 配置（可选）
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    
    # 时区和调度
    TIMEZONE: str = os.getenv("TIMEZONE", "America/New_York")
    
    # 过滤和推送配置
    # 评分阈值（0-100分制）：只发送分数 >= 此值的新闻
    # 建议值：30=更多新闻（新评分标准下推荐），40=标准，50=严格，60=极严格
    # 注意：新评分标准（分桶+愤世嫉俗Persona）更严格，建议使用 30-35
    # 系统会自动动态调整阈值（最低不低于30），确保有足够新闻
    SCORE_THRESHOLD: float = float(os.getenv("SCORE_THRESHOLD", "35"))
    TOPK: int = int(os.getenv("TOPK", "8"))
    
    # 去重和历史记录
    ENABLE_DEDUP: bool = os.getenv("ENABLE_DEDUP", "true").lower() == "true"
    HISTORY_DB_PATH: str = os.getenv("HISTORY_DB_PATH", "./history/sent_news.db")
    # 标题相似度阈值（0.0-1.0）：用于去除不同来源的同一条新闻，默认0.75（75%相似）
    TITLE_SIMILARITY_THRESHOLD: float = float(os.getenv("TITLE_SIMILARITY_THRESHOLD", "0.75"))
    # 去重时间窗口（天）：只检查最近N天内的记录，默认7天（同一条新闻7天后可以再次发送）
    DEDUP_WINDOW_DAYS: int = int(os.getenv("DEDUP_WINDOW_DAYS", "7"))
    
    # 费用与速率控制
    MAX_ITEMS: int = int(os.getenv("MAX_ITEMS", "12"))
    MODEL_TIMEOUT: int = int(os.getenv("MODEL_TIMEOUT", "30"))
    
    # 全文抓取配置（分层处理）
    # 只对最终要发送的新闻抓取全文（0=抓取所有，>0=只抓取前N条）
    # 例如：TOPK=8, FULL_TEXT_TOP_N=0 → 抓取所有8条；FULL_TEXT_TOP_N=5 → 只抓取前5条
    FULL_TEXT_TOP_N: int = int(os.getenv("FULL_TEXT_TOP_N", "0"))  # 0=所有，>0=只抓取前N条
    FULL_TEXT_MAX_PARAGRAPHS: int = int(os.getenv("FULL_TEXT_MAX_PARAGRAPHS", "3"))  # 每篇最多提取段落数
    
    # 摘要生成配置
    # 摘要长度配置（建议范围，不是硬上限）
    SUMMARY_TARGET_LENGTH: int = int(os.getenv("SUMMARY_TARGET_LENGTH", "60"))  # 目标长度（建议值）
    SUMMARY_MAX_LENGTH: int = int(os.getenv("SUMMARY_MAX_LENGTH", "100"))  # 最大长度（硬上限，超过会截断）
    
    # SMTP 重试配置
    SMTP_MAX_RETRIES: int = int(os.getenv("SMTP_MAX_RETRIES", "3"))
    SMTP_RETRY_DELAY: int = int(os.getenv("SMTP_RETRY_DELAY", "2"))  # 秒
    
    # 语言配置
    # 可选值: "zh" (中文) 或 "en" (英文)
    LANGUAGE: str = os.getenv("LANGUAGE", "zh").lower()
    
    @classmethod
    def validate(cls) -> bool:
        """
        验证必需的配置项是否已设置
        
        Returns:
            bool: 配置是否有效
        """
        required_fields = {
            "OPENAI_API_KEY": cls.OPENAI_API_KEY,
            "MAIL_TO": cls.MAIL_TO,
        }
        
        # 检查邮件配置（SMTP 或 SendGrid 至少配置一个）
        has_smtp = cls.SMTP_USER and cls.SMTP_PASS
        has_sendgrid = cls.SENDGRID_API_KEY
        
        if not (has_smtp or has_sendgrid):
            logger.error("必须配置 SMTP 或 SendGrid 邮件服务")
            return False
        
        # 检查必需字段
        for field_name, field_value in required_fields.items():
            if not field_value:
                logger.error(f"缺少必需配置: {field_name}")
                return False
        
        logger.info("配置验证通过")
        return True
    
    @classmethod
    def get_summary(cls) -> str:
        """
        获取配置摘要（隐藏敏感信息）
        
        Returns:
            str: 配置摘要
        """
        def mask_sensitive(value: str) -> str:
            """隐藏敏感信息"""
            if not value or len(value) < 8:
                return "***"
            return f"{value[:4]}...{value[-4:]}"
        
        summary = f"""
配置摘要:
- OpenAI Model: {cls.OPENAI_MODEL}
- OpenAI Base URL: {cls.OPENAI_BASE_URL}
- SMTP Host: {cls.SMTP_HOST}:{cls.SMTP_PORT}
- Mail From: {cls.MAIL_FROM or cls.SMTP_USER}
- Mail To: {cls.MAIL_TO}
- Score Threshold: {cls.SCORE_THRESHOLD}
- Top K: {cls.TOPK}
- Max Items: {cls.MAX_ITEMS}
- Model Timeout: {cls.MODEL_TIMEOUT}s
- Full Text Top N: {cls.FULL_TEXT_TOP_N} (分层处理)
- Full Text Max Paragraphs: {cls.FULL_TEXT_MAX_PARAGRAPHS}
- Summary Target Length: {cls.SUMMARY_TARGET_LENGTH} (建议)
- Summary Max Length: {cls.SUMMARY_MAX_LENGTH} (硬上限)
- Enable Dedup: {cls.ENABLE_DEDUP}
- Dedup Window Days: {cls.DEDUP_WINDOW_DAYS} (去重时间窗口)
- Timezone: {cls.TIMEZONE}
"""
        return summary.strip()


# 导出单例配置对象
config = Config()

