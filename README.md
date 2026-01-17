# 🔥 HotNews Agent

> 基于 AI 评分的每日热点新闻推送系统 - 自动抓取、智能评分、精选推送

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## 📖 项目简介

HotNews Agent 是一个智能新闻推送系统，它：

- ✅ **RSS 抓取**：自动从多个 RSS 源抓取最新新闻
- ✅ **AI 评分**：使用 LLM 对新闻进行严格评分（0-100 分制）
- ✅ **智能过滤**：只推送高分新闻（可配置阈值，支持动态调整）
- ✅ **中文改写**：客观、简洁的中文标题
- ✅ **中文摘要**：≤50字的事实导向摘要（支持全文提取）
- ✅ **邮件推送**：精美的每日简报邮件（支持多个收件人）
- ✅ **自动去重**：基于 URL 和标题相似度的智能去重
- ✅ **定时执行**：GitHub Actions 自动运行

## 🎯 核心特性

### 1. 结构化 AI 评分系统（核心创新）

采用**结构化 JSON 输出 + 确定性分数计算 + 批处理校准**架构，彻底解决 AI 评分的不确定性问题：

#### 1.1 结构化 JSON 输出
- LLM 只负责**判断**（tier、4个维度、flags、reasons），不直接输出分数
- 返回格式：
  ```json
  {
    "tier": "S|A|B|C",
    "impact": 0-5,
    "novelty": 0-5,
    "credibility": 0-5,
    "actionability": 0-5,
    "flags": {"clickbait": false, "job_posting": false, ...},
    "reasons": ["reason1", "reason2"]
  }
  ```
- 严格 JSON 校验，失败自动重试

#### 1.2 确定性分数计算
- **代码计算最终分数**，完全可预测、可调参
- Tier 决定基础区间：
  - S Tier: 90-100
  - A Tier: 70-89
  - B Tier: 40-69
  - C Tier: 0-39
- 4个维度分决定区间内位置（加权平均）
- Hard rules（确定性规则）：
  - job_posting cap ≤ 30
  - tool/tutorial/review cap ≤ 25/20
  - clickbait penalty: 降一档或扣 20 分

#### 1.3 批处理校准
- **强制比例约束**（写死在代码，不依赖 prompt）：
  - S Tier ≤ 3%
  - A Tier ≤ 10%
- **防塌缩机制**：如果分数分布太集中，自动拉伸（top quartile +3，bottom quartile -3）
- 确保系统长期运行不会"评分通胀/塌缩"

#### 1.4 可观测性与可回放
- 每天保存完整运行 artifact 到 `history/runs/YYYY-MM-DD.json`
- 包含：原始新闻、LLM 原始输出、解析结果、最终分数、阈值调整、去重过程、最终发送列表
- 日志输出分布统计：mean/std/p10/p50/p90/tier counts/top5 bottom5
- 支持离线回测和调参

### 2. 动态阈值调整

- 如果过滤后新闻少于目标数量，系统会自动降低阈值
- 最低阈值保护（≥30），确保新闻质量
- 智能回退机制，确保每天都能收到足够数量的邮件

### 3. 智能去重（增强版）

- **URL 去重**：规范化 URL，去除跟踪参数（utm_*, fbclid, gclid 等）
- **标题相似度**：
  - 优先使用 **TF-IDF cosine 相似度**（更准确，对改写更稳）
  - 回退到 SequenceMatcher（无需额外依赖）
- **历史记录**：SQLite 数据库记录已发送新闻，避免重复推送
- **全文缓存**：SQLite 缓存抓取的全文内容，7天过期策略，避免重复抓取

### 4. 分层处理（成本优化）

- **第一层**：使用摘要对所有新闻评分
- **第二层**：只对高分新闻抓取全文，生成高质量摘要
- **成本控制**：避免不必要的全文抓取和 API 调用

## 🏗 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                      HotNews Agent                            │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────┐│
│  │ RSS Fetch│→│ Structured    │→│ Calibrate│→│ Filter   ││
│  │          │  │ JSON Scoring  │  │(Batch)   │  │(Dynamic) ││
│  └──────────┘  └──────────────┘  └──────────┘  └──────────┘│
│                │ Deterministic │                              │
│                │ Score Compute │                              │
│                └──────────────┘                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Dedupe   │→│Full Text  │→│ Rewrite  │→│ Summary  │   │
│  │(TF-IDF)  │  │(Cached)   │  │(Bilingual)│ │(Bilingual)│   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                               │
│  ┌──────────┐  ┌──────────┐                                 │
│  │ Email     │  │ Artifact │                                 │
│  │(Digest)   │  │(JSON)    │                                 │
│  └──────────┘  └──────────┘                                 │
└──────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/news-agent.git
cd news-agent
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
# LLM API（推荐 DeepSeek，便宜且质量好）
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com

# 邮件配置（SMTP）
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password  # Gmail 需要使用应用专用密码
MAIL_FROM=your-email@gmail.com
MAIL_TO=recipient@example.com

# 过滤配置（新评分标准下推荐）
SCORE_THRESHOLD=35  # 0-100分制，35=标准，30=更多新闻，40=严格
TOPK=8              # 每日发送数量
MAX_ITEMS=12        # 最多处理的新闻数量（费用控制）

# 语言配置
LANGUAGE=zh  # 可选: "zh" (中文) 或 "en" (英文)
```

### 4. 运行测试

```bash
cd extensions/hotnews-agent

# 使用模拟数据测试（不调用 API）
python run_daily.py --mock

# 完整运行（真实新闻）
python run_daily.py --real
```

## 📧 邮件示例

```
┌─────────────────────────────────────┐
│     📰 今日热点速递                  │
│        2025-11-14                   │
└─────────────────────────────────────┘

1) [分数 85.2] OpenAI 发布 GPT-5，性能提升 10 倍
   摘要：OpenAI 正式发布 GPT-5，在多项基准测试中性能
         提升 10 倍，支持更长的上下文和更强的推理能力。
   来源：TechCrunch | 时间：2025-11-14 08:30 | 阅读原文 →

2) [分数 78.5] 美联储宣布降息 0.5 个百分点
   摘要：美联储宣布将基准利率下调 0.5 个百分点，这是
         自 2020 年以来的首次降息，市场反应积极。
   来源：Bloomberg | 时间：2025-11-14 07:15 | 阅读原文 →

...
```

## ⚙️ 配置说明

### 核心配置项

| 配置项 | 说明 | 默认值 | 推荐值 |
|--------|------|--------|--------|
| `SCORE_THRESHOLD` | 新闻分数阈值（0-100） | 35 | 30-40（新评分标准下） |
| `TOPK` | 每日发送数量 | 8 | 8 |
| `MAX_ITEMS` | 最多处理数量 | 12 | 12 |
| `TITLE_SIMILARITY_THRESHOLD` | 标题相似度阈值 | 0.75 | 0.75 |
| `ENABLE_DEDUP` | 启用去重 | true | true |
| `DEDUP_WINDOW_DAYS` | 去重时间窗口（天） | 7 | 7 |
| `LANGUAGE` | 邮件语言 | zh | zh (中文) 或 en (英文) |

### 邮件配置

**方式 1: SMTP（推荐 Gmail）**

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password  # 需要在 Google 账户设置中生成
MAIL_FROM=your-email@gmail.com
MAIL_TO=recipient1@example.com,recipient2@example.com
```

**方式 2: SendGrid（推荐生产环境）**

```bash
SENDGRID_API_KEY=SG.xxx
MAIL_FROM=noreply@yourdomain.com
MAIL_TO=recipient@example.com
```

### LLM 提供商

**DeepSeek**（推荐 - 便宜且质量好）：
- 每日推送约 $0.14/月
- 质量足够好

```bash
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com
```

**OpenAI**：
- 更贵但质量更高
- GPT-4 Turbo 效果最好

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
- `SMTP_USER` 或 `SENDGRID_API_KEY`
- `SMTP_PASS`（如果使用 SMTP）
- `MAIL_TO`

### 2. 修改执行时间

编辑 `.github/workflows/daily.yml`：

```yaml
on:
  schedule:
    - cron: '0 12 * * *'  # UTC 12:00 = 北京时间 20:00
```

### 3. 手动触发

在 GitHub Actions 页面可以手动运行 workflow。

## 📁 项目结构

```
news-agent/
├── extensions/
│   └── hotnews-agent/           # 核心代码
│       ├── __init__.py
│       ├── config.py            # 配置管理
│       ├── rss_fetcher.py       # RSS 新闻抓取
│       ├── news_scorer.py       # AI 新闻评分（结构化JSON+确定性计算+批处理校准）
│       ├── newscore_adapter.py  # 数据模型和适配器
│       ├── zh_rewrite.py        # 中文标题改写
│       ├── zh_summary.py        # 中文摘要生成
│       ├── full_text_extractor.py # 全文提取
│       ├── full_text_cache.py   # 全文缓存（SQLite，7天过期）
│       ├── email_push.py        # 邮件推送
│       ├── storage.py           # 历史记录/去重
│       ├── run_artifact.py       # 运行 Artifact 保存（可回测）
│       └── run_daily.py         # 主执行入口
├── .github/
│   └── workflows/
│       └── daily.yml            # GitHub Actions 配置
├── scripts/                     # 工具脚本
├── tests/                       # 单元测试
├── history/                     # 历史记录数据库
│   ├── sent_news.db            # 已发送新闻记录
│   ├── fulltext_cache.db       # 全文缓存
│   └── runs/                    # 每日运行 Artifact
│       └── YYYY-MM-DD.json     # 完整运行数据（可回测）
├── logs/                        # 日志文件
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```

## 🔧 开发指南

### 添加新闻源

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

# 模拟数据测试（不调用 API）
cd extensions/hotnews-agent
python run_daily.py --mock

# 完整流程测试（真实新闻）
python run_daily.py --real
```

## 💰 成本估算

使用 DeepSeek API，每日发送 8 条新闻给 10 个收件人：

- **API 调用**：约 $0.14/月
- **邮件**：免费（SMTP）或免费额度（SendGrid）
- **GitHub Actions**：公开仓库免费

**总计：约 $0.14/月** - 非常便宜！

## 📝 许可

本项目使用 **MIT License**。

### 原创项目

HotNews Agent 是一个完全原创的项目，核心创新包括：

- **分桶式 AI 评分系统**：S/A/B/C 四档分类，结合愤世嫉俗 Persona，减少 AI 幻觉
- **动态阈值调整机制**：自动调整过滤阈值，确保每日邮件送达
- **点击诱饵检测**：智能检测标题夸张但内容空洞的新闻，自动扣分
- **智能去重系统**：基于 URL 规范化和标题相似度的多层去重
- **分层处理架构**：成本优化的两阶段处理，先用摘要评分，再对高分新闻抓取全文
- **RSS 集成**：自动从多个 RSS 源抓取新闻
- **多语言支持**：中文标题改写和摘要生成（可轻松扩展到其他语言）

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

在贡献代码前，请确保：
1. 遵循 PEP 8 代码规范
2. 为新功能添加测试
3. 更新相关文档

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

A: 修改 `TOPK` 配置项。系统会自动调整阈值，确保有足够新闻。

### Q: 如何禁用去重？

A: 设置 `ENABLE_DEDUP=false`。

### Q: Gmail SMTP 报错？

A: 需要在 Google 账户设置中开启"两步验证"并生成"应用专用密码"。

### Q: 新评分标准下收不到足够新闻？

A: 系统会自动降低阈值（最低 30），确保每天都能收到邮件。你也可以手动将 `SCORE_THRESHOLD` 设为 30。

### Q: 如何添加更多收件人？

A: 在 `MAIL_TO` 中用逗号分隔多个邮箱：

```bash
MAIL_TO=email1@example.com,email2@example.com,email3@example.com
```

## 📮 联系方式

- Email: jackysong.2002@gmail.com
- Issues: [GitHub Issues](https://github.com/your-username/news-agent/issues)

---

**Built with ❤️ - 让 AI 帮你筛选每日最重要的新闻**
