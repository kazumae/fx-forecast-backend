"""
AI市場分析ジョブの結合テスト
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json
from datetime import datetime, timezone

from src.batch.jobs.ai_market_analysis import AIMarketAnalysisJob


class TestAIMarketAnalysisJobIntegration:
    """AIMarketAnalysisJobの結合テスト"""
    
    @pytest.fixture
    def job(self):
        """ジョブインスタンス"""
        return AIMarketAnalysisJob()
    
    @pytest.fixture
    def mock_market_data(self):
        """モック市場データ"""
        return {
            "symbol": "XAUUSD",
            "market_data": {
                "current_price": 3255.75,
                "bid": 3255.50,
                "ask": 3256.00,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "candlesticks": [
                {
                    "open_time": "2024-06-30T14:45:00Z",
                    "open_price": 3252.00,
                    "high_price": 3256.50,
                    "low_price": 3251.50,
                    "close_price": 3255.75,
                    "volume": 2500
                },
                {
                    "open_time": "2024-06-30T14:30:00Z", 
                    "open_price": 3250.00,
                    "high_price": 3253.00,
                    "low_price": 3249.50,
                    "close_price": 3252.00,
                    "volume": 2000
                }
            ],
            "indicators": [
                {"indicator_type": "RSI", "value": 72.3, "timestamp": "2024-06-30T15:00:00Z"},
                {"indicator_type": "EMA5", "value": 3253.20, "timestamp": "2024-06-30T15:00:00Z"},
                {"indicator_type": "EMA20", "value": 3248.50, "timestamp": "2024-06-30T15:00:00Z"}
            ],
            "signals": [
                {
                    "created_at": "2024-06-30T14:00:00Z",
                    "signal_type": "BUY",
                    "confidence_score": 0.82,
                    "entry_price": 3248.00
                }
            ]
        }
    
    @pytest.fixture
    def mock_ai_response_warning(self):
        """WARNING レベルのAI応答"""
        return {
            "success": True,
            "content": json.dumps({
                "importance": "WARNING",
                "executive_summary": "金価格が重要な抵抗線3260に接近。ブレイクアウトの可能性。",
                "trend": "bullish",
                "short_term_trend": "強気（RSI過熱感あり）",
                "medium_term_trend": "強気（全EMA上向き）",
                "long_term_trend": "強気（年初来高値更新中）",
                "signals": [
                    {
                        "type": "BUY",
                        "confidence": 0.78,
                        "entry_price": 3254.00,
                        "risk_reward": "1:3",
                        "pattern": "ascending_triangle"
                    }
                ],
                "risk_assessment": {
                    "level": "high",
                    "volatility": "非常に高い（ATR: 45.2）",
                    "key_risks": [
                        "RSI 70超えの過熱感",
                        "重要抵抗線 $3,260",
                        "FOMC議事録発表待ち"
                    ],
                    "position_size": "通常の50%",
                    "max_loss": "$15 per position"
                },
                "recommendations": [
                    "段階的エントリーを推奨",
                    "$3,245でストップロス設定",
                    "$3,275で部分利確"
                ],
                "detailed_analysis": {
                    "technical": {
                        "support_levels": [3245, 3240, 3235],
                        "resistance_levels": [3260, 3270, 3280]
                    }
                }
            }),
            "usage": {
                "input_tokens": 1500,
                "output_tokens": 350,
                "total_tokens": 1850
            }
        }
    
    @pytest.mark.asyncio
    async def test_full_execution_flow(self, job, mock_market_data, mock_ai_response_warning):
        """完全な実行フローのテスト"""
        # モック設定
        with patch.object(job.data_collector, 'collect_all_data', AsyncMock(return_value=mock_market_data)), \
             patch.object(job.ai_client, 'analyze_market', AsyncMock(return_value=mock_ai_response_warning)), \
             patch.object(job.slack_notifier, 'send_message', AsyncMock()) as mock_slack:
            
            # 実行
            result = await job.execute(symbol="XAUUSD", dry_run=False)
            
            # 基本的な成功確認
            assert result["success"] is True
            assert result["symbol"] == "XAUUSD"
            
            # 分析結果の確認
            analysis = result["analysis"]
            assert analysis["importance"] == "WARNING"
            assert analysis["trend"] == "bullish"
            assert len(analysis["signals"]) == 1
            assert analysis["signals"][0]["confidence"] == 0.78
            
            # リスク評価の確認
            assert analysis["risk_assessment"]["level"] == "high"
            assert len(analysis["risk_assessment"]["key_risks"]) == 3
            
            # Slack通知の確認
            mock_slack.assert_called_once()
            slack_call = mock_slack.call_args
            assert slack_call.kwargs["channel"] == "#fx-analysis"  # WARNINGレベル
            assert "blocks" in slack_call.kwargs
            assert "attachments" in slack_call.kwargs
    
    @pytest.mark.asyncio
    async def test_error_handling_flow(self, job, mock_market_data):
        """エラーハンドリングフローのテスト"""
        # AI分析でエラーを発生させる
        error_response = {
            "success": False,
            "error": "Rate limit exceeded",
            "usage": {"total_tokens": 0}
        }
        
        with patch.object(job.data_collector, 'collect_all_data', AsyncMock(return_value=mock_market_data)), \
             patch.object(job.ai_client, 'analyze_market', AsyncMock(return_value=error_response)), \
             patch.object(job.slack_notifier, 'send_message', AsyncMock()) as mock_slack:
            
            # エラーが発生することを確認
            with pytest.raises(ValueError, match="AI analysis failed"):
                await job.execute(symbol="XAUUSD", dry_run=False)
            
            # エラー通知が送信されたことを確認
            mock_slack.assert_called_once()
            error_call = mock_slack.call_args
            assert error_call.kwargs["channel"] == "#fx-alerts"
            assert "<!here>" in error_call.kwargs["text"]
    
    @pytest.mark.asyncio
    async def test_alert_level_notification(self, job, mock_market_data):
        """ALERTレベル通知のテスト"""
        alert_response = {
            "success": True,
            "content": json.dumps({
                "importance": "ALERT",
                "executive_summary": "重要なブレイクアウト発生！即座の対応が必要。",
                "trend": "bullish",
                "signals": [
                    {
                        "type": "BUY",
                        "confidence": 0.92,
                        "entry_price": 3261.00,
                        "risk_reward": "1:5"
                    }
                ],
                "risk_assessment": {
                    "level": "high",
                    "key_risks": ["Extreme volatility"]
                },
                "recommendations": ["Immediate entry recommended"]
            }),
            "usage": {"total_tokens": 1000}
        }
        
        with patch.object(job.data_collector, 'collect_all_data', AsyncMock(return_value=mock_market_data)), \
             patch.object(job.ai_client, 'analyze_market', AsyncMock(return_value=alert_response)), \
             patch.object(job.slack_notifier, 'send_message', AsyncMock()) as mock_slack:
            
            result = await job.execute(symbol="XAUUSD", dry_run=False)
            
            # ALERTレベルの通知確認
            mock_slack.assert_called_once()
            alert_call = mock_slack.call_args
            assert alert_call.kwargs["channel"] == "#fx-alerts"
            assert "<!here>" in alert_call.kwargs["text"]
    
    @pytest.mark.asyncio
    async def test_dry_run_mode(self, job, mock_market_data, mock_ai_response_warning):
        """ドライランモードのテスト"""
        with patch.object(job.data_collector, 'collect_all_data', AsyncMock(return_value=mock_market_data)), \
             patch.object(job.ai_client, 'analyze_market', AsyncMock(return_value=mock_ai_response_warning)), \
             patch.object(job.slack_notifier, 'send_message', AsyncMock()) as mock_slack:
            
            # ドライランで実行
            result = await job.execute(symbol="XAUUSD", dry_run=True)
            
            # 結果は正常に返るが、通知は送信されない
            assert result["success"] is True
            mock_slack.assert_not_called()
            
            # 実行詳細にdry_runフラグが含まれることを確認
            execution_detail = job.get_execution_detail()
            assert execution_detail["dry_run"] is True
    
    @pytest.mark.asyncio
    async def test_invalid_ai_response_handling(self, job, mock_market_data):
        """無効なAI応答の処理テスト"""
        # JSONではない応答
        invalid_response = {
            "success": True,
            "content": "This is not JSON. The market looks bullish but I cannot format properly.",
            "usage": {"total_tokens": 500}
        }
        
        with patch.object(job.data_collector, 'collect_all_data', AsyncMock(return_value=mock_market_data)), \
             patch.object(job.ai_client, 'analyze_market', AsyncMock(return_value=invalid_response)), \
             patch.object(job.slack_notifier, 'send_message', AsyncMock()) as mock_slack:
            
            # 実行（エラーにはならない）
            result = await job.execute(symbol="XAUUSD", dry_run=False)
            
            # フォールバック値が使用されることを確認
            assert result["success"] is True
            assert result["analysis"]["importance"] == "INFO"
            assert result["analysis"]["trend"] == "neutral"
            assert "Manual review required" in result["analysis"]["recommendations"]
            
            # 通知は送信される
            mock_slack.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_multiple_symbol_analysis(self, job, mock_market_data, mock_ai_response_warning):
        """複数シンボルの分析テスト"""
        symbols = ["XAUUSD", "EURUSD", "GBPUSD"]
        
        with patch.object(job.data_collector, 'collect_all_data', AsyncMock(return_value=mock_market_data)), \
             patch.object(job.ai_client, 'analyze_market', AsyncMock(return_value=mock_ai_response_warning)), \
             patch.object(job.slack_notifier, 'send_message', AsyncMock()):
            
            # 各シンボルで実行
            for symbol in symbols:
                result = await job.execute(symbol=symbol, dry_run=True)
                assert result["symbol"] == symbol
                job.data_collector.collect_all_data.assert_called_with(symbol)
    
    @pytest.mark.asyncio
    async def test_execution_detail_tracking(self, job, mock_market_data, mock_ai_response_warning):
        """実行詳細の追跡テスト"""
        with patch.object(job.data_collector, 'collect_all_data', AsyncMock(return_value=mock_market_data)), \
             patch.object(job.ai_client, 'analyze_market', AsyncMock(return_value=mock_ai_response_warning)), \
             patch.object(job.slack_notifier, 'send_message', AsyncMock()):
            
            await job.execute(symbol="XAUUSD", dry_run=True)
            
            # 実行詳細の確認
            detail = job.get_execution_detail()
            assert detail["symbol"] == "XAUUSD"
            assert detail["importance"] == "WARNING"
            assert detail["trend"] == "bullish"
            assert detail["signal_count"] == 1
            assert detail["ai_tokens_used"] == 1850