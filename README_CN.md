# 🔥 HotNews Agent - 中文说明

> 基于 AI 评分的每日热点新闻推送系统

## 📖 项目简介

HotNews Agent 是一个智能新闻推送系统，能够自动抓取、评分、过滤并推送高质量新闻。

## ✨ 核心功能

- 🤖 **AI 评分**：使用 LLM 对新闻进行质量评分
- 📰 **RSS 抓取**：从多个新闻源自动抓取最新新闻
- 🎯 **智能过滤**：仅推送高分新闻
- 🇨🇳 **中文改写**：自动将英文标题改写为中文
- 📝 **中文摘要**：生成简洁的事实导向摘要
- 📧 **邮件推送**：精美的每日简报邮件
- 🔄 **智能去重**：基于 URL 和标题相似度
- ⏰ **定时执行**：GitHub Actions 自动运行

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/hotnews-agent.git
cd hotnews-agent
```

### 2. 安装依赖

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp env.example .env
# 编辑 .env 文件，填写你的配置
```

### 4. 运行

```bash
cd extensions/hotnews-agent
python run_daily.py --real
```

## 💰 成本

使用 DeepSeek API，每天推送 8 条新闻给 10 个邮箱：
- **API 成本**：约 0.14 元/月
- **邮件成本**：0 元（SMTP 免费）
- **总计**：约 0.14 元/月 ✅

## 📚 详细文档

请查看 [README.md](README.md) 获取完整文档。

## 📄 许可证

MIT License

---

**基于 [NewsScore](https://github.com/themaximalist/newsscore) 构建**

