"""
存储模块测试
"""

import sys
from pathlib import Path
import tempfile
import os

# 添加 agent 目录到路径
agent_dir = Path(__file__).parent.parent / "extensions" / "hotnews-agent"
sys.path.insert(0, str(agent_dir))

import pytest
from storage import HistoryStorage


class TestHistoryStorage:
    """历史存储测试类"""
    
    @pytest.fixture
    def temp_storage(self):
        """临时存储 fixture"""
        # 创建临时数据库
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            temp_db = f.name
        
        storage = HistoryStorage(db_path=temp_db)
        yield storage
        
        # 清理
        if os.path.exists(temp_db):
            os.unlink(temp_db)
    
    def test_hash_url(self):
        """测试 URL 哈希"""
        url = "https://example.com/news/123"
        hash1 = HistoryStorage.hash_url(url)
        hash2 = HistoryStorage.hash_url(url)
        
        # 相同 URL 应该产生相同哈希
        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 哈希长度
    
    def test_mark_and_check_sent(self, temp_storage):
        """测试标记和检查已发送"""
        url = "https://example.com/news/123"
        title = "Test News"
        score = 0.95
        
        # 初始应该未发送
        assert temp_storage.is_sent(url) is False
        
        # 标记为已发送
        temp_storage.mark_as_sent(url, title, score)
        
        # 现在应该已发送
        assert temp_storage.is_sent(url) is True
    
    def test_get_stats(self, temp_storage):
        """测试统计信息"""
        # 添加一些记录
        temp_storage.mark_as_sent("https://example.com/1", "News 1", 0.9)
        temp_storage.mark_as_sent("https://example.com/2", "News 2", 0.8)
        
        stats = temp_storage.get_stats()
        
        assert stats["total_count"] == 2
        assert stats["recent_7days_count"] == 2





