# HotNews Agent - 模块说明

这是 HotNews Agent 的核心模块，负责在 NewsScore 评分结果基础上进行后处理和推送。

## 模块职责

### 1. `config.py` - 配置管理
- 从环境变量读取所有配置
- 验证必需配置项
- 提供配置摘要

### 2. `newscore_adapter.py` - NewsScore 集成
- 调用 NewsScore 执行评分
- 加载评分结果（JSON）
- 数据模型定义（NewsScoredItem）
- 提供模拟数据（用于测试）

**约束**：不修改 NewsScore 的评分逻辑，仅消费其输出结果。

### 3. `zh_rewrite.py` - 中文标题改写
- 使用 LLM 将英文标题改写为中文
- 要求：客观、简洁、去夸张
- 字数：15-30 字

### 4. `zh_summary.py` - 中文摘要生成
- 基于标题+片段生成中文摘要
- 要求：事实导向、极度简洁
- 字数：≤50 字

### 5. `email_push.py` - 邮件推送
- 支持 SMTP 和 SendGrid
- 生成 HTML + 纯文本邮件
- 精美的邮件模板

### 6. `storage.py` - 历史记录
- SQLite 数据库存储已推送新闻
- URL 哈希去重
- 定期清理旧记录

### 7. `run_daily.py` - 主执行入口
- 串联整个流程
- 错误处理和日志记录
- 命令行参数支持

## 数据流

```
NewsScore 输出
    ↓
加载评分结果 (newscore_adapter)
    ↓
阈值过滤 (score >= 0.8)
    ↓
去重过滤 (storage)
    ↓
排序 + Top K
    ↓
中文标题改写 (zh_rewrite)
    ↓
中文摘要生成 (zh_summary)
    ↓
邮件推送 (email_push)
    ↓
记录历史 (storage)
```

## 使用示例

### 单独使用各模块

```python
from config import config
from newscore_adapter import NewsScoreAdapter
from zh_rewrite import ChineseTitleRewriter
from zh_summary import ChineseSummaryGenerator
from email_push import EmailPusher

# 1. 获取评分结果
adapter = NewsScoreAdapter()
scored_items = adapter.get_scored_news()

# 2. 过滤
filtered = [item for item in scored_items if item.score >= 0.8]

# 3. 中文化
rewriter = ChineseTitleRewriter()
summarizer = ChineseSummaryGenerator()

for item in filtered:
    item.title_zh = rewriter.rewrite_title(item.title)
    item.summary_zh = summarizer.generate_summary(item.title, item.title_zh)

# 4. 推送
pusher = EmailPusher()
pusher.send_daily_digest(filtered)
```

### 完整流程

```python
from run_daily import main

# 使用模拟数据测试
main(use_mock_data=True)

# 完整运行
main(use_mock_data=False)
```

## 扩展点

### 添加新的数据源

在 NewsScore 项目中按其规范添加，不需要修改本模块。

### 自定义提示词

编辑 `zh_rewrite.py` 和 `zh_summary.py` 中的提示词构建函数。

### 更换邮件服务

在 `email_push.py` 中添加新的发送方法。

### 添加推送渠道

参考 `email_push.py`，创建新的推送器（如 Telegram、Slack 等）。

## 注意事项

1. **不修改 NewsScore**：所有评分逻辑保持原样
2. **最小依赖**：仅依赖必要的第三方库
3. **错误处理**：每个模块都有完善的异常处理
4. **日志记录**：使用 loguru 记录详细日志
5. **配置驱动**：所有参数通过环境变量配置

## 开发建议

1. 先使用 `--mock` 模式测试
2. 逐步添加真实配置
3. 查看 `logs/` 目录下的日志
4. 使用 `history/` 数据库检查去重状态





