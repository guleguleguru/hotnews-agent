# 测试说明

## 运行测试

### 安装测试依赖

```bash
pip install pytest pytest-cov
```

### 运行所有测试

```bash
pytest tests/
```

### 运行指定测试文件

```bash
pytest tests/test_config.py
```

### 查看覆盖率

```bash
pytest --cov=extensions/hotnews-agent tests/
```

### 生成覆盖率报告

```bash
pytest --cov=extensions/hotnews-agent --cov-report=html tests/
```

然后在浏览器中打开 `htmlcov/index.html`。

## 测试结构

```
tests/
├── __init__.py
├── test_config.py        # 配置模块测试
├── test_storage.py       # 存储模块测试
├── test_zh_rewrite.py    # 标题改写测试（需要 API Key）
├── test_zh_summary.py    # 摘要生成测试（需要 API Key）
└── test_email_push.py    # 邮件推送测试（需要邮件配置）
```

## 注意事项

1. **API Key 依赖**
   - 涉及 LLM 调用的测试需要有效的 API Key
   - 可以使用 Mock 来避免实际调用

2. **邮件测试**
   - 邮件推送测试需要有效的邮件配置
   - 建议使用专门的测试邮箱

3. **环境隔离**
   - 测试使用临时数据库，不影响实际数据
   - 清理工作会自动执行

## 添加新测试

1. 在 `tests/` 目录下创建 `test_*.py` 文件
2. 创建测试类（以 `Test` 开头）
3. 编写测试方法（以 `test_` 开头）
4. 运行测试确保通过

### 示例

```python
import pytest

class TestMyModule:
    def test_something(self):
        result = my_function()
        assert result == expected_value
    
    @pytest.fixture
    def setup_data(self):
        # 准备测试数据
        yield data
        # 清理
```

## CI/CD 集成

测试可以集成到 GitHub Actions 中：

```yaml
- name: Run tests
  run: |
    pip install pytest pytest-cov
    pytest tests/ --cov=extensions/hotnews-agent
```





