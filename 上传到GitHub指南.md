# 🚀 上传到 GitHub 指南

## 📋 准备工作

### 1. 清理不需要的文件

在 `hotnews-agent-open-source` 目录下，删除以下文件夹（如果存在）：

```bash
# Windows PowerShell
Remove-Item -Recurse -Force extensions\hotnews-agent\history
Remove-Item -Recurse -Force extensions\hotnews-agent\logs
Remove-Item -Recurse -Force extensions\hotnews-agent\__pycache__
```

或者手动删除：
- `extensions/hotnews-agent/history/`
- `extensions/hotnews-agent/logs/`
- `extensions/hotnews-agent/__pycache__/`

### 2. 确认文件结构

最终的文件结构应该是：

```
hotnews-agent-open-source/
├── .github/
│   └── workflows/
│       └── daily.yml
├── extensions/
│   └── hotnews-agent/
│       ├── __init__.py
│       ├── config.py
│       ├── email_push.py
│       ├── full_text_extractor.py
│       ├── news_scorer.py
│       ├── newscore_adapter.py
│       ├── README.md
│       ├── rss_fetcher.py
│       ├── run_daily.py
│       ├── storage.py
│       ├── zh_rewrite.py
│       └── zh_summary.py
├── scripts/
│   ├── check_history.py
│   ├── clean_history.py
│   ├── test_email.py
│   ├── test_fulltext.py
│   └── test_real_news.py
├── tests/
│   ├── __init__.py
│   ├── README.md
│   ├── test_config.py
│   └── test_storage.py
├── .gitignore
├── CONTRIBUTING.md
├── env.example
├── LICENSE
├── README.md
└── requirements.txt
```

## 🔧 初始化 Git 仓库

### 1. 进入项目目录

```bash
cd hotnews-agent-open-source
```

### 2. 初始化 Git

```bash
git init
```

### 3. 添加所有文件

```bash
git add .
```

### 4. 提交

```bash
git commit -m "Initial commit: HotNews Agent - AI-powered daily news digest system"
```

## 📤 创建 GitHub 仓库并推送

### 1. 在 GitHub 上创建新仓库

1. 登录 GitHub
2. 点击右上角的 "+" → "New repository"
3. 填写仓库信息：
   - **Repository name**: `hotnews-agent`（或你喜欢的名字）
   - **Description**: `AI-powered daily news digest system based on NewsScore scoring standards`
   - **Visibility**: Public（开源项目）
   - **不要**勾选：
     - ❌ Add a README file（我们已经有了）
     - ❌ Add .gitignore（我们已经有了）
     - ❌ Choose a license（我们已经有了）

4. 点击 "Create repository"

### 2. 连接本地仓库到 GitHub

GitHub 会显示推送命令，类似这样：

```bash
git remote add origin https://github.com/your-username/hotnews-agent.git
git branch -M main
git push -u origin main
```

**如果遇到认证问题**：

使用 Personal Access Token（PAT）：
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. 生成新 token，勾选 `repo` 和 `workflow` 权限
3. 使用 token 作为密码

或者使用 SSH：
```bash
git remote set-url origin git@github.com:your-username/hotnews-agent.git
```

### 3. 推送代码

```bash
git push -u origin main
```

## ✅ 推送后的操作

### 1. 配置 GitHub Secrets（用于 GitHub Actions）

1. 进入仓库 → Settings → Secrets and variables → Actions
2. 点击 "New repository secret"
3. 添加以下 Secrets：

**必需的 Secrets：**
- `OPENAI_API_KEY` - 你的 LLM API 密钥
- `SMTP_USER` - 邮件发送账户
- `SMTP_PASS` - 邮件发送密码（Gmail 使用应用专用密码）
- `MAIL_TO` - 收件人邮箱（多个用逗号分隔）

**可选的 Secrets（如果不设置，使用默认值）：**
- `OPENAI_MODEL` - 默认：`deepseek-chat`
- `OPENAI_BASE_URL` - 默认：`https://api.deepseek.com`
- `SMTP_HOST` - 默认：`smtp.gmail.com`
- `SMTP_PORT` - 默认：`587`
- `MAIL_FROM` - 默认：与 `SMTP_USER` 相同
- `SCORE_THRESHOLD` - 默认：`0.4`
- `TOPK` - 默认：`8`
- `MAX_ITEMS` - 默认：`12`

### 2. 测试 GitHub Actions

1. 进入仓库 → Actions
2. 点击 "Daily HotNews Digest" workflow
3. 点击 "Run workflow" → "Run workflow"（手动触发）
4. 查看运行日志，确认一切正常

### 3. 更新仓库描述和主题

在仓库设置中添加：
- **Topics**: `news`, `ai`, `rss`, `email`, `automation`, `python`, `newsletter`
- **Website**: （如果有）

## 📝 后续维护

### 更新代码

```bash
# 1. 在原始项目目录修改代码
cd "e:\mot\news agnet"

# 2. 复制更新的文件到开源版本
# （手动复制或使用脚本）

# 3. 在开源版本目录提交
cd hotnews-agent-open-source
git add .
git commit -m "描述你的更改"
git push
```

### 处理 Issues 和 Pull Requests

- 定期查看 Issues，回复问题
- 审查 Pull Requests，合并有价值的贡献
- 更新文档，保持项目活跃

## 🎉 完成！

你的开源项目已经准备好了！

**项目亮点：**
- ✅ 完整的 AI 新闻评分系统
- ✅ 智能去重（URL + 标题相似度）
- ✅ 精美的邮件模板
- ✅ GitHub Actions 自动执行
- ✅ 详细的文档和示例
- ✅ MIT 许可证

**下一步：**
1. 分享项目链接
2. 在 README 中添加 Star 和 Fork 按钮
3. 考虑添加 GitHub Pages 文档站点
4. 在社交媒体上宣传项目

---

**祝你的开源项目成功！** 🚀

