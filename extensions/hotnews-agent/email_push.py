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
        fallback_items: Optional[List[NewsScoredItem]] = None,
        language: str = None
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
            lang = language or config.LANGUAGE
            if lang == "en":
                subject = f"Daily News Digest - {date}"
            else:
                subject = f"【今日热点速递】{date}"
            html_body = self._build_html_body(items, date, lang)
            text_body = self._build_text_body(items, date, lang)
        
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
    
    def _build_html_body(self, items: List[NewsScoredItem], date: str, language: str = None) -> str:
        """
        构建 HTML 邮件正文（高端 AI 产品设计）
        
        Args:
            items: 新闻项列表
            date: 日期
            language: 语言 ("zh" 或 "en")，默认使用配置中的语言
        
        Returns:
            str: HTML 内容
        """
        lang = language or config.LANGUAGE
        
        # 根据语言选择文本
        if lang == "en":
            header_title = "Daily Intelligence Digest"
            score_high = "High Confidence"
            score_medium = "Relevant"
            score_low = "Noteworthy"
            source_label = ""
            read_more = "Read full story"
            footer_text1 = "Powered by HotNews Agent"
            footer_text2 = "AI-curated news intelligence"
            why_matters = "Why this matters"
        else:
            header_title = "每日情报摘要"
            score_high = "高置信度"
            score_medium = "相关"
            score_low = "值得关注"
            source_label = ""
            read_more = "阅读全文"
            footer_text1 = "由 HotNews Agent 驱动"
            footer_text2 = "AI 策划的新闻情报"
            why_matters = "为什么重要"
        
        html = f"""
<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="dark">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        @media (prefers-reduced-motion: reduce) {{
            *, *::before, *::after {{
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }}
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', 'SF Pro Display', system-ui, sans-serif;
            line-height: 1.6;
            color: #e4e4e7;
            background: #09090b;
            padding: 24px 16px;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }}
        
        .container {{
            max-width: 680px;
            margin: 0 auto;
        }}
        
        /* Premium Header */
        .header {{
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
            padding: 48px 32px;
            border-radius: 12px 12px 0 0;
            position: relative;
            overflow: hidden;
        }}
        
        .header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: radial-gradient(circle at 30% 50%, rgba(255,255,255,0.08) 0%, transparent 60%);
            pointer-events: none;
        }}
        
        .header-content {{
            position: relative;
            z-index: 1;
        }}
        
        .header h1 {{
            font-size: 28px;
            font-weight: 600;
            letter-spacing: -0.02em;
            color: #ffffff;
            margin-bottom: 8px;
        }}
        
        .header-date {{
            font-size: 14px;
            font-weight: 500;
            color: rgba(255, 255, 255, 0.75);
            letter-spacing: 0.01em;
        }}
        
        /* Content Area */
        .content {{
            background: #18181b;
            padding: 32px;
            border-radius: 0 0 12px 12px;
            border: 1px solid #27272a;
            border-top: none;
        }}
        
        /* News Card - Premium AI Product Style */
        .news-card {{
            background: #1c1c1f;
            border: 1px solid #2a2a2d;
            border-radius: 10px;
            padding: 24px;
            margin-bottom: 16px;
            transition: all 180ms cubic-bezier(0.2, 0.8, 0.2, 1);
            position: relative;
        }}
        
        .news-card:hover {{
            transform: translateY(-2px);
            border-color: #3a3a3d;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.06);
        }}
        
        .news-card:last-child {{
            margin-bottom: 0;
        }}
        
        /* Card Header */
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
            gap: 16px;
        }}
        
        .rank-badge {{
            font-size: 16px;
            font-weight: 600;
            color: #71717a;
            font-variant-numeric: tabular-nums;
            flex-shrink: 0;
        }}
        
        /* Score Pill - Semantic + Premium */
        .score-pill {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(34, 197, 94, 0.12);
            border: 1px solid rgba(34, 197, 94, 0.2);
            color: #86efac;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.01em;
            box-shadow: 0 0 12px rgba(34, 197, 94, 0.08);
            flex-shrink: 0;
        }}
        
        .score-pill-medium {{
            background: rgba(234, 179, 8, 0.12);
            border-color: rgba(234, 179, 8, 0.2);
            color: #fde047;
            box-shadow: 0 0 12px rgba(234, 179, 8, 0.08);
        }}
        
        .score-pill-low {{
            background: rgba(148, 163, 184, 0.12);
            border-color: rgba(148, 163, 184, 0.2);
            color: #cbd5e1;
            box-shadow: 0 0 12px rgba(148, 163, 184, 0.05);
        }}
        
        .score-label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            opacity: 0.9;
        }}
        
        .score-value {{
            font-size: 13px;
            font-weight: 700;
            font-variant-numeric: tabular-nums;
        }}
        
        /* Title - Editorial Spacing */
        .news-title {{
            font-size: 19px;
            font-weight: 600;
            line-height: 1.5;
            color: #fafafa;
            margin-bottom: 14px;
            letter-spacing: -0.01em;
        }}
        
        .news-title a {{
            color: inherit;
            text-decoration: none;
        }}
        
        /* Summary - Calm Background */
        .news-summary {{
            font-size: 15px;
            line-height: 1.65;
            color: #a1a1aa;
            background: rgba(39, 39, 42, 0.6);
            padding: 14px 16px;
            border-radius: 6px;
            border-left: 2px solid #3f3f46;
            margin-bottom: 16px;
        }}
        
        /* Metadata Row - Product Style */
        .metadata {{
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
            font-size: 13px;
            color: #71717a;
            margin-bottom: 12px;
            font-variant-numeric: tabular-nums;
        }}
        
        .metadata-item {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        
        .metadata-separator {{
            color: #3f3f46;
        }}
        
        .metadata-source {{
            font-weight: 500;
            color: #a1a1aa;
        }}
        
        /* CTA - Guided Action */
        .cta-container {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .read-more {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            color: #a78bfa;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
            transition: all 160ms cubic-bezier(0.2, 0.8, 0.2, 1);
            padding: 6px 12px;
            margin: -6px -12px;
            border-radius: 6px;
        }}
        
        .read-more:hover {{
            color: #c4b5fd;
            background: rgba(167, 139, 250, 0.08);
        }}
        
        .read-more::after {{
            content: '→';
            display: inline-block;
            transition: transform 160ms cubic-bezier(0.2, 0.8, 0.2, 1);
        }}
        
        .read-more:hover::after {{
            transform: translateX(3px);
        }}
        
        /* AI Insight - Always Visible */
        .ai-insight {{
            display: flex;
            align-items: flex-start;
            gap: 8px;
            margin-top: 12px;
            padding: 10px 12px;
            background: rgba(167, 139, 250, 0.08);
            border-left: 2px solid rgba(167, 139, 250, 0.3);
            border-radius: 6px;
            font-size: 12px;
            line-height: 1.5;
            color: #a1a1aa;
        }}
        
        .ai-insight-icon {{
            color: #a78bfa;
            font-size: 14px;
            flex-shrink: 0;
            margin-top: 1px;
        }}
        
        .ai-insight-content {{
            flex: 1;
        }}
        
        .ai-insight-label {{
            font-weight: 600;
            color: #c4b5fd;
            margin-bottom: 3px;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .ai-insight-text {{
            color: #a1a1aa;
        }}
        
        /* Footer - Minimal */
        .footer {{
            background: #18181b;
            border-top: 1px solid #27272a;
            padding: 32px;
            text-align: center;
            margin-top: 32px;
            border-radius: 12px;
        }}
        
        .footer-text {{
            font-size: 13px;
            color: #71717a;
            line-height: 1.8;
            margin-bottom: 4px;
        }}
        
        .footer-link {{
            color: #a1a1aa;
            text-decoration: none;
            transition: color 160ms;
        }}
        
        .footer-link:hover {{
            color: #e4e4e7;
        }}
        
        .footer-unsubscribe {{
            font-size: 11px;
            color: #52525b;
            margin-top: 16px;
        }}
        
        /* Responsive */
        @media (max-width: 600px) {{
            body {{
                padding: 16px 12px;
            }}
            
            .header {{
                padding: 36px 24px;
            }}
            
            .header h1 {{
                font-size: 24px;
            }}
            
            .content {{
                padding: 24px 20px;
            }}
            
            .news-card {{
                padding: 20px;
            }}
            
            .news-title {{
                font-size: 17px;
            }}
            
            .card-header {{
                flex-direction: column;
                align-items: flex-start;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-content">
                <h1>{header_title}</h1>
                <div class="header-date">{self._format_date_human(date, lang)}</div>
            </div>
        </div>
        <div class="content">
"""
        
        for i, item in enumerate(items, 1):
            # UTM 参数
            link = f"{item.url}?utm_source=hotnews-agent&utm_medium=email" if '?' not in item.url else f"{item.url}&utm_source=hotnews-agent"
            
            # 根据语言选择标题和摘要
            if lang == "en":
                title = item.title_en or item.title
                summary = item.summary_en or "No summary available"
            else:
                title = item.title_zh or item.title
                summary = item.summary_zh or "暂无摘要"
            
            # 分数语义化
            score = item.score
            if score >= 80:
                score_class = "score-pill"
                score_semantic = score_high
            elif score >= 60:
                score_class = "score-pill score-pill-medium"
                score_semantic = score_medium
            else:
                score_class = "score-pill score-pill-low"
                score_semantic = score_low
            
            # 格式化时间
            time_human = self._format_time_human(item.published_time, lang)
            
            # 获取 AI 评分理由
            reasons = getattr(item, 'reasons', [])
            ai_insight_html = ""
            if reasons:
                # 显示 AI reasons
                if lang == "en":
                    reasons_text = " · ".join(reasons[:3])  # 最多显示 3 条
                    insight_label = "Why this matters"
                else:
                    reasons_text = " · ".join(reasons[:3])
                    insight_label = "为什么重要"
                
                ai_insight_html = f"""
                <div class="ai-insight">
                    <div class="ai-insight-icon">✦</div>
                    <div class="ai-insight-content">
                        <div class="ai-insight-label">{insight_label}</div>
                        <div class="ai-insight-text">{reasons_text}</div>
                    </div>
                </div>
                """
            
            html += f"""
            <div class="news-card">
                <div class="card-header">
                    <div class="rank-badge">{i:02d}</div>
                    <div class="{score_class}">
                        <span class="score-label">{score_semantic}</span>
                        <span class="score-value">{score:.1f}</span>
                    </div>
                </div>
                
                <h2 class="news-title">
                    <a href="{link}" target="_blank">{title}</a>
                </h2>
                
                <div class="news-summary">{summary}</div>
                
                <div class="metadata">
                    <span class="metadata-source">{item.source}</span>
                    <span class="metadata-separator">·</span>
                    <span class="metadata-item">{time_human}</span>
                </div>
                
                {ai_insight_html}
                
                <div class="cta-container">
                    <a href="{link}" target="_blank" class="read-more">{read_more}</a>
                </div>
            </div>
"""
        
        html += f"""
        </div>
        
        <div class="footer">
            <div class="footer-text">{footer_text1}</div>
            <div class="footer-text">{footer_text2} · <a href="https://github.com/themaximalist/newsscore" class="footer-link" target="_blank">Scoring by NewsScore</a></div>
            <div class="footer-unsubscribe">Reply STOP to unsubscribe</div>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def _format_date_human(self, date_str: str, lang: str) -> str:
        """格式化日期为人类可读格式"""
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            if lang == "en":
                return dt.strftime("%B %d, %Y")
            else:
                return f"{dt.year}年{dt.month}月{dt.day}日"
        except:
            return date_str
    
    def _format_time_human(self, time_str: str, lang: str) -> str:
        """格式化时间为人类可读格式"""
        try:
            from datetime import datetime
            # 尝试解析 ISO 格式
            if 'T' in time_str:
                dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                if lang == "en":
                    return dt.strftime("%b %d · %I:%M %p")
                else:
                    return dt.strftime("%m月%d日 · %H:%M")
            else:
                return time_str
        except:
            return time_str
        """
        构建 HTML 邮件正文（现代化设计，支持双语）
        
        Args:
            items: 新闻项列表
            date: 日期
            language: 语言 ("zh" 或 "en")，默认使用配置中的语言
        
        Returns:
            str: HTML 内容
        """
        lang = language or config.LANGUAGE
        
        # 根据语言选择文本
        if lang == "en":
            header_title = "📰 Daily News Digest"
            score_label = "Score"
            source_label = "Source"
            time_label = "Time"
            read_more = "Read More →"
            footer_text1 = "This email is automatically generated by HotNews Agent"
            footer_text2 = "Scored using NewsScore project"
            no_summary = "No summary available"
        else:
            header_title = "📰 今日热点速递"
            score_label = "分数"
            source_label = "来源"
            time_label = "时间"
            read_more = "阅读原文 →"
            footer_text1 = "此邮件由 HotNews Agent 自动生成"
            footer_text2 = "基于 NewsScore 项目打分"
            no_summary = "暂无摘要"
        
        html = f"""
<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            line-height: 1.6;
            color: #1a1a1a;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 700px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }}
        .header::before {{
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
            animation: pulse 20s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); opacity: 0.5; }}
            50% {{ transform: scale(1.1); opacity: 0.8; }}
        }}
        .header-content {{
            position: relative;
            z-index: 1;
        }}
        .header h1 {{
            margin: 0;
            font-size: 32px;
            font-weight: 700;
            letter-spacing: -0.5px;
            text-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
        }}
        .header .date {{
            font-size: 16px;
            opacity: 0.95;
            margin-top: 12px;
            font-weight: 400;
        }}
        .content {{
            padding: 30px;
        }}
        .news-item {{
            background: #ffffff;
            border: 1px solid #e8e8e8;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        .news-item::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s ease;
        }}
        .news-item:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(102, 126, 234, 0.15);
            border-color: #667eea;
        }}
        .news-item:hover::before {{
            width: 6px;
        }}
        .news-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}
        .news-number {{
            font-size: 24px;
            font-weight: 700;
            color: #667eea;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .news-score {{
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(40, 167, 69, 0.3);
        }}
        .news-title {{
            font-size: 20px;
            font-weight: 600;
            color: #1a1a1a;
            margin: 16px 0;
            line-height: 1.5;
        }}
        .news-summary {{
            color: #555;
            margin: 16px 0;
            font-size: 15px;
            line-height: 1.8;
            background: #f8f9fa;
            padding: 16px;
            border-radius: 8px;
            border-left: 3px solid #667eea;
        }}
        .news-meta {{
            color: #888;
            font-size: 13px;
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid #e8e8e8;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            align-items: center;
        }}
        .news-meta span {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }}
        .news-meta a {{
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            transition: color 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }}
        .news-meta a:hover {{
            color: #764ba2;
            text-decoration: underline;
        }}
        .news-meta a::after {{
            content: '→';
            font-size: 16px;
            transition: transform 0.2s ease;
        }}
        .news-meta a:hover::after {{
            transform: translateX(4px);
        }}
        .footer {{
            background: #f8f9fa;
            padding: 30px;
            text-align: center;
            border-top: 1px solid #e8e8e8;
        }}
        .footer p {{
            margin: 8px 0;
            color: #666;
            font-size: 13px;
        }}
        .footer a {{
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }}
        .footer a:hover {{
            text-decoration: underline;
        }}
        .footer .unsubscribe {{
            margin-top: 16px;
            font-size: 11px;
            color: #999;
        }}
        @media (max-width: 600px) {{
            body {{
                padding: 10px;
            }}
            .container {{
                border-radius: 12px;
            }}
            .header {{
                padding: 30px 20px;
            }}
            .header h1 {{
                font-size: 24px;
            }}
            .content {{
                padding: 20px;
            }}
            .news-item {{
                padding: 20px;
            }}
            .news-title {{
                font-size: 18px;
            }}
            .news-summary {{
                font-size: 14px;
                padding: 12px;
            }}
        }}
        @media (prefers-color-scheme: dark) {{
            body {{
                background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            }}
            .container {{
                background: #2d2d2d;
            }}
            .news-item {{
                background: #363636;
                border-color: #444;
            }}
            .news-title {{
                color: #e0e0e0;
            }}
            .news-summary {{
                color: #b0b0b0;
                background: #2d2d2d;
            }}
            .footer {{
                background: #2d2d2d;
                border-color: #444;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-content">
                <h1>{header_title}</h1>
                <div class="date">{date}</div>
            </div>
        </div>
        <div class="content">
"""
        
        for i, item in enumerate(items, 1):
            # UTM 参数用于统计
            link = f"{item.url}?utm_source=hotnews-agent&utm_medium=email" if '?' not in item.url else f"{item.url}&utm_source=hotnews-agent"
            
            # 根据语言选择标题和摘要
            if lang == "en":
                title = item.title_en or item.title
                summary = item.summary_en or no_summary
            else:
                title = item.title_zh or item.title
                summary = item.summary_zh or no_summary
            
            html += f"""
            <div class="news-item">
                <div class="news-header">
                    <span class="news-number">{i}</span>
                    <span class="news-score">{score_label} {item.score:.1f}</span>
                </div>
                <div class="news-title">{title}</div>
                <div class="news-summary">{summary}</div>
                <div class="news-meta">
                    <span>{source_label}: {item.source}</span>
                    <span>{time_label}: {item.published_time}</span>
                    <a href="{link}" target="_blank">{read_more}</a>
                </div>
            </div>
"""
        
        html += f"""
        </div>
        <div class="footer">
            <p>{footer_text1}</p>
            <p>{footer_text2} - <a href="https://github.com/themaximalist/newsscore" target="_blank">NewsScore</a></p>
            <p class="unsubscribe">Reply STOP to unsubscribe</p>
        </div>
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
    
    def _build_text_body(self, items: List[NewsScoredItem], date: str, language: str = None) -> str:
        """
        构建纯文本邮件正文（支持双语）
        
        Args:
            items: 新闻项列表
            date: 日期
            language: 语言 ("zh" 或 "en")
        
        Returns:
            str: 纯文本内容
        """
        lang = language or config.LANGUAGE
        
        if lang == "en":
            text = f"Daily News Digest - {date}\n\n"
            text += "=" * 60 + "\n\n"
            
            for i, item in enumerate(items, 1):
                title = item.title_en or item.title
                summary = item.summary_en or "No summary available"
                text += f"{i}) [Score {item.score:.2f}] {title}\n"
                text += f"   Summary: {summary}\n"
                text += f"   Source: {item.source} | Time: {item.published_time}\n"
                text += f"   Link: {item.url}\n\n"
            
            text += "=" * 60 + "\n"
            text += "This email is automatically generated by HotNews Agent\n"
            text += "Scored using NewsScore: https://github.com/themaximalist/newsscore\n"
        else:
            text = f"【今日热点速递】{date}\n\n"
            text += "=" * 60 + "\n\n"
            
            for i, item in enumerate(items, 1):
                title = item.title_zh or item.title
                summary = item.summary_zh or "暂无摘要"
                text += f"{i}) [分数 {item.score:.2f}] {title}\n"
                text += f"   摘要：{summary}\n"
                text += f"   来源：{item.source} | 时间：{item.published_time}\n"
                text += f"   链接：{item.url}\n\n"
            
            text += "=" * 60 + "\n"
            text += "此邮件由 HotNews Agent 自动生成\n"
            text += "基于 NewsScore 项目打分: https://github.com/themaximalist/newsscore\n"
        
        return text

