# 🔥 HotNews Agent

> A daily news digest system that uses AI to score and filter news, then sends you the best stories via email.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## 📖 What it does

I built this because I was tired of sifting through dozens of news articles every morning. HotNews Agent:

- ✅ **RSS Fetching**: Automatically fetches news from multiple RSS feeds
- ✅ **AI Scoring**: Uses LLM to score news quality with optimized tier-based scoring (0-100 scale)
- ✅ **Smart Filtering**: Only sends high-scoring articles (with dynamic threshold adjustment)
- ✅ **Title Rewriting**: Converts English titles to Chinese (you can modify this)
- ✅ **Summary Generation**: Creates concise, fact-oriented summaries (supports full-text extraction)
- ✅ **Email Delivery**: Beautiful daily digest emails (supports multiple recipients)
- ✅ **Auto Deduplication**: Smart deduplication based on URL and title similarity
- ✅ **Scheduled Execution**: GitHub Actions runs automatically

## ✨ Key Features

### 1. Optimized AI Scoring System

Uses **Tier-based Scoring + Cynical Persona + Clickbait Detection**:

- **Tier-based Scoring**: S/A/B/C classification reduces AI hallucinations
  - S Tier (90-100): Industry-shaking events
  - A Tier (70-89): Major updates with high value
  - B Tier (40-69): Regular news
  - C Tier (0-39): Noise/trash
- **Cynical Persona**: Defaults to low scores, only truly important news gets high scores
- **Clickbait Penalty**: Detects sensational titles with empty content, automatically deducts points

### 2. Dynamic Threshold Adjustment

- Automatically lowers threshold if filtered articles are fewer than target
- Minimum threshold protection (≥30) ensures quality
- Smart fallback mechanism ensures you always receive enough emails daily

### 3. Smart Deduplication

- **URL Deduplication**: Normalizes URLs, removes tracking parameters
- **Title Similarity**: Uses text similarity algorithm to remove duplicate articles from different sources
- **History Tracking**: SQLite database records sent articles to avoid duplicates

### 4. Two-Layer Processing (Cost Optimization)

- **Layer 1**: Scores all articles using snippets
- **Layer 2**: Only fetches full text for high-scoring articles to generate quality summaries
- **Cost Control**: Avoids unnecessary full-text fetching and API calls

## 🏗 How it works

```
┌──────────────────────────────────────────────────────────────┐
│                      HotNews Agent                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ RSS Fetch│→│ AI Score  │→│ Filter   │→│ Dedupe    │   │
│  │          │  │(Tier-based│  │(Dynamic) │  │(Smart)   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Full Text │→│ Rewrite   │→│ Summary  │→│ Email     │   │
│  │(Top N)   │  │(Chinese) │  │(Chinese) │  │(Digest)  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└──────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/guleguleguru/hotnews-agent.git
cd hotnews-agent
```

### 2. Install dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `env.example` to `.env` and fill in your settings:

```bash
cp env.example .env
```

You'll need:
- An LLM API key (DeepSeek is cheap, OpenAI works too)
- SMTP credentials (Gmail/Outlook) or SendGrid API key
- Recipient email address(es)

Example `.env`:

```bash
# LLM API (DeepSeek is recommended - much cheaper)
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
MAIL_FROM=your-email@gmail.com
MAIL_TO=recipient@example.com

# Filtering (recommended for new scoring system)
SCORE_THRESHOLD=35  # 0-100 scale, 35=standard, 30=more articles, 40=strict
TOPK=8  # Number of articles to send daily
MAX_ITEMS=12  # Max articles to process (cost control)
```

### 4. Run tests

```bash
cd extensions/hotnews-agent

# Test with mock data (no API calls)
python run_daily.py --mock

# Run with real news
python run_daily.py --real
```

## 📧 Email Example

Here's what the daily digest looks like:

```
┌─────────────────────────────────────┐
│     📰 Daily HotNews Digest         │
│        2025-11-14                   │
└─────────────────────────────────────┘

1) [Score 85.2] OpenAI Releases GPT-5 with 10x Performance Boost
   Summary: OpenAI officially released GPT-5, showing 10x 
            performance improvement in multiple benchmarks, 
            with support for longer context and stronger 
            reasoning capabilities.
   Source: TechCrunch | Time: 2025-11-14 08:30 | Read more →

2) [Score 78.5] Fed Announces 0.5% Rate Cut
   Summary: The Federal Reserve announced a 0.5% cut in 
            benchmark interest rates, the first rate cut 
            since 2020, with positive market reactions.
   Source: Bloomberg | Time: 2025-11-14 07:15 | Read more →

...
```

## ⚙️ Configuration

### Core Settings

| Setting | Description | Default | Recommended |
|---------|-------------|---------|-------------|
| `SCORE_THRESHOLD` | Minimum score to include (0-100) | 35 | 30-40 (for new scoring system) |
| `TOPK` | Articles per digest | 8 | 8 |
| `MAX_ITEMS` | Max articles to process | 12 | 12 |
| `TITLE_SIMILARITY_THRESHOLD` | Dedup similarity | 0.75 | 0.75 |
| `ENABLE_DEDUP` | Enable deduplication | true | true |
| `DEDUP_WINDOW_DAYS` | Dedup time window (days) | 7 | 7 |

### Email Setup

**Option 1: SMTP (Gmail/Outlook)**

Gmail requires an app password (not your regular password). Get it from Google Account settings → Security → App passwords.

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
MAIL_FROM=your-email@gmail.com
MAIL_TO=recipient1@example.com,recipient2@example.com
```

**Option 2: SendGrid (Recommended for production)**

Better for production. Free tier gives you 100 emails/day, which is plenty.

```bash
SENDGRID_API_KEY=SG.xxx
MAIL_FROM=noreply@yourdomain.com
MAIL_TO=recipient@example.com
```

### LLM Providers

**DeepSeek** (recommended - very cheap):
- ~$0.14/month for daily digests
- Good quality for this use case

```bash
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com
```

**OpenAI**:
- More expensive but higher quality
- GPT-4 Turbo works great if you want the best results

```bash
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_BASE_URL=https://api.openai.com/v1
```

## 🤖 GitHub Actions Setup

The repo includes a GitHub Actions workflow that runs daily. To set it up:

### 1. Configure Secrets

Add secrets in your repo settings:

```
Settings → Secrets and variables → Actions → New repository secret
```

Required secrets:
- `OPENAI_API_KEY`
- `SMTP_USER` or `SENDGRID_API_KEY`
- `SMTP_PASS` (if using SMTP)
- `MAIL_TO`
- (Other config items as needed)

### 2. Adjust Schedule

Edit `.github/workflows/daily.yml`:

```yaml
on:
  schedule:
    - cron: '0 12 * * *'  # Daily at 12:00 UTC (20:00 Beijing time)
```

### 3. Manual Trigger

You can also trigger the workflow manually from the GitHub Actions page.

## 📁 Project Structure

```
hotnews-agent/
├── extensions/
│   └── hotnews-agent/           # Core code
│       ├── __init__.py
│       ├── config.py            # Configuration management
│       ├── rss_fetcher.py       # RSS news fetching
│       ├── news_scorer.py       # AI news scoring (Tier-based + Persona + Clickbait)
│       ├── newscore_adapter.py  # Data models and adapters
│       ├── zh_rewrite.py        # Title rewriting
│       ├── zh_summary.py        # Summary generation
│       ├── full_text_extractor.py # Full-text extraction
│       ├── email_push.py        # Email delivery
│       ├── storage.py           # History/deduplication
│       └── run_daily.py         # Main entry point
├── .github/
│   └── workflows/
│       └── daily.yml            # GitHub Actions config
├── scripts/                     # Utility scripts
├── tests/                       # Unit tests
├── requirements.txt
├── .gitignore
├── LICENSE
├── CONTRIBUTING.md
└── README.md
```

## 🔧 Development Guide

### Add News Sources

Edit `extensions/hotnews-agent/rss_fetcher.py`:

```python
DEFAULT_SOURCES = [
    {"name": "Your News Source", "url": "https://example.com/rss", "category": "tech"},
    # ...
]
```

### Customize Email Template

Edit `extensions/hotnews-agent/email_push.py` - the `_build_html_body()` method.

### Adjust Prompts

- Title rewriting: `zh_rewrite.py` → `_build_rewrite_prompt()`
- Summary generation: `zh_summary.py` → `_build_summary_prompt()`
- News scoring: `news_scorer.py` → `SCORE_PROMPT_TEMPLATE`

## 🧪 Testing

```bash
# Unit tests
pytest tests/

# Mock data test (no API calls)
cd extensions/hotnews-agent
python run_daily.py --mock

# Full test with real news
python run_daily.py --real
```

## 💰 Cost Estimate

Using DeepSeek API, sending 8 articles daily to 10 recipients:

- **API calls**: ~$0.14/month
- **Email**: Free (SMTP) or free tier (SendGrid)
- **GitHub Actions**: Free for public repos

**Total: ~$0.14/month** - pretty cheap for a daily news digest.

## 📝 License & Attribution

This project uses **MIT License**.

### Important Notice

The news scoring logic is based on [NewsScore](https://github.com/themaximalist/newsscore) (by [@themaximalist](https://github.com/themaximalist)). This project implements a Python version that doesn't depend on the original Node.js implementation, but strictly follows the same scoring standards.

We only added on top:
- RSS fetching (independent of NewsScore)
- Optimized scoring system (Tier-based + Persona + Clickbait detection)
- Dynamic threshold adjustment
- Title rewriting and summary generation (currently in Chinese)
- Email delivery
- Scheduled execution

NewsScore also uses MIT License.

## 🤝 Contributing

Pull requests welcome! Just make sure to:
- Follow PEP 8
- Add tests for new features
- Update docs if needed

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## ❓ FAQ

### Q: Can I use other LLM providers?

A: Yes, any OpenAI-compatible API works. Just change `OPENAI_BASE_URL` and `OPENAI_MODEL`.

Examples:

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

### Q: How do I adjust the number of articles?

A: Modify the `TOPK` setting in your `.env` file. The system will automatically adjust the threshold to ensure enough articles.

### Q: How do I disable deduplication?

A: Set `ENABLE_DEDUP=false` in your `.env`.

### Q: Gmail SMTP not working?

A: You need an app password, not your regular password. Enable 2FA first, then generate an app password from Google Account settings → Security → App passwords.

### Q: How do I add more recipients?

A: Comma-separate emails in `MAIL_TO`:

```bash
MAIL_TO=email1@example.com,email2@example.com,email3@example.com
```

### Q: Not getting enough articles with new scoring system?

A: The system automatically lowers the threshold (minimum 30) to ensure you always receive emails. You can also manually set `SCORE_THRESHOLD=30`.

### Q: How do I change the digest frequency?

A: Edit the cron schedule in `.github/workflows/daily.yml`.

## 📮 Contact

- Email: jackysong.2002@gmail.com
- Issues: [GitHub Issues](https://github.com/guleguleguru/hotnews-agent/issues)

---

**Built with ❤️ based on [NewsScore](https://github.com/themaximalist/newsscore)**

If you find this useful, consider giving it a star ⭐
