"""
Slackフォーマッターの単体テスト
"""
import pytest
from datetime import datetime, timezone
import json

from src.services.analysis.slack_formatter import SlackAnalysisFormatter


@pytest.fixture
def formatter():
    """SlackAnalysisFormatterのフィクスチャ"""
    return SlackAnalysisFormatter()


@pytest.fixture
def sample_analysis_result():
    """サンプル分析結果"""
    return {
        "symbol": "XAUUSD",
        "timestamp": "2024-06-30T12:00:00Z",
        "current_price": 3250.50,
        "importance": "INFO",
        "executive_summary": "金価格は強い上昇トレンドを維持しています。",
        "trend": "bullish",
        "short_term_trend": "強気（RSI 68）",
        "medium_term_trend": "強気（MACD上昇）",
        "long_term_trend": "中立（レンジ内）",
        "signals": [{
            "type": "BUY",
            "confidence": 0.85,
            "entry_price": 3248.00,
            "risk_reward": "1:2.5"
        }],
        "risk_assessment": {
            "level": "medium",
            "volatility": "高",
            "key_risks": ["米雇用統計発表待ち", "FRB政策決定", "地政学的リスク"],
            "position_size": "通常の70%"
        },
        "recommendations": [
            "現在のポジションを維持",
            "$3,260でテイクプロフィット設定",
            "$3,240でストップロス設定"
        ],
        "detailed_analysis": {
            "technical": {
                "ema_analysis": "全EMAが上向き",
                "macd": "ブルクロス確認"
            },
            "fundamental": {
                "usd_strength": "弱含み",
                "gold_demand": "高い"
            }
        }
    }


class TestSlackAnalysisFormatter:
    """SlackAnalysisFormatterのテスト"""
    
    def test_format_analysis_report_info_level(self, formatter, sample_analysis_result):
        """INFO レベルの分析レポートフォーマットテスト"""
        result = formatter.format_analysis_report(sample_analysis_result)
        
        # 基本構造の確認
        assert result["channel"] == "#fx-analysis"
        assert "AI分析: XAUUSD" in result["text"]
        assert len(result["blocks"]) > 0
        assert result["attachments"][0]["color"] == "#36a64f"  # 緑
        
        # ヘッダーの確認
        header = result["blocks"][0]
        assert header["type"] == "header"
        assert "AI市場分析レポート - XAUUSD" in header["text"]["text"]
    
    def test_format_analysis_report_alert_level(self, formatter, sample_analysis_result):
        """ALERT レベルの分析レポートフォーマットテスト"""
        sample_analysis_result["importance"] = "ALERT"
        result = formatter.format_analysis_report(sample_analysis_result)
        
        assert result["channel"] == "#fx-alerts"
        assert "<!here>" in result["text"]
        assert result["attachments"][0]["color"] == "#ff0000"  # 赤
    
    def test_create_trend_section(self, formatter, sample_analysis_result):
        """トレンドセクションのテスト"""
        result = formatter.format_analysis_report(sample_analysis_result)
        
        # トレンドセクションを探す
        trend_section = None
        for block in result["blocks"]:
            if block.get("type") == "section" and "市場トレンド" in block.get("text", {}).get("text", ""):
                trend_section = block
                break
        
        assert trend_section is not None
        assert "📈" in trend_section["text"]["text"]  # bullishの絵文字
        assert "短期: 強気（RSI 68）" in trend_section["text"]["text"]
    
    def test_create_signals_section(self, formatter, sample_analysis_result):
        """シグナルセクションのテスト"""
        result = formatter.format_analysis_report(sample_analysis_result)
        
        # シグナルセクションを探す
        signal_section = None
        for block in result["blocks"]:
            if block.get("type") == "section" and "エントリーシグナル" in block.get("text", {}).get("text", ""):
                signal_section = block
                break
        
        assert signal_section is not None
        assert "🟢" in signal_section["text"]["text"]  # BUYの絵文字
        assert "信頼度: 85%" in signal_section["text"]["text"]
        assert "リスク/リワード: 1:2.5" in signal_section["text"]["text"]
    
    def test_create_risk_section(self, formatter, sample_analysis_result):
        """リスク評価セクションのテスト"""
        result = formatter.format_analysis_report(sample_analysis_result)
        
        # リスクセクションを探す
        risk_section = None
        for block in result["blocks"]:
            if block.get("type") == "section" and "リスク評価" in block.get("text", {}).get("text", ""):
                risk_section = block
                break
        
        assert risk_section is not None
        assert "🟡" in risk_section["text"]["text"]  # mediumの絵文字
        assert "ボラティリティ: 高" in risk_section["text"]["text"]
        assert "米雇用統計発表待ち" in risk_section["text"]["text"]
    
    def test_create_recommendations_section(self, formatter, sample_analysis_result):
        """推奨アクションセクションのテスト"""
        result = formatter.format_analysis_report(sample_analysis_result)
        
        # 推奨セクションを探す
        rec_section = None
        for block in result["blocks"]:
            if block.get("type") == "section" and "推奨アクション" in block.get("text", {}).get("text", ""):
                rec_section = block
                break
        
        assert rec_section is not None
        assert "💡" in rec_section["text"]["text"]
        assert "現在のポジションを維持" in rec_section["text"]["text"]
        assert "$3,260でテイクプロフィット設定" in rec_section["text"]["text"]
    
    def test_create_detailed_section(self, formatter, sample_analysis_result):
        """詳細分析セクションのテスト"""
        result = formatter.format_analysis_report(sample_analysis_result)
        
        # 詳細セクションを探す
        detail_section = None
        for block in result["blocks"]:
            if block.get("type") == "section" and "詳細分析" in block.get("text", {}).get("text", ""):
                detail_section = block
                break
        
        assert detail_section is not None
        assert "```" in detail_section["text"]["text"]  # コードブロック
        assert "technical" in detail_section["text"]["text"]
    
    def test_missing_optional_fields(self, formatter):
        """オプションフィールドが欠けている場合のテスト"""
        minimal_result = {
            "symbol": "EURUSD",
            "current_price": 1.0850,
            "importance": "INFO"
        }
        
        result = formatter.format_analysis_report(minimal_result)
        
        assert result is not None
        assert result["channel"] == "#fx-analysis"
        assert len(result["blocks"]) >= 2  # 最低限ヘッダーとサマリー
    
    def test_format_error_notification(self, formatter):
        """エラー通知フォーマットのテスト"""
        error = ValueError("API rate limit exceeded")
        context = {
            "symbol": "XAUUSD",
            "attempt": 3,
            "last_price": 3250.00
        }
        
        result = formatter.format_error_notification(error, context)
        
        assert result["channel"] == "#fx-alerts"
        assert "@here" in result["text"]
        assert "AI分析エラー" in result["blocks"][0]["text"]["text"]
        assert "ValueError" in result["text"]
        assert result["attachments"][0]["color"] == "#ff0000"  # 赤
        
        # エラーメッセージの確認
        error_section = result["blocks"][2]
        assert "API rate limit exceeded" in error_section["text"]["text"]
    
    def test_recommendations_as_dict(self, formatter, sample_analysis_result):
        """推奨アクションが辞書形式の場合のテスト"""
        sample_analysis_result["recommendations"] = {
            "action": "BUY",
            "stop_loss": 3240.00,
            "take_profit": 3260.00
        }
        
        result = formatter.format_analysis_report(sample_analysis_result)
        
        # 推奨セクションを探す
        rec_section = None
        for block in result["blocks"]:
            if block.get("type") == "section" and "推奨アクション" in block.get("text", {}).get("text", ""):
                rec_section = block
                break
        
        assert rec_section is not None
        assert "BUY" in rec_section["text"]["text"]
        assert "$3,240.00" in rec_section["text"]["text"]
        assert "$3,260.00" in rec_section["text"]["text"]
    
    def test_long_detailed_analysis_truncation(self, formatter, sample_analysis_result):
        """長い詳細分析の切り詰めテスト"""
        # 長い詳細分析を作成
        sample_analysis_result["detailed_analysis"] = {
            f"key_{i}": f"value_{i}" * 100 for i in range(50)
        }
        
        result = formatter.format_analysis_report(sample_analysis_result)
        
        # 詳細セクションを探す
        detail_section = None
        for block in result["blocks"]:
            if block.get("type") == "section" and "詳細分析" in block.get("text", {}).get("text", ""):
                detail_section = block
                break
        
        assert detail_section is not None
        assert "..." in detail_section["text"]["text"]  # 切り詰められている
    
    def test_notification_levels(self, formatter):
        """通知レベルの設定確認"""
        levels = formatter.NOTIFICATION_LEVELS
        
        assert "INFO" in levels
        assert "WARNING" in levels
        assert "ALERT" in levels
        
        assert levels["INFO"]["color"] == "#36a64f"
        assert levels["WARNING"]["color"] == "#ff9900"
        assert levels["ALERT"]["color"] == "#ff0000"
        
        assert levels["ALERT"]["mention"] == "@here"
        assert levels["INFO"]["mention"] is False