"""
Anthropic APIクライアントの結合テスト
"""
import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock

from src.services.analysis.anthropic_client import AnthropicAnalysisClient


class TestAnthropicAnalysisClientIntegration:
    """AnthropicAnalysisClientの結合テスト"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set"
    )
    async def test_real_api_call(self):
        """実際のAPIを使用したテスト（APIキーが設定されている場合のみ）"""
        client = AnthropicAnalysisClient()
        
        # 簡単なテストプロンプト
        result = await client.analyze_market(
            system_prompt="You are a helpful assistant. Keep responses very brief.",
            user_prompt="Say 'test successful' in 3 words or less."
        )
        
        assert result["success"] is True
        assert len(result["content"]) > 0
        assert result["usage"]["input_tokens"] > 0
        assert result["usage"]["output_tokens"] > 0
    
    @pytest.mark.asyncio
    async def test_full_market_analysis_flow(self, monkeypatch):
        """市場分析の完全なフローテスト（モック使用）"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        
        with patch("src.services.analysis.anthropic_client.AsyncAnthropic") as mock_anthropic:
            # モックレスポンス
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="""
{
    "market_trend": "bullish",
    "confidence": 0.85,
    "key_levels": {
        "support": 3240.00,
        "resistance": 3265.00
    },
    "recommendation": "BUY",
    "risk_level": "medium"
}
            """)]
            mock_response.usage.input_tokens = 1500
            mock_response.usage.output_tokens = 200
            mock_response.model = "claude-3-opus-20240229"
            
            mock_instance = AsyncMock()
            mock_instance.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_instance
            
            # テスト実行
            client = AnthropicAnalysisClient()
            client.client = mock_instance
            
            system_prompt = """
            You are an expert forex analyst. Analyze the provided market data 
            and return a JSON response with your analysis.
            """
            
            user_prompt = """
            Analyze XAUUSD with the following data:
            - Current price: 3250.50
            - 24h change: +0.85%
            - RSI: 65
            - MACD: Bullish crossover
            """
            
            result = await client.analyze_market(system_prompt, user_prompt)
            
            # 検証
            assert result["success"] is True
            assert "market_trend" in result["content"]
            assert "bullish" in result["content"]
            assert result["usage"]["total_tokens"] == 1700
            
            # コスト計算検証
            cost = client.get_token_cost(result["usage"])
            assert cost > 0
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, monkeypatch):
        """エラーハンドリングの統合テスト"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        
        with patch("src.services.analysis.anthropic_client.AsyncAnthropic") as mock_anthropic:
            # ネットワークエラーをシミュレート
            mock_instance = AsyncMock()
            mock_instance.messages.create.side_effect = [
                ConnectionError("Network unreachable"),
                TimeoutError("Request timeout"),
                MagicMock(
                    content=[MagicMock(text="Recovery successful")],
                    usage=MagicMock(input_tokens=100, output_tokens=50),
                    model="claude-3-opus-20240229"
                )
            ]
            mock_anthropic.return_value = mock_instance
            
            client = AnthropicAnalysisClient()
            client.client = mock_instance
            
            # 3回目で成功
            result = await client.analyze_market(
                "test system",
                "test user",
                max_retries=3
            )
            
            assert result["success"] is True
            assert result["attempt"] == 3
    
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, monkeypatch):
        """レート制限の統合テスト"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        
        with patch("src.services.analysis.anthropic_client.AsyncAnthropic") as mock_anthropic:
            mock_instance = AsyncMock()
            mock_response = MagicMock(
                content=[MagicMock(text="Response")],
                usage=MagicMock(input_tokens=10, output_tokens=10),
                model="test-model"
            )
            mock_instance.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_instance
            
            client = AnthropicAnalysisClient()
            client.client = mock_instance
            client.rate_limiter.requests_per_minute = 2  # テスト用に制限を下げる
            
            # 連続リクエスト
            with patch("asyncio.sleep") as mock_sleep:
                # 3回リクエスト（2回目まではOK、3回目で待機）
                for i in range(3):
                    await client.analyze_market("test", "test")
                
                # 3回目のリクエストで待機が発生することを確認
                assert mock_sleep.called
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, monkeypatch):
        """並行リクエストのテスト"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        
        with patch("src.services.analysis.anthropic_client.AsyncAnthropic") as mock_anthropic:
            mock_instance = AsyncMock()
            
            # 異なるレスポンスを返す
            responses = [
                MagicMock(
                    content=[MagicMock(text=f"Response {i}")],
                    usage=MagicMock(input_tokens=10, output_tokens=10),
                    model="test-model"
                )
                for i in range(3)
            ]
            
            mock_instance.messages.create.side_effect = responses
            mock_anthropic.return_value = mock_instance
            
            client = AnthropicAnalysisClient()
            client.client = mock_instance
            
            # 並行実行
            import asyncio
            tasks = [
                client.analyze_market("system", f"user {i}")
                for i in range(3)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # 全て成功することを確認
            assert all(r["success"] for r in results)
            assert len(results) == 3
            
            # 異なるレスポンスが返ることを確認
            contents = [r["content"] for r in results]
            assert contents == ["Response 0", "Response 1", "Response 2"]