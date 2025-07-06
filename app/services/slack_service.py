import json
import httpx
from typing import Optional
from datetime import datetime
from app.core.config import settings
from app.utils.timezone import get_jst_now


class SlackService:
    def __init__(self):
        self.webhook_url = settings.SLACK_WEBHOOK_URL
        self.channel = settings.SLACK_CHANNEL
        self.username = settings.SLACK_USERNAME
    
    async def send_notification(self, message: str, images_count: int) -> bool:
        """Send analysis result to Slack"""
        if not self.webhook_url:
            print("Slack webhook URL not configured")
            return False
        
        payload = {
            "channel": self.channel,
            "username": self.username,
            "text": f"📊 FX相場分析結果 (画像{images_count}枚)",
            "attachments": [
                {
                    "color": "good",
                    "text": message,
                    "footer": "FX Forecast API",
                    "ts": int(get_jst_now().timestamp())
                }
            ]
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                return response.status_code == 200
        except Exception as e:
            print(f"Failed to send Slack notification: {e}")
            return False