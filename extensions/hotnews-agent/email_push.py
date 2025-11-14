"""
邮件推送模块
支持 SMTP 和 SendGrid 两种方式
"""

import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from datetime import datetime
from loguru import logger
from config import config
from newscore_adapter import NewsScoredItem

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    HAS_SENDGRID = True
except ImportError:
    HAS_SENDGRID = False
    logger.warning("SendGrid 未安装，仅支持 SMTP 推送")


class EmailPusher:
    """邮件推送器"""
    
    def __init__(self):
        """初始化邮件推送器"""
        self.use_sendgrid = bool(config.SENDGRID_API_KEY and HAS_SENDGRID)
        
        if self.use_sendgrid:
            logger.info("使用 SendGrid 发送邮件")
            self.sendgrid_client = SendGridAPIClient(config.SENDGRID_API_KEY)
        else:
            logger.info("使用 SMTP 发送邮件")
    
    def send_daily_digest(
        self, 
        items: List[NewsScoredItem], 
        date: str = None,
        fallback_items: Optional[List[NewsScoredItem]] = None
    ) -> bool:
        """
        发送每日新闻简报（支持空结果回退）
        
        Args:
            items: 新闻项列表
            date: 日期字符串（如 2025-11-11）
            fallback_items: 当 items 为空时的备选新闻（Top 3）
        
        Returns:
            bool: 是否发送成功
        """
        # 生成日期
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        # 空结果回退
        if not items:
            logger.warning("没有符合条件的新闻，发送空结果邮件")
            subject = f"【今日热点速递】{date} - 暂无符合条件的热点"
            html_body = self._build_empty_html_body(date, fallback_items)
            text_body = self._build_empty_text_body(date, fallback_items)
        else:
            # 正常邮件
            subject = f"【今日热点速递】{date}"
            html_body = self._build_html_body(items, date)
            text_body = self._build_text_body(items, date)
        
        # 发送邮件
        try:
            if self.use_sendgrid:
                return self._send_via_sendgrid(subject, html_body, text_body)
            else:
                return self._send_via_smtp(subject, html_body, text_body)
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False
    
    def _send_via_smtp(self, subject: str, html_body: str, text_body: str) -> bool:
        """
        通过 SMTP 发送邮件（含重试和指数退避，支持多个收件人）
        
        Args:
            subject: 邮件主题
            html_body: HTML 正文
            text_body: 纯文本正文
        
        Returns:
            bool: 是否发送成功
        """
        # 解析收件人列表（支持逗号分隔的多个邮箱）
        recipients = [email.strip() for email in config.MAIL_TO.split(",") if email.strip()]
        if not recipients:
            logger.error("未配置收件人邮箱")
            return False
        
        for attempt in range(1, config.SMTP_MAX_RETRIES + 1):
            try:
                # 创建邮件
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = config.MAIL_FROM or config.SMTP_USER
                msg["To"] = ", ".join(recipients)  # 显示用逗号+空格分隔
                
                # 添加正文
                part1 = MIMEText(text_body, "plain", "utf-8")
                part2 = MIMEText(html_body, "html", "utf-8")
                msg.attach(part1)
                msg.attach(part2)
                
                # 连接 SMTP 服务器并发送（强制 TLS）
                with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
                    server.starttls()  # 强制 TLS 加密
                    server.login(config.SMTP_USER, config.SMTP_PASS)
                    # 发送给所有收件人
                    server.send_message(msg, to_addrs=recipients)
                
                logger.info(f"邮件已通过 SMTP 发送至: {', '.join(recipients)}")
                return True
                
            except Exception as e:
                logger.error(f"SMTP 发送失败 (尝试 {attempt}/{config.SMTP_MAX_RETRIES}): {e}")
                
                if attempt < config.SMTP_MAX_RETRIES:
                    # 指数退避：2^attempt 秒
                    delay = config.SMTP_RETRY_DELAY ** attempt
                    logger.info(f"等待 {delay} 秒后重试...")
                    time.sleep(delay)
                else:
                    logger.error("SMTP 发送失败，已达最大重试次数")
                    return False
        
        return False
    
    def _send_via_sendgrid(self, subject: str, html_body: str, text_body: str) -> bool:
        """
        通过 SendGrid 发送邮件（支持多个收件人）
        
        Args:
            subject: 邮件主题
            html_body: HTML 正文
            text_body: 纯文本正文
        
        Returns:
            bool: 是否发送成功
        """
        # 解析收件人列表（支持逗号分隔的多个邮箱）
        recipients = [email.strip() for email in config.MAIL_TO.split(",") if email.strip()]
        if not recipients:
            logger.error("未配置收件人邮箱")
            return False
        
        try:
            message = Mail(
                from_email=config.MAIL_FROM,
                to_emails=recipients,  # SendGrid 支持列表
                subject=subject,
                plain_text_content=text_body,
                html_content=html_body
            )
            
            response = self.sendgrid_client.send(message)
            
            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"邮件已通过 SendGrid 发送至: {', '.join(recipients)}")
                return True
            else:
                logger.error(f"SendGrid 返回错误: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"SendGrid 发送失败: {e}")
            return False
    
    def _build_html_body(self, items: List[NewsScoredItem], date: str) -> str:
        """
        构建 HTML 邮件正文（优化版）
        
        Args:
            items: 新闻项列表
            date: 日期
        
        Returns:
            str: HTML 内容
        """
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, 'PingFang SC', 'Hiragino Sans GB', sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 28px; }}
        .header .date {{ font-size: 16px; opacity: 0.9; margin-top: 10px; }}
        .news-item {{ background: white; padding: 20px; margin-bottom: 15px; border-radius: 8px; border-left: 4px solid #667eea; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .news-item:hover {{ box-shadow: 0 4px 8px rgba(0,0,0,0.15); }}
        .news-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
        .news-number {{ font-size: 20px; font-weight: bold; color: #667eea; }}
        .news-score {{ background: #28a745; color: white; padding: 3px 12px; border-radius: 15px; font-size: 13px; font-weight: bold; }}
        .news-title {{ font-size: 18px; font-weight: bold; color: #2c3e50; margin: 10px 0; }}
        .news-summary {{ color: #555; margin: 10px 0; font-size: 14px; line-height: 1.8; }}
        .news-meta {{ color: #999; font-size: 13px; margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee; }}
        .news-meta a {{ color: #667eea; text-decoration: none; font-weight: 500; }}
        .news-meta a:hover {{ text-decoration: underline; }}
        .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 40px; padding: 20px; background: white; border-radius: 10px; }}
        .footer p {{ margin: 5px 0; }}
        @media (prefers-color-scheme: dark) {{
            body {{ background: #1a1a1a; color: #e0e0e0; }}
            .news-item {{ background: #2d2d2d; border-left-color: #8b9aec; }}
            .news-title {{ color: #e0e0e0; }}
            .news-summary {{ color: #b0b0b0; }}
            .footer {{ background: #2d2d2d; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📰 今日热点速递</h1>
        <div class="date">{date}</div>
    </div>
"""
        
        for i, item in enumerate(items, 1):
            # UTM 参数用于统计
            link = f"{item.url}?utm_source=hotnews-agent&utm_medium=email" if '?' not in item.url else f"{item.url}&utm_source=hotnews-agent"
            
            html += f"""
    <div class="news-item">
        <div class="news-header">
            <span class="news-number">{i}</span>
            <span class="news-score">分数 {item.score:.2f}</span>
        </div>
        <div class="news-title">{item.title_zh or item.title}</div>
        <div class="news-summary">{item.summary_zh or '暂无摘要'}</div>
        <div class="news-meta">
            来源：{item.source} | 时间：{item.published_time} | 
            <a href="{link}" target="_blank">阅读原文 →</a>
        </div>
    </div>
"""
        
        html += """
    <div class="footer">
        <p>此邮件由 HotNews Agent 自动生成</p>
        <p>基于 <a href="https://github.com/themaximalist/newsscore" target="_blank">NewsScore</a> 项目打分</p>
        <p style="margin-top: 15px; font-size: 11px; color: #aaa;">回复 STOP 可退订此邮件</p>
    </div>
</body>
</html>
"""
        return html
    
    def _build_empty_html_body(self, date: str, fallback_items: Optional[List[NewsScoredItem]] = None) -> str:
        """
        构建空结果邮件的 HTML 正文
        
        Args:
            date: 日期
            fallback_items: 备选新闻（原始 Top 3）
        
        Returns:
            str: HTML 内容
        """
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, 'PingFang SC', sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        .header {{ background: linear-gradient(135deg, #ffa500 0%, #ff6b6b 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 28px; }}
        .header .date {{ font-size: 16px; opacity: 0.9; margin-top: 10px; }}
        .notice {{ background: white; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px; }}
        .notice-icon {{ font-size: 48px; margin-bottom: 20px; }}
        .notice-title {{ font-size: 20px; font-weight: bold; color: #555; margin-bottom: 10px; }}
        .notice-text {{ color: #777; font-size: 15px; }}
        .fallback-section {{ background: white; padding: 20px; border-radius: 10px; }}
        .fallback-title {{ font-size: 18px; font-weight: bold; color: #555; margin-bottom: 15px; }}
        .fallback-item {{ padding: 15px; margin-bottom: 10px; border-left: 3px solid #ccc; background: #f9f9f9; border-radius: 5px; }}
        .fallback-item-title {{ font-weight: 500; color: #333; margin-bottom: 5px; }}
        .fallback-item-meta {{ font-size: 13px; color: #999; }}
        .fallback-item-meta a {{ color: #667eea; text-decoration: none; }}
        .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 40px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📭 今日热点速递</h1>
        <div class="date">{date}</div>
    </div>
    
    <div class="notice">
        <div class="notice-icon">🔍</div>
        <div class="notice-title">今日暂无符合条件的热点新闻</div>
        <div class="notice-text">
            今天没有评分达到 {config.SCORE_THRESHOLD} 以上的新闻。<br>
            以下是今日评分最高的 3 条新闻供参考。
        </div>
    </div>
"""
        
        if fallback_items:
            html += '<div class="fallback-section"><div class="fallback-title">📋 今日 Top 3 新闻：</div>'
            for i, item in enumerate(fallback_items[:3], 1):
                html += f"""
    <div class="fallback-item">
        <div class="fallback-item-title">{i}. {item.title}</div>
        <div class="fallback-item-meta">
            分数：{item.score:.2f} | 来源：{item.source} | 
            <a href="{item.url}" target="_blank">阅读原文 →</a>
        </div>
    </div>
"""
            html += '</div>'
        
        html += """
    <div class="footer">
        <p>此邮件由 HotNews Agent 自动生成</p>
        <p>基于 <a href="https://github.com/themaximalist/newsscore" target="_blank">NewsScore</a> 项目打分</p>
    </div>
</body>
</html>
"""
        return html
    
    def _build_empty_text_body(self, date: str, fallback_items: Optional[List[NewsScoredItem]] = None) -> str:
        """
        构建空结果邮件的纯文本正文
        
        Args:
            date: 日期
            fallback_items: 备选新闻（原始 Top 3）
        
        Returns:
            str: 纯文本内容
        """
        text = f"【今日热点速递】{date}\n\n"
        text += "=" * 60 + "\n\n"
        text += "今日暂无符合条件的热点新闻\n\n"
        text += f"今天没有评分达到 {config.SCORE_THRESHOLD} 以上的新闻。\n"
        text += "以下是今日评分最高的 3 条新闻供参考：\n\n"
        
        if fallback_items:
            for i, item in enumerate(fallback_items[:3], 1):
                text += f"{i}. {item.title}\n"
                text += f"   分数：{item.score:.2f} | 来源：{item.source}\n"
                text += f"   链接：{item.url}\n\n"
        else:
            text += "暂无新闻数据\n\n"
        
        text += "=" * 60 + "\n"
        text += "此邮件由 HotNews Agent 自动生成\n"
        text += "基于 NewsScore 项目打分: https://github.com/themaximalist/newsscore\n"
        
        return text
    
    def _build_text_body(self, items: List[NewsScoredItem], date: str) -> str:
        """
        构建纯文本邮件正文
        
        Args:
            items: 新闻项列表
            date: 日期
        
        Returns:
            str: 纯文本内容
        """
        text = f"【今日热点速递】{date}\n\n"
        text += "=" * 60 + "\n\n"
        
        for i, item in enumerate(items, 1):
            text += f"{i}) [分数 {item.score:.2f}] {item.title_zh or item.title}\n"
            text += f"   摘要：{item.summary_zh or '暂无摘要'}\n"
            text += f"   来源：{item.source} | 时间：{item.published_time}\n"
            text += f"   链接：{item.url}\n\n"
        
        text += "=" * 60 + "\n"
        text += "此邮件由 HotNews Agent 自动生成\n"
        text += "基于 NewsScore 项目打分: https://github.com/themaximalist/newsscore\n"
        
        return text

