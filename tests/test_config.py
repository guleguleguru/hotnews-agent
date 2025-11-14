"""
配置模块测试
"""

import os
import sys
from pathlib import Path

# 添加 agent 目录到路径
agent_dir = Path(__file__).parent.parent / "extensions" / "hotnews-agent"
sys.path.insert(0, str(agent_dir))

import pytest
from config import Config


class TestConfig:
    """配置测试类"""
    
    def test_default_values(self):
        """测试默认值"""
        assert Config.SCORE_THRESHOLD == float(os.getenv("SCORE_THRESHOLD", "0.8"))
        assert Config.TOPK == int(os.getenv("TOPK", "8"))
        assert Config.TIMEZONE == os.getenv("TIMEZONE", "America/New_York")
    
    def test_validate_missing_keys(self, monkeypatch):
        """测试缺少必需配置时的验证"""
        # 清空必需的配置
        monkeypatch.setattr(Config, "OPENAI_API_KEY", "")
        monkeypatch.setattr(Config, "MAIL_TO", "")
        
        # 验证应该失败
        assert Config.validate() is False
    
    def test_get_summary(self):
        """测试配置摘要生成"""
        summary = Config.get_summary()
        assert "OpenAI Model" in summary
        assert "Score Threshold" in summary





