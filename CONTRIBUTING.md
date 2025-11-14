# 贡献指南

感谢你对 HotNews Agent 项目的关注！

## 🎯 贡献原则

在贡献代码前，请务必遵循以下原则：

1. **不修改 NewsScore 的评分逻辑**
   - 本项目的核心约束是复用 NewsScore 的评分算法
   - 只在其外层添加功能，不修改其内部实现

2. **最小侵入性设计**
   - 通过标准接口/输出对接 NewsScore
   - 保持模块解耦，易于维护

3. **保持代码质量**
   - 遵循 PEP 8 代码规范
   - 添加必要的注释和文档字符串
   - 编写单元测试

## 📝 提交流程

### 1. Fork 项目

点击右上角的 "Fork" 按钮，将项目复制到你的账户下。

### 2. 克隆到本地

```bash
git clone https://github.com/your-username/hotnews-agent.git
cd hotnews-agent
```

### 3. 创建分支

```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/your-bug-fix
```

### 4. 进行修改

- 修改代码
- 添加测试
- 更新文档

### 5. 提交更改

```bash
git add .
git commit -m "feat: 添加某某功能"
```

提交信息格式：
- `feat: 新功能`
- `fix: 修复 bug`
- `docs: 文档更新`
- `style: 代码格式调整`
- `refactor: 代码重构`
- `test: 测试相关`
- `chore: 构建/工具相关`

### 6. 推送到 GitHub

```bash
git push origin feature/your-feature-name
```

### 7. 创建 Pull Request

在 GitHub 上创建 Pull Request，描述你的更改。

## 🧪 测试

在提交 PR 前，请确保：

```bash
# 代码格式检查
black extensions/hotnews-agent/
flake8 extensions/hotnews-agent/

# 运行测试
pytest tests/

# 测试完整流程
cd extensions/hotnews-agent
python run_daily.py --mock
```

## 📚 文档

如果你的更改涉及用户可见的功能，请更新：

- `README.md` - 主文档
- `extensions/hotnews-agent/README.md` - 模块说明
- 代码中的文档字符串

## 🤔 建议的贡献方向

### 容易上手的任务

- 修复文档错误
- 改进错误提示信息
- 添加使用示例
- 改进邮件模板样式

### 中等难度任务

- 添加新的推送渠道（Telegram、Slack 等）
- 改进去重算法（使用 embedding 相似度）
- 添加主题过滤功能
- 优化提示词

### 高难度任务

- 添加 Web 界面（配置/查看历史）
- 支持多语言输出
- 添加事件聚类功能
- 性能优化

## ❓ 问题讨论

如果你有任何疑问或建议，欢迎：

1. 提交 Issue 讨论
2. 在现有 Issue 下评论
3. 加入讨论频道（如果有）

## 📄 许可

通过提交 PR，你同意将你的贡献以 MIT License 发布。

---

再次感谢你的贡献！🎉





