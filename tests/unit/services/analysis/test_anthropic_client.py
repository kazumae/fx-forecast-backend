"""
Anthropic APIクライアントの単体テスト
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import os

from src.services.analysis.anthropic_client import AnthropicAnalysisClient, RateLimitInfo


@pytest.fixture
def mock_env_vars(monkeypatch):
    """環境変数のモック"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-api-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")


@pytest.fixture
def mock_anthropic_client():
    """Anthropicクライアントのモック"""
    with patch("src.services.analysis.anthropic_client.AsyncAnthropic") as mock:
        yield mock


class TestAnthropicAnalysisClient:
    """AnthropicAnalysisClientのテスト"""
    
    def test_init_success(self, mock_env_vars, mock_anthropic_client):
        """初期化の正常系テスト"""
        client = AnthropicAnalysisClient()
        
        assert client.model == "claude-3-opus-20240229"
        assert client.max_tokens == 4096
        assert client.temperature == 0.7
        assert client.rate_limiter.requests_per_minute == 50
    
    def test_init_no_api_key(self, monkeypatch, mock_anthropic_client):
        """APIキーがない場合のテスト"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY environment variable is not set"):
            AnthropicAnalysisClient()
    
    @pytest.mark.asyncio
    async def test_analyze_market_success(self, mock_env_vars, mock_anthropic_client):
        """市場分析の正常系テスト"""
        # モックレスポンス設定
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="市場は上昇トレンドです。")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.model = "claude-3-opus-20240229"
        
        mock_instance = AsyncMock()
        mock_instance.messages.create.return_value = mock_response
        mock_anthropic_client.return_value = mock_instance
        
        client = AnthropicAnalysisClient()
        client.client = mock_instance
        
        # テスト実行
        result = await client.analyze_market(
            system_prompt="あなたは金融アナリストです",
            user_prompt="現在の市場を分析してください"
        )
        
        # 検証
        assert result["success"] is True
        assert result["content"] == "市場は上昇トレンドです。"
        assert result["usage"]["input_tokens"] == 100
        assert result["usage"]["output_tokens"] == 50
        assert result["usage"]["total_tokens"] == 150
        assert result["model"] == "claude-3-opus-20240229"
        assert result["attempt"] == 1
    
    @pytest.mark.asyncio
    async def test_analyze_market_retry_success(self, mock_env_vars, mock_anthropic_client):
        """リトライで成功するケース"""
        mock_instance = AsyncMock()
        
        # 1回目は失敗、2回目で成功
        mock_instance.messages.create.side_effect = [
            Exception("Network error"),
            MagicMock(
                content=[MagicMock(text="成功しました")],
                usage=MagicMock(input_tokens=100, output_tokens=50),
                model="claude-3-opus-20240229"
            )
        ]
        
        mock_anthropic_client.return_value = mock_instance
        
        client = AnthropicAnalysisClient()
        client.client = mock_instance
        
        result = await client.analyze_market(
            system_prompt="test",
            user_prompt="test",
            max_retries=2
        )
        
        assert result["success"] is True
        assert result["content"] == "成功しました"
        assert result["attempt"] == 2
    
    @pytest.mark.asyncio
    async def test_analyze_market_all_retries_failed(self, mock_env_vars, mock_anthropic_client):
        """全てのリトライが失敗するケース"""
        mock_instance = AsyncMock()
        mock_instance.messages.create.side_effect = Exception("API Error")
        mock_anthropic_client.return_value = mock_instance
        
        client = AnthropicAnalysisClient()
        client.client = mock_instance
        
        result = await client.analyze_market(
            system_prompt="test",
            user_prompt="test",
            max_retries=2
        )
        
        assert result["success"] is False
        assert result["error"] == "API Error"
        assert result["error_type"] == "Exception"
        assert result["attempts"] == 2
    
    @pytest.mark.asyncio
    async def test_validate_api_key_success(self, mock_env_vars, mock_anthropic_client):
        """APIキー検証の正常系"""
        mock_instance = AsyncMock()
        mock_instance.messages.create.return_value = MagicMock()
        mock_anthropic_client.return_value = mock_instance
        
        client = AnthropicAnalysisClient()
        client.client = mock_instance
        
        result = await client.validate_api_key()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_api_key_failure(self, mock_env_vars, mock_anthropic_client):
        """APIキー検証の失敗"""
        mock_instance = AsyncMock()
        mock_instance.messages.create.side_effect = Exception("Invalid API key")
        mock_anthropic_client.return_value = mock_instance
        
        client = AnthropicAnalysisClient()
        client.client = mock_instance
        
        result = await client.validate_api_key()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_rate_limit_wait(self, mock_env_vars, mock_anthropic_client):
        """レート制限の待機テスト"""
        client = AnthropicAnalysisClient()
        
        # レート制限に達するまでリクエストを記録
        now = datetime.now(timezone.utc)
        client.rate_limiter.request_times = [now for _ in range(50)]
        
        # 待機時間を短くしてテスト
        with patch("asyncio.sleep") as mock_sleep:
            await client._wait_for_rate_limit()
            mock_sleep.assert_called_once()
    
    def test_get_token_cost(self, mock_env_vars, mock_anthropic_client):
        """トークンコスト計算のテスト"""
        client = AnthropicAnalysisClient()
        
        usage = {
            "input_tokens": 1000,
            "output_tokens": 500
        }
        
        cost = client.get_token_cost(usage)
        
        # Input: 1000 tokens * $15/1M = $0.015
        # Output: 500 tokens * $75/1M = $0.0375
        # Total: $0.0525
        assert cost == pytest.approx(0.0525, rel=1e-6)
    
    def test_rate_limit_info_dataclass(self):
        """RateLimitInfoデータクラスのテスト"""
        rate_limit = RateLimitInfo()
        assert rate_limit.requests_per_minute == 50
        assert rate_limit.request_times == []
        
        # カスタム値でのインスタンス化
        custom_rate_limit = RateLimitInfo(requests_per_minute=100)
        assert custom_rate_limit.requests_per_minute == 100