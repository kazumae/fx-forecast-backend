"""
AI市場分析ジョブの単体テスト
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone
import json
import os

from src.batch.jobs.ai_market_analysis import AIMarketAnalysisJob


@pytest.fixture
def job():
    """AIMarketAnalysisJobのフィクスチャ"""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        job = AIMarketAnalysisJob()
        # サービスをモックで初期化
        job.data_collector = MagicMock()
        job.ai_client = MagicMock()
        return job


@pytest.fixture  
def sample_market_data():
    """サンプル市場データ"""
    return {
        "symbol": "XAUUSD",
        "market_data": {
            "current_price": 3250.50,
            "bid": 3250.25,
            "ask": 3250.75,
            "timestamp": "2024-06-30T12:00:00Z"
        },
        "candlesticks": [
            {
                "open_time": "2024-06-30T11:45:00Z",
                "open_price": 3248.00,
                "high_price": 3251.00,
                "low_price": 3247.50,
                "close_price": 3250.50,
                "volume": 1500
            }
        ],
        "indicators": [
            {
                "indicator_type": "RSI",
                "value": 68.5,
                "timestamp": "2024-06-30T12:00:00Z"
            }
        ],
        "signals": []
    }


@pytest.fixture
def sample_ai_response():
    """サンプルAI応答"""
    return {
        "success": True,
        "content": json.dumps({
            "importance": "INFO",
            "executive_summary": "Gold maintaining bullish momentum",
            "trend": "bullish",
            "short_term_trend": "Strong upward movement",
            "signals": [
                {
                    "type": "BUY",
                    "confidence": 0.75,
                    "entry_price": 3249.00,
                    "risk_reward": "1:2.5"
                }
            ],
            "risk_assessment": {
                "level": "medium",
                "volatility": "Moderate",
                "key_risks": ["Resistance at 3260"],
                "position_size": "Standard"
            },
            "recommendations": ["Hold current positions"],
            "detailed_analysis": {}
        }),
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 200,
            "total_tokens": 1200
        }
    }


class TestAIMarketAnalysisJob:
    """AIMarketAnalysisJobのテスト"""
    
    @pytest.mark.asyncio
    async def test_execute_success(self, job, sample_market_data, sample_ai_response):
        """正常実行のテスト"""
        # モック設定
        job.data_collector.collect_all_data = AsyncMock(return_value=sample_market_data)
        job.ai_client.analyze_market = AsyncMock(return_value=sample_ai_response)
        job.slack_notifier.send_message = AsyncMock()
        
        # 実行
        result = await job.execute(symbol="XAUUSD", dry_run=True)
        
        # 検証
        assert result["success"] is True
        assert result["symbol"] == "XAUUSD"
        assert result["analysis"]["importance"] == "INFO"
        assert result["analysis"]["trend"] == "bullish"
        assert len(result["analysis"]["signals"]) == 1
        assert result["ai_usage"]["total_tokens"] == 1200
        
        # データ収集が呼ばれたことを確認
        job.data_collector.collect_all_data.assert_called_once_with("XAUUSD")
        
        # AI分析が呼ばれたことを確認
        job.ai_client.analyze_market.assert_called_once()
        
        # ドライランなので通知は送られない
        job.slack_notifier.send_message.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_execute_with_notification(self, job, sample_market_data, sample_ai_response):
        """通知送信ありの実行テスト"""
        # モック設定
        job.data_collector.collect_all_data = AsyncMock(return_value=sample_market_data)
        job.ai_client.analyze_market = AsyncMock(return_value=sample_ai_response)
        job.slack_notifier.send_message = AsyncMock()
        
        # 実行
        result = await job.execute(symbol="XAUUSD", dry_run=False)
        
        # 通知が送られたことを確認
        job.slack_notifier.send_message.assert_called_once()
        call_args = job.slack_notifier.send_message.call_args
        assert call_args.kwargs["channel"] == "#fx-analysis"  # INFOレベル
        assert "XAUUSD" in call_args.kwargs["text"]
    
    @pytest.mark.asyncio
    async def test_execute_no_data_collected(self, job):
        """データ収集失敗時のテスト"""
        # 空のデータを返す
        job.data_collector.collect_all_data = AsyncMock(return_value={})
        job.slack_notifier.send_message = AsyncMock()
        
        # 実行してエラーを確認
        with pytest.raises(ValueError, match="No market data collected"):
            await job.execute(symbol="XAUUSD")
    
    @pytest.mark.asyncio
    async def test_execute_ai_analysis_failed(self, job, sample_market_data):
        """AI分析失敗時のテスト"""
        # AI分析失敗
        job.data_collector.collect_all_data = AsyncMock(return_value=sample_market_data)
        job.ai_client.analyze_market = AsyncMock(return_value={
            "success": False,
            "error": "API rate limit exceeded"
        })
        job.slack_notifier.send_message = AsyncMock()
        
        # 実行してエラーを確認
        with pytest.raises(ValueError, match="AI analysis failed"):
            await job.execute(symbol="XAUUSD")
    
    def test_format_candlesticks(self, job):
        """ローソク足フォーマットのテスト"""
        candlesticks = [
            {
                "open_time": "2024-06-30T12:00:00Z",
                "open_price": 3250.00,
                "high_price": 3252.00,
                "low_price": 3249.00,
                "close_price": 3251.50,
                "volume": 1000
            }
        ]
        
        result = job._format_candlesticks(candlesticks)
        
        assert "Time: 2024-06-30T12:00:00Z" in result
        assert "O: 3250.00" in result
        assert "H: 3252.00" in result
        assert "L: 3249.00" in result
        assert "C: 3251.50" in result
        assert "V: 1000" in result
    
    def test_format_candlesticks_empty(self, job):
        """空のローソク足データのテスト"""
        result = job._format_candlesticks([])
        assert result == "No candlestick data available"
    
    def test_format_indicators(self, job):
        """指標フォーマットのテスト"""
        indicators = [
            {"indicator_type": "RSI", "value": 65.5, "timestamp": "2024-06-30T12:00:00Z"},
            {"indicator_type": "MACD", "value": {"macd": 5.2, "signal": 4.8}, "timestamp": "2024-06-30T12:00:00Z"}
        ]
        
        result = job._format_indicators(indicators)
        
        assert "RSI: 65.5" in result
        assert "MACD:" in result
        assert '"macd": 5.2' in result
    
    def test_format_signals(self, job):
        """シグナルフォーマットのテスト"""
        signals = [
            {
                "created_at": "2024-06-30T11:30:00Z",
                "signal_type": "BUY",
                "confidence_score": 0.85
            }
        ]
        
        result = job._format_signals(signals)
        
        assert "Time: 2024-06-30T11:30:00Z" in result
        assert "Type: BUY" in result
        assert "Score: 0.85" in result
    
    def test_parse_analysis_result_valid_json(self, job):
        """有効なJSON応答のパーステスト"""
        content = json.dumps({
            "importance": "WARNING",
            "executive_summary": "Test summary",
            "trend": "bearish"
        })
        
        result = job._parse_analysis_result(content)
        
        assert result["importance"] == "WARNING"
        assert result["executive_summary"] == "Test summary"
        assert result["trend"] == "bearish"
    
    def test_parse_analysis_result_invalid_json(self, job):
        """無効なJSON応答のパーステスト"""
        content = "This is not valid JSON"
        
        result = job._parse_analysis_result(content)
        
        # フォールバック値を確認
        assert result["importance"] == "INFO"
        assert "This is not valid JSON" in result["executive_summary"]
        assert result["trend"] == "neutral"
        assert result["detailed_analysis"]["raw_response"] == content
    
    @pytest.mark.asyncio
    async def test_send_slack_notification(self, job):
        """Slack通知送信のテスト"""
        analysis = {
            "symbol": "XAUUSD",
            "importance": "ALERT",
            "executive_summary": "Critical breakout detected"
        }
        
        # モック設定
        job.slack_formatter.format_analysis_report = MagicMock(return_value={
            "channel": "#fx-alerts",
            "text": "Test message",
            "blocks": [],
            "attachments": []
        })
        job.slack_notifier.send_message = AsyncMock()
        
        # 実行
        await job._send_slack_notification(analysis)
        
        # 検証
        job.slack_formatter.format_analysis_report.assert_called_once_with(analysis)
        job.slack_notifier.send_message.assert_called_once_with(
            channel="#fx-alerts",
            text="Test message",
            blocks=[],
            attachments=[]
        )
    
    @pytest.mark.asyncio
    async def test_send_error_notification(self, job):
        """エラー通知送信のテスト"""
        error = ValueError("Test error")
        context = {"symbol": "XAUUSD"}
        
        # モック設定
        job.slack_formatter.format_error_notification = MagicMock(return_value={
            "channel": "#fx-alerts",
            "text": "Error message",
            "blocks": [],
            "attachments": []
        })
        job.slack_notifier.send_message = AsyncMock()
        
        # 実行
        await job._send_error_notification(error, context)
        
        # 検証
        job.slack_formatter.format_error_notification.assert_called_once_with(error, context)
        job.slack_notifier.send_message.assert_called_once()
    
    def test_summarize_collected_data(self, job, sample_market_data):
        """データサマリー作成のテスト"""
        summary = job._summarize_collected_data(sample_market_data)
        
        assert summary["has_market_data"] is True
        assert summary["candlestick_count"] == 1
        assert summary["indicator_count"] == 1
        assert summary["signal_count"] == 0
        assert summary["latest_price"] == 3250.50
    
    @pytest.mark.asyncio
    async def test_execute_with_custom_symbol(self, job, sample_market_data, sample_ai_response):
        """カスタムシンボルでの実行テスト"""
        # モック設定
        job.data_collector.collect_all_data = AsyncMock(return_value=sample_market_data)
        job.ai_client.analyze_market = AsyncMock(return_value=sample_ai_response)
        
        # EURUSDで実行
        result = await job.execute(symbol="EURUSD", dry_run=True)
        
        assert result["symbol"] == "EURUSD"
        job.data_collector.collect_all_data.assert_called_once_with("EURUSD")