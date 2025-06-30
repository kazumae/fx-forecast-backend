"""
AI分析結果のSlackフォーマッター
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import json


class SlackAnalysisFormatter:
    """AI分析結果のSlackフォーマッター"""
    
    # 重要度レベル設定
    NOTIFICATION_LEVELS = {
        "INFO": {
            "color": "#36a64f",  # 緑
            "channel": "#fx-analysis",
            "mention": False
        },
        "WARNING": {
            "color": "#ff9900",  # 黄
            "channel": "#fx-analysis", 
            "mention": False
        },
        "ALERT": {
            "color": "#ff0000",  # 赤
            "channel": "#fx-alerts",
            "mention": True
        }
    }
    
    def format_analysis_report(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """分析レポートをSlack Block Kitフォーマットに変換
        
        Args:
            analysis_result: AI分析結果
            
        Returns:
            Slack用のメッセージフォーマット
        """
        importance = analysis_result.get("importance", "INFO")
        importance_config = self.NOTIFICATION_LEVELS.get(
            importance, 
            self.NOTIFICATION_LEVELS["INFO"]
        )
        
        blocks = [
            self._create_header(analysis_result),
            self._create_summary_section(analysis_result),
            self._create_divider(),
            self._create_trend_section(analysis_result),
            self._create_signals_section(analysis_result),
            self._create_risk_section(analysis_result),
            self._create_recommendations_section(analysis_result)
        ]
        
        # 詳細情報は折りたたみセクションに
        if analysis_result.get("detailed_analysis"):
            blocks.append(self._create_detailed_section(analysis_result))
        
        # Noneを除外
        blocks = [b for b in blocks if b is not None]
        
        # メンション設定
        text_content = f"AI分析: {analysis_result.get('symbol', 'N/A')} - "
        text_content += analysis_result.get('executive_summary', '')
        
        if importance_config.get("mention"):
            # @here メンションを先頭に追加（Slack形式）
            text_content = f"<!here> {text_content}"
        
        return {
            "channel": importance_config["channel"],
            "text": text_content,
            "blocks": blocks,
            "attachments": [{
                "color": importance_config["color"]
            }]
        }
    
    def _create_header(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """ヘッダーセクション"""
        return {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🤖 AI市場分析レポート - {result.get('symbol', 'N/A')}",
                "emoji": True
            }
        }
    
    def _create_summary_section(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """サマリーセクション"""
        timestamp = result.get('timestamp', datetime.now(timezone.utc).isoformat())
        current_price = result.get('current_price', 0)
        
        fields = [{
            "type": "mrkdwn",
            "text": f"*分析時刻:*\n{timestamp}"
        }]
        
        if current_price is not None:
            fields.append({
                "type": "mrkdwn", 
                "text": f"*現在価格:*\n${current_price:,.2f}"
            })
        
        return {
            "type": "section",
            "fields": fields
        }
    
    def _create_divider(self) -> Dict[str, Any]:
        """区切り線"""
        return {"type": "divider"}
    
    def _create_trend_section(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """トレンド分析セクション"""
        if "trend" not in result:
            return None
            
        trend_emoji = {
            "bullish": "📈",
            "bearish": "📉", 
            "neutral": "➡️",
            "強気": "📈",
            "弱気": "📉",
            "中立": "➡️"
        }
        
        trend = result.get("trend", "中立")
        emoji = trend_emoji.get(trend, "➡️")
        
        text = f"*{emoji} 市場トレンド*\n"
        
        if "short_term_trend" in result:
            text += f"• 短期: {result['short_term_trend']}\n"
        if "medium_term_trend" in result:
            text += f"• 中期: {result['medium_term_trend']}\n"
        if "long_term_trend" in result:
            text += f"• 長期: {result['long_term_trend']}"
        
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text
            }
        }
    
    def _create_signals_section(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """シグナルセクション"""
        if "signals" not in result or not result["signals"]:
            return None
            
        signals = result["signals"]
        if isinstance(signals, list) and signals:
            signal = signals[0]  # 最新のシグナル
        elif isinstance(signals, dict):
            signal = signals
        else:
            return None
        
        signal_type = signal.get("type", "N/A")
        confidence = signal.get("confidence", 0) * 100
        entry_price = signal.get("entry_price", 0)
        stop_loss = signal.get("stop_loss", 0)
        take_profit = signal.get("take_profit", 0)
        
        emoji = "🟢" if signal_type == "BUY" else "🔴" if signal_type == "SELL" else "⚪"
        
        text = f"*{emoji} エントリーシグナル*\n"
        text += f"• タイプ: *{signal_type}*\n"
        if entry_price:
            text += f"• エントリー価格: ${entry_price:,.2f}\n"
        if stop_loss:
            text += f"• ストップロス: ${stop_loss:,.2f}\n"
        if take_profit:
            text += f"• テイクプロフィット: ${take_profit:,.2f}\n"
        text += f"• 信頼度: {confidence:.0f}%"
        
        if "risk_reward" in signal:
            text += f"\n• リスク/リワード: {signal['risk_reward']}"
        
        if "pattern" in signal:
            text += f"\n• パターン: {signal['pattern']}"
        
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text
            }
        }
    
    def _create_risk_section(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """リスク評価セクション"""
        if "risk_assessment" not in result:
            return None
            
        risk = result["risk_assessment"]
        risk_level = risk.get("level", "medium")
        
        risk_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🔴",
            "低": "🟢",
            "中": "🟡",
            "高": "🔴"
        }
        
        emoji = risk_emoji.get(risk_level, "🟡")
        
        text = f"*{emoji} リスク評価*\n"
        
        if "volatility" in risk:
            text += f"• ボラティリティ: {risk['volatility']}\n"
        
        if "key_risks" in risk and isinstance(risk["key_risks"], list):
            text += "• 主要リスク:\n"
            for r in risk["key_risks"][:3]:  # 最大3つ
                text += f"  - {r}\n"
        
        if "position_size" in risk:
            text += f"• 推奨ポジションサイズ: {risk['position_size']}"
        
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text.rstrip()
            }
        }
    
    def _create_recommendations_section(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """推奨アクションセクション"""
        if "recommendations" not in result:
            return None
            
        recommendations = result["recommendations"]
        if not recommendations:
            return None
        
        text = "*💡 推奨アクション*\n"
        
        if isinstance(recommendations, list):
            for i, rec in enumerate(recommendations[:5], 1):  # 最大5つ
                text += f"{i}. {rec}\n"
        elif isinstance(recommendations, dict):
            if "action" in recommendations:
                text += f"• {recommendations['action']}\n"
            if "stop_loss" in recommendations:
                text += f"• ストップロス: ${recommendations['stop_loss']:,.2f}\n"
            if "take_profit" in recommendations:
                text += f"• テイクプロフィット: ${recommendations['take_profit']:,.2f}"
        else:
            text += str(recommendations)
        
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text.rstrip()
            }
        }
    
    def _create_detailed_section(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """詳細分析セクション（より読みやすい形式）"""
        detailed = result.get("detailed_analysis", {})
        
        text = "*📋 詳細分析*\n"
        
        # エントリー根拠
        if "entry_rationale" in detailed:
            rationale = detailed["entry_rationale"]
            text += "\n*エントリー根拠:*\n"
            if isinstance(rationale, dict):
                if "primary_reason" in rationale:
                    text += f"• 主要理由: {rationale['primary_reason']}\n"
                if "confirmation_signals" in rationale:
                    text += f"• 確認シグナル: {rationale['confirmation_signals']}\n"
                if "invalidation_level" in rationale:
                    level = rationale['invalidation_level']
                    if isinstance(level, (int, float)):
                        text += f"• 無効化レベル: ${level:,.2f}\n"
                    else:
                        text += f"• 無効化レベル: {level}\n"
        
        # EMA分析
        if "ema_analysis" in detailed:
            ema = detailed["ema_analysis"]
            text += "\n*EMA分析:*\n"
            if isinstance(ema, dict):
                for key, value in ema.items():
                    if value:
                        text += f"• {value}\n"
        
        # サポート/レジスタンス
        if "support_resistance" in detailed:
            sr = detailed["support_resistance"]
            text += "\n*サポート/レジスタンス:*\n"
            if isinstance(sr, dict):
                for key, value in sr.items():
                    if value:
                        text += f"• {value}\n"
        
        # 長すぎる場合は切り詰め
        if len(text) > 2000:
            text = text[:1997] + "..."
        
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text.rstrip()
            }
        }
    
    def format_error_notification(self, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """エラー通知のフォーマット
        
        Args:
            error: 発生したエラー
            context: エラーコンテキスト
            
        Returns:
            Slack用のエラー通知フォーマット
        """
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 AI分析エラー",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*エラー時刻:*\n{datetime.now(timezone.utc).isoformat()}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*エラータイプ:*\n{type(error).__name__}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*エラーメッセージ:*\n```{str(error)}```"
                }
            }
        ]
        
        if context:
            context_text = json.dumps(context, indent=2, ensure_ascii=False)[:500]
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*コンテキスト:*\n```{context_text}```"
                }
            })
        
        return {
            "channel": self.NOTIFICATION_LEVELS["ALERT"]["channel"],
            "text": f"<!here> AI分析でエラーが発生しました: {type(error).__name__}",
            "blocks": blocks,
            "attachments": [{
                "color": self.NOTIFICATION_LEVELS["ALERT"]["color"]
            }]
        }