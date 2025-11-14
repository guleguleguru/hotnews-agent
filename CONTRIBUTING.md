# Contributing Guide

Thanks for your interest in HotNews Agent!

## 🎯 Contribution Principles

Before contributing, please follow these principles:

1. **Don't modify NewsScore's scoring logic**
   - The core constraint is to reuse NewsScore's scoring algorithm
   - Only add features on top, don't modify the internal implementation

2. **Minimal invasive design**
   - Interface with NewsScore through standard interfaces/outputs
   - Keep modules decoupled and maintainable

3. **Maintain code quality**
   - Follow PEP 8 code style
   - Add necessary comments and docstrings
   - Write unit tests

## 📝 Submission Process

### 1. Fork the project

Click the "Fork" button in the top right to copy the project to your account.

### 2. Clone to local

```bash
git clone https://github.com/your-username/hotnews-agent.git
cd hotnews-agent
```

### 3. Create a branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 4. Make changes

- Modify code
- Add tests
- Update documentation

### 5. Commit changes

```bash
git add .
git commit -m "feat: add some feature"
```

Commit message format:
- `feat: new feature`
- `fix: bug fix`
- `docs: documentation update`
- `style: code formatting`
- `refactor: code refactoring`
- `test: test related`
- `chore: build/tool related`

### 6. Push to GitHub

```bash
git push origin feature/your-feature-name
```

### 7. Create Pull Request

Create a Pull Request on GitHub describing your changes.

## 🧪 Testing

Before submitting a PR, make sure:

```bash
# Code formatting check
black extensions/hotnews-agent/
flake8 extensions/hotnews-agent/

# Run tests
pytest tests/

# Test full workflow
cd extensions/hotnews-agent
python run_daily.py --mock
```

## 📚 Documentation

If your changes involve user-visible features, please update:

- `README.md` - Main documentation
- `extensions/hotnews-agent/README.md` - Module documentation
- Docstrings in code

## 🤔 Suggested Contribution Areas

### Easy tasks

- Fix documentation errors
- Improve error messages
- Add usage examples
- Improve email template styling

### Medium difficulty

- Add new delivery channels (Telegram, Slack, etc.)
- Improve deduplication algorithm (use embedding similarity)
- Add topic filtering
- Optimize prompts

### Advanced tasks

- Add web interface (configuration/view history)
- Support multi-language output
- Add event clustering
- Performance optimization

## ❓ Questions and Discussion

If you have any questions or suggestions, feel free to:

1. Open an Issue for discussion
2. Comment on existing Issues
3. Join discussion channels (if available)

## 📄 License

By submitting a PR, you agree to release your contribution under the MIT License.

---

Thanks again for your contribution! 🎉
