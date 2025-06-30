"""
Slackフォーマッターの結合テスト
"""
import pytest
import json
from datetime import datetime, timezone

from src.services.analysis.slack_formatter import SlackAnalysisFormatter


class TestSlackAnalysisFormatterIntegration:
    """SlackAnalysisFormatterの結合テスト"""
    
    @pytest.fixture
    def formatter(self):
        """フォーマッターのフィクスチャ"""
        return SlackAnalysisFormatter()
    
    @pytest.fixture
    def complex_analysis_result(self):
        """複雑な分析結果のサンプル"""
        return {
            "symbol": "XAUUSD",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "current_price": 3255.75,
            "importance": "WARNING",
            "executive_summary": "金価格は重要な抵抗線に接近。ブレイクアウトの可能性が高まっています。",
            "trend": "bullish",
            "short_term_trend": "強気（RSI 72 - 買われ過ぎ圏）",
            "medium_term_trend": "強気（20EMA > 50EMA > 200EMA）",
            "long_term_trend": "強気（年初来高値更新中）",
            "signals": [
                {
                    "type": "BUY",
                    "confidence": 0.78,
                    "entry_price": 3252.00,
                    "risk_reward": "1:3.2",
                    "pattern": "ascending_triangle"
                },
                {
                    "type": "WAIT",
                    "confidence": 0.22,
                    "reason": "RSI過熱感"
                }
            ],
            "risk_assessment": {
                "level": "high",
                "volatility": "非常に高い（ATR: 45.2）",
                "key_risks": [
                    "RSI 70超えの過熱感",
                    "重要抵抗線 $3,260付近",
                    "FOMC議事録発表（明日）",
                    "ドル指数の反発リスク",
                    "利益確定売りの増加"
                ],
                "position_size": "通常の50%以下を推奨",
                "max_loss": "$15 per position"
            },
            "recommendations": [
                "段階的エントリーを推奨（1/3ずつ）",
                "$3,238の直近安値下でストップロス",
                "第1目標: $3,268（0.618 Fib）",
                "第2目標: $3,285（1.0 Fib）",
                "RSI 75超えで一部利確検討"
            ],
            "detailed_analysis": {
                "technical": {
                    "ema_analysis": {
                        "5EMA": 3252.30,
                        "20EMA": 3245.80,
                        "50EMA": 3235.20,
                        "200EMA": 3198.50,
                        "trend": "Perfect bullish alignment"
                    },
                    "indicators": {
                        "RSI": {"value": 72.3, "signal": "Overbought"},
                        "MACD": {"value": 8.5, "signal": 6.2, "histogram": 2.3},
                        "Stochastics": {"K": 85.2, "D": 82.1, "signal": "Overbought"}
                    },
                    "patterns": [
                        "Ascending Triangle (85% complete)",
                        "Bull Flag on 4H chart",
                        "Golden Cross confirmed (50/200)"
                    ]
                },
                "market_structure": {
                    "support_levels": [3240, 3225, 3210],
                    "resistance_levels": [3260, 3275, 3300],
                    "pivot_point": 3248.50,
                    "volume_profile": "Increasing on up moves"
                },
                "sentiment": {
                    "retail_positioning": "75% long",
                    "institutional_flow": "Net buying",
                    "options_flow": "Call buying dominant"
                }
            }
        }
    
    def test_full_analysis_workflow(self, formatter, complex_analysis_result):
        """完全な分析ワークフローのテスト"""
        result = formatter.format_analysis_report(complex_analysis_result)
        
        # WARNING レベルの設定確認
        assert result["channel"] == "#fx-analysis"
        assert result["attachments"][0]["color"] == "#ff9900"
        
        # 全セクションが含まれていることを確認
        block_texts = [str(block) for block in result["blocks"]]
        combined_text = " ".join(block_texts)
        
        # ヘッダーの確認
        assert any("AI市場分析レポート" in block.get("text", {}).get("text", "") 
                  for block in result["blocks"] if block.get("type") == "header")
        
        # 各セクションの存在確認
        section_texts = []
        for block in result["blocks"]:
            if block.get("type") == "section" and "text" in block:
                section_texts.append(block["text"].get("text", ""))
            if block.get("type") == "section" and "fields" in block:
                for field in block["fields"]:
                    section_texts.append(field.get("text", ""))
        
        combined_sections = " ".join(section_texts)
        assert "現在価格" in combined_sections
        assert "市場トレンド" in combined_sections
        assert "エントリーシグナル" in combined_sections
        assert "リスク評価" in combined_sections
        assert "推奨アクション" in combined_sections
        assert "詳細分析" in combined_sections
    
    def test_multiple_signals_handling(self, formatter, complex_analysis_result):
        """複数シグナルの処理テスト"""
        result = formatter.format_analysis_report(complex_analysis_result)
        
        # 最初のシグナル（BUY）が表示されることを確認
        signal_block = None
        for block in result["blocks"]:
            if block.get("type") == "section" and "エントリーシグナル" in str(block):
                signal_block = block
                break
        
        assert signal_block is not None
        text = signal_block["text"]["text"]
        assert "BUY" in text
        assert "78%" in text  # confidence 0.78
        assert "1:3.2" in text  # risk_reward
    
    def test_risk_section_with_many_risks(self, formatter, complex_analysis_result):
        """多数のリスクがある場合のテスト"""
        result = formatter.format_analysis_report(complex_analysis_result)
        
        risk_block = None
        for block in result["blocks"]:
            if block.get("type") == "section" and "リスク評価" in str(block):
                risk_block = block
                break
        
        assert risk_block is not None
        text = risk_block["text"]["text"]
        
        # high リスクレベル
        assert "🔴" in text
        
        # 最初の3つのリスクのみ表示されることを確認
        assert "RSI 70超えの過熱感" in text
        assert "重要抵抗線" in text
        assert "FOMC議事録発表" in text
        
        # 4つ目以降は表示されない
        assert "ドル指数の反発リスク" not in text
    
    def test_detailed_analysis_formatting(self, formatter, complex_analysis_result):
        """詳細分析の整形テスト"""
        result = formatter.format_analysis_report(complex_analysis_result)
        
        detail_block = None
        for block in result["blocks"]:
            if block.get("type") == "section" and "詳細分析" in str(block):
                detail_block = block
                break
        
        assert detail_block is not None
        text = detail_block["text"]["text"]
        
        # JSON形式で整形されていることを確認
        assert "```" in text
        assert '"technical"' in text
        assert '"ema_analysis"' in text
        assert "3252.3" in text  # 5EMA value
    
    def test_real_world_data_handling(self, formatter):
        """実際のデータ形式での処理テスト"""
        # AI分析から返される可能性のある実データ形式
        real_world_result = {
            "symbol": "XAUUSD",
            "timestamp": "2024-06-30T15:30:00Z",
            "current_price": 3248.25,
            "importance": "INFO",
            "executive_summary": "Gold maintains bullish momentum above key support.",
            "trend": "bullish",
            "short_term_trend": "Bullish (Price > 20EMA)",
            "signals": {
                "type": "HOLD",
                "confidence": 0.65,
                "entry_price": None,
                "reason": "Waiting for pullback to support"
            },
            "risk_assessment": {
                "level": "low",
                "volatility": "Normal",
                "key_risks": ["Weekend gap risk"],
                "position_size": "Standard"
            },
            "recommendations": "Monitor $3,240 support level for entry opportunity"
        }
        
        result = formatter.format_analysis_report(real_world_result)
        
        assert result is not None
        assert result["channel"] == "#fx-analysis"
        assert len(result["blocks"]) > 0
    
    def test_error_notification_workflow(self, formatter):
        """エラー通知の完全なワークフローテスト"""
        # 複数のエラータイプをテスト
        errors = [
            (ConnectionError("Failed to connect to API"), {"attempt": 3, "endpoint": "analyze"}),
            (ValueError("Invalid response format"), {"raw_response": '{"error": "rate_limit"}'}),
            (TimeoutError("Request timed out after 30s"), {"symbol": "XAUUSD", "timeout": 30})
        ]
        
        for error, context in errors:
            result = formatter.format_error_notification(error, context)
            
            assert result["channel"] == "#fx-alerts"
            assert "@here" in result["text"]
            assert type(error).__name__ in result["text"]
            
            # エラーメッセージが含まれていることを確認
            error_block = result["blocks"][2]
            assert str(error) in error_block["text"]["text"]
    
    def test_edge_cases(self, formatter):
        """エッジケースのテスト"""
        # 空の分析結果
        empty_result = {}
        result = formatter.format_analysis_report(empty_result)
        assert result is not None
        assert result["channel"] == "#fx-analysis"  # デフォルト
        
        # None値を含む結果
        none_result = {
            "symbol": "XAUUSD",
            "current_price": None,
            "trend": None,
            "signals": None,
            "recommendations": None
        }
        result = formatter.format_analysis_report(none_result)
        assert result is not None
        
        # 非常に長いテキスト
        long_summary = "A" * 500
        long_result = {
            "symbol": "XAUUSD",
            "executive_summary": long_summary,
            "importance": "INFO"
        }
        result = formatter.format_analysis_report(long_result)
        assert len(result["text"]) < 200  # 切り詰められている