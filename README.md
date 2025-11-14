# 🔥 HotNews Agent

> 基于 AI 评分的每日热点新闻推送系统

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## 📖 项目简介

HotNews Agent 是一个智能新闻推送系统，它能够：

- ✅ **AI 评分**：使用 LLM 对新闻进行质量评分（基于 NewsScore 的评分标准）
- ✅ **RSS 抓取**：从多个新闻源自动抓取最新新闻
- ✅ **智能过滤**：仅推送高分新闻（可配置阈值）
- ✅ **中文改写**：自动将英文标题改写为客观、简洁的中文标题
- ✅ **中文摘要**：生成事实导向的简洁摘要（支持全文抓取）
- ✅ **邮件推送**：精美的每日简报邮件（支持多收件人）
- ✅ **自动去重**：基于 URL 和标题相似度的智能去重
- ✅ **定时执行**：GitHub Actions 自动定时运行

## 🏗 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                      HotNews Agent                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ RSS抓取   │→│ AI评分    │→│ 阈值过滤   │→│ 去重过滤   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 全文抓取   │→│ 中文改写   │→│ 中文摘要   │→│ 邮件推送   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└──────────────────────────────────────────────────────────────┘
```

## ✨ 核心特性

### 1. AI 新闻评分
- 基于 NewsScore 的严格评分标准
- 重点关注科技、商业、经济新闻
- 过滤低质量内容（八卦、过度政治化等）

### 2. 智能去重
- **URL 去重**：归一化 URL，去除跟踪参数
- **标题相似度去重**：使用文本相似度算法，去除不同来源的同一条新闻
- **历史记录**：SQLite 数据库记录已发送新闻，避免重复推送

### 3. 分层处理
- **第一层**：使用 snippet 对所有新闻进行评分
- **第二层**：仅对高分新闻抓取全文，生成高质量摘要
- **成本优化**：避免不必要的全文抓取和 API 调用

### 4. 灵活的摘要生成
- 支持基于 snippet 或全文生成摘要
- 可配置目标长度和最大长度
- 智能截断（在标点处截断，保持句子完整性）

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/hotnews-agent.git
cd hotnews-agent
```

### 2. 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `env.example` 为 `.env` 并填写配置：

```bash
cp env.example .env
```

编辑 `.env` 文件：

```bash
# LLM API 配置（推荐使用 DeepSeek，便宜）
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com

# 邮件配置（SMTP）
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
MAIL_FROM=your-email@gmail.com
MAIL_TO=recipient@example.com

# 过滤配置
SCORE_THRESHOLD=0.4  # 推荐值：0.3-0.5
TOPK=8
```

### 4. 运行测试

```bash
cd extensions/hotnews-agent

# 使用模拟数据测试（不调用 API）
python run_daily.py --mock

# 完整运行（真实新闻 + AI 评分）
python run_daily.py --real
```

## 📧 邮件示例

```
┌─────────────────────────────────────┐
│     📰 今日热点速递                  │
│        2025-11-14                   │
└─────────────────────────────────────┘

1) [分数 0.82] 首例AI策划网络间谍活动被阻断
   摘要：网络安全机构成功阻断首例AI策划的网络间谍活动，
         该攻击采用高度复杂技术，系统性评估显示网络攻击
         能力在六个月内翻倍。
   来源：Hacker News | 时间：2025-11-13 18:34 | 阅读原文 →

2) [分数 0.82] Waymo无人驾驶出租车将登陆美国三市高速
   摘要：Waymo无人驾驶出租车将于周三在美国洛杉矶、凤凰城
         和旧金山三市高速公路投入运营，首次实现无驾驶员
         情况下在高速公路提供付费载客服务。
   来源：Ars Technica | 时间：2025-11-13 15:30 | 阅读原文 →

...
```

## ⚙️ 配置说明

### 核心配置项

| 配置项 | 说明 | 默认值 | 推荐值 |
|--------|------|--------|--------|
| `SCORE_THRESHOLD` | 新闻分数阈值 | 0.8 | 0.4 |
| `TOPK` | 每天推送的新闻数量 | 8 | 8 |
| `MAX_ITEMS` | 每天最多处理的新闻数 | 12 | 12 |
| `TITLE_SIMILARITY_THRESHOLD` | 标题相似度阈值 | 0.75 | 0.75 |
| `ENABLE_DEDUP` | 启用去重 | true | true |

### 邮件配置

**方式 1: SMTP（推荐 Gmail/Outlook）**

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password  # Gmail 需要使用应用专用密码
MAIL_FROM=your-email@gmail.com
MAIL_TO=recipient1@example.com,recipient2@example.com
```

**方式 2: SendGrid（推荐用于生产环境）**

```bash
SENDGRID_API_KEY=SG.xxx
MAIL_FROM=noreply@yourdomain.com
MAIL_TO=recipient@example.com
```

### LLM 配置

**使用 DeepSeek（推荐，便宜）**

```bash
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com
```

**使用 OpenAI（更贵但质量更高）**

```bash
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_BASE_URL=https://api.openai.com/v1
```

## 🤖 GitHub Actions 定时执行

### 1. 配置 Secrets

在 GitHub 仓库设置中添加以下 Secrets：

```
Settings → Secrets and variables → Actions → New repository secret
```

必需的 Secrets：
- `OPENAI_API_KEY`
- `SMTP_USER`
- `SMTP_PASS`
- `MAIL_TO`
- （其他配置项根据需要添加）

### 2. 修改执行时间

编辑 `.github/workflows/daily.yml`：

```yaml
on:
  schedule:
    - cron: '0 12 * * *'  # 每天 12:00 UTC（北京时间 20:00）
```

### 3. 手动触发

在 GitHub Actions 页面可以手动运行 workflow。

## 📁 项目结构

```
hotnews-agent/
├── extensions/
│   └── hotnews-agent/           # 核心代码
│       ├── __init__.py
│       ├── config.py            # 配置管理
│       ├── rss_fetcher.py       # RSS 新闻抓取
│       ├── news_scorer.py       # AI 新闻评分
│       ├── newscore_adapter.py  # 数据模型和适配器
│       ├── zh_rewrite.py        # 中文标题改写
│       ├── zh_summary.py        # 中文摘要生成
│       ├── full_text_extractor.py # 全文抓取
│       ├── email_push.py        # 邮件推送
│       ├── storage.py           # 历史记录/去重
│       └── run_daily.py         # 主执行入口
├── .github/
│   └── workflows/
│       └── daily.yml            # GitHub Actions 配置
├── scripts/                     # 工具脚本
├── tests/                       # 单元测试
├── requirements.txt
├── .gitignore
├── LICENSE
├── CONTRIBUTING.md
└── README.md
```

## 🔧 开发指南

### 添加新的新闻源

编辑 `extensions/hotnews-agent/rss_fetcher.py`：

```python
DEFAULT_SOURCES = [
    {"name": "Your News Source", "url": "https://example.com/rss", "category": "tech"},
    # ...
]
```

### 自定义邮件模板

编辑 `extensions/hotnews-agent/email_push.py` 中的 `_build_html_body()` 方法。

### 调整提示词

- 标题改写：`zh_rewrite.py` → `_build_rewrite_prompt()`
- 摘要生成：`zh_summary.py` → `_build_summary_prompt()`
- 新闻评分：`news_scorer.py` → `SCORE_PROMPT_TEMPLATE`

## 🧪 测试

```bash
# 单元测试
pytest tests/

# 模拟数据测试
cd extensions/hotnews-agent
python run_daily.py --mock

# 完整流程测试
python run_daily.py --real
```

## 💰 成本估算

使用 DeepSeek API，每天推送 8 条新闻给 10 个邮箱：

- **API 调用成本**：约 0.14 元/月
- **邮件发送成本**：0 元（SMTP 免费）
- **GitHub Actions**：0 元（公共仓库免费）

**总计：约 0.14 元/月** ✅

详细成本分析请参考项目文档。

## 📝 许可与归属

本项目使用 **MIT License**。

### 重要声明

本项目的新闻评分逻辑基于 [NewsScore](https://github.com/themaximalist/newsscore) (by [@themaximalist](https://github.com/themaximalist)) 的评分标准和提示词。我们严格遵循其评分标准，但实现了独立的 Python 版本，不依赖原项目的 Node.js 实现。

NewsScore 项目同样使用 MIT License。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

在贡献代码前，请确保：
1. 遵循 PEP 8 代码规范
2. 添加必要的注释和文档字符串
3. 编写单元测试
4. 更新相关文档

详细贡献指南请参考 [CONTRIBUTING.md](CONTRIBUTING.md)。

## ❓ 常见问题

### Q: 如何使用国内 LLM 服务？

A: 修改配置：

```bash
# DeepSeek
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com

# Moonshot
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=moonshot-v1-8k
OPENAI_BASE_URL=https://api.moonshot.cn/v1
```

### Q: 如何调整新闻数量？

A: 修改 `TOPK` 配置项。

### Q: 如何禁用去重？

A: 设置 `ENABLE_DEDUP=false`。

### Q: Gmail SMTP 报错？

A: 需要在 Google 账户设置中开启"两步验证"并生成"应用专用密码"。

### Q: 如何添加更多收件人？

A: 在 `MAIL_TO` 中用逗号分隔多个邮箱：

```bash
MAIL_TO=email1@example.com,email2@example.com,email3@example.com
```

## 📮 联系方式

- 提交 Issue：[GitHub Issues](https://github.com/your-username/hotnews-agent/issues)
- 邮箱：your-email@example.com

---

**Built with ❤️ based on [NewsScore](https://github.com/themaximalist/newsscore)**

