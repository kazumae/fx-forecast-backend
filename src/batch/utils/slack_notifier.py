import json
from typing import List, Dict, Optional
from slack_sdk import WebClient
from slack_sdk.webhook import WebhookClient
from slack_sdk.errors import SlackApiError
import logging

from src.core.config import settings


class SlackNotifier:
    """Slack通知を送信するユーティリティクラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.webhook_url = getattr(settings, 'SLACK_WEBHOOK_URL', None)
        self.bot_token = getattr(settings, 'SLACK_BOT_TOKEN', None)
        self.default_channel = getattr(settings, 'SLACK_DEFAULT_CHANNEL', '#general')
        
        # Webhook クライアント
        if self.webhook_url:
            self.webhook_client = WebhookClient(self.webhook_url)
        else:
            self.webhook_client = None
            
        # Web API クライアント
        if self.bot_token:
            self.web_client = WebClient(token=self.bot_token)
        else:
            self.web_client = None
    
    def send_webhook_message(self, text: str, attachments: Optional[List[Dict]] = None) -> bool:
        """Webhookを使用してメッセージを送信"""
        if not self.webhook_client:
            self.logger.warning("Slack webhook URL is not configured")
            return False
        
        try:
            response = self.webhook_client.send(
                text=text,
                attachments=attachments
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Failed to send Slack webhook message: {str(e)}")
            return False
    
    def send_message(self, channel: str, text: str, blocks: Optional[List[Dict]] = None) -> bool:
        """Web APIを使用してメッセージを送信"""
        if not self.web_client:
            self.logger.warning("Slack bot token is not configured")
            return False
        
        try:
            response = self.web_client.chat_postMessage(
                channel=channel,
                text=text,
                blocks=blocks
            )
            return response["ok"]
        except SlackApiError as e:
            self.logger.error(f"Slack API Error: {e.response['error']}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to send Slack message: {str(e)}")
            return False
    
    def send_error_notification(self, job_name: str, error_message: str) -> bool:
        """エラー通知を送信"""
        attachments = [{
            "color": "danger",
            "title": f"バッチジョブエラー: {job_name}",
            "text": error_message,
            "fields": [
                {
                    "title": "環境",
                    "value": "Production",
                    "short": True
                },
                {
                    "title": "ジョブ名",
                    "value": job_name,
                    "short": True
                }
            ],
            "footer": "FX Forecast System",
            "ts": int(datetime.utcnow().timestamp())
        }]
        
        return self.send_webhook_message(
            text=f"⚠️ バッチジョブ `{job_name}` でエラーが発生しました",
            attachments=attachments
        )
    
    def send_success_notification(self, job_name: str, message: str, details: Optional[Dict] = None) -> bool:
        """成功通知を送信"""
        fields = [
            {
                "title": "ジョブ名",
                "value": job_name,
                "short": True
            },
            {
                "title": "ステータス",
                "value": "✅ 成功",
                "short": True
            }
        ]
        
        if details:
            for key, value in details.items():
                fields.append({
                    "title": key,
                    "value": str(value),
                    "short": True
                })
        
        attachments = [{
            "color": "good",
            "title": f"バッチジョブ完了: {job_name}",
            "text": message,
            "fields": fields,
            "footer": "FX Forecast System",
            "ts": int(datetime.utcnow().timestamp())
        }]
        
        return self.send_webhook_message(
            text=f"✅ バッチジョブ `{job_name}` が正常に完了しました",
            attachments=attachments
        )


    def send_custom_notification(
        self, 
        title: str,
        message: str,
        color: str = "good",  # good, warning, danger, or hex color
        fields: Optional[List[Dict[str, str]]] = None,
        emoji: Optional[str] = None
    ) -> bool:
        """カスタム通知を送信（汎用メソッド）"""
        if emoji:
            text = f"{emoji} {title}"
        else:
            text = title
            
        attachment_fields = fields or []
        
        attachments = [{
            "color": color,
            "title": title,
            "text": message,
            "fields": attachment_fields,
            "footer": "FX Forecast System",
            "ts": int(datetime.utcnow().timestamp())
        }]
        
        return self.send_webhook_message(text=text, attachments=attachments)
    
    def send_batch_notification(
        self,
        job_name: str,
        status: str,  # "started", "completed", "failed", "warning"
        message: str,
        details: Optional[Dict] = None,
        error: Optional[Exception] = None
    ) -> bool:
        """バッチジョブの統一的な通知"""
        # ステータスに応じた設定
        status_config = {
            "started": {"color": "#3AA3E3", "emoji": "🚀", "text": "開始しました"},
            "completed": {"color": "good", "emoji": "✅", "text": "正常に完了しました"},
            "failed": {"color": "danger", "emoji": "❌", "text": "エラーが発生しました"},
            "warning": {"color": "warning", "emoji": "⚠️", "text": "警告があります"}
        }
        
        config = status_config.get(status, {"color": "#808080", "emoji": "ℹ️", "text": status})
        
        fields = [
            {"title": "ジョブ名", "value": job_name, "short": True},
            {"title": "ステータス", "value": config["text"], "short": True}
        ]
        
        if details:
            for key, value in details.items():
                fields.append({
                    "title": key,
                    "value": str(value),
                    "short": True
                })
        
        if error:
            fields.append({
                "title": "エラー詳細",
                "value": str(error),
                "short": False
            })
        
        return self.send_custom_notification(
            title=f"バッチジョブ: {job_name}",
            message=message,
            color=config["color"],
            fields=fields,
            emoji=config["emoji"]
        )


from datetime import datetime