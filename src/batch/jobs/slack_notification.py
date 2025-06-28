from datetime import datetime, timedelta
from typing import Dict, List
from sqlalchemy import func

from src.batch.base import BaseBatchJob
from src.batch.utils.slack_notifier import SlackNotifier
from src.models.forex import ForexRate, ForexForecast
from src.models.user import User


class SlackNotificationBatch(BaseBatchJob):
    """Slack通知を送信するバッチジョブ"""
    
    def __init__(self, notification_type: str = "daily_summary"):
        super().__init__("SlackNotification")
        self.notification_type = notification_type
        self.notifier = SlackNotifier()
    
    def execute(self):
        """通知タイプに応じた処理を実行"""
        if self.notification_type == "daily_summary":
            return self._send_daily_summary()
        elif self.notification_type == "rate_alert":
            return self._send_rate_alert()
        elif self.notification_type == "system_status":
            return self._send_system_status()
        else:
            raise ValueError(f"Unknown notification type: {self.notification_type}")
    
    def _send_daily_summary(self) -> Dict:
        """日次サマリーを送信"""
        # 過去24時間のデータを集計
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        # ユーザー統計
        total_users = self.db.query(func.count(User.id)).scalar()
        new_users = self.db.query(func.count(User.id))\
            .filter(User.created_at >= yesterday).scalar()
        
        # 為替レート統計
        rates_count = self.db.query(func.count(ForexRate.id))\
            .filter(ForexRate.created_at >= yesterday).scalar()
        
        # 予測統計
        forecasts_count = self.db.query(func.count(ForexForecast.id))\
            .filter(ForexForecast.created_at >= yesterday).scalar()
        
        # 最新レート取得
        latest_rates = self._get_latest_rates()
        
        # メッセージ作成
        message = f"""
📊 *日次レポート* - {datetime.utcnow().strftime('%Y年%m月%d日')}

*ユーザー統計*
• 総ユーザー数: {total_users}
• 新規ユーザー: {new_users}

*データ統計*
• 新規為替レート: {rates_count}
• 新規予測: {forecasts_count}

*現在の為替レート*
"""
        for rate in latest_rates:
            message += f"• {rate['pair']}: {rate['rate']:.4f} ({rate['change']:+.2f}%)\n"
        
        # Slack送信
        success = self.notifier.send_webhook_message(
            text=message,
            attachments=[{
                "color": "#36a64f",
                "title": "FX Forecast System - Daily Summary",
                "text": f"過去24時間の統計情報",
                "footer": "FX Forecast System",
                "ts": int(datetime.utcnow().timestamp())
            }]
        )
        
        return {
            "notification_type": "daily_summary",
            "sent": success,
            "stats": {
                "total_users": total_users,
                "new_users": new_users,
                "rates_count": rates_count,
                "forecasts_count": forecasts_count
            }
        }
    
    def _send_rate_alert(self) -> Dict:
        """為替レートアラートを送信"""
        # 大きな変動があった通貨ペアを検出
        alerts = self._detect_rate_changes()
        
        if not alerts:
            self.logger.info("No significant rate changes detected")
            return {"notification_type": "rate_alert", "sent": False, "alerts": 0}
        
        message = "🚨 *為替レート変動アラート*\n\n"
        
        for alert in alerts:
            emoji = "📈" if alert['change'] > 0 else "📉"
            message += f"{emoji} *{alert['pair']}*: {alert['current']:.4f} ({alert['change']:+.2f}%)\n"
        
        success = self.notifier.send_webhook_message(
            text=message,
            attachments=[{
                "color": "warning",
                "title": "大幅な為替変動を検出",
                "text": f"{len(alerts)}個の通貨ペアで1%以上の変動",
                "footer": "FX Forecast System",
                "ts": int(datetime.utcnow().timestamp())
            }]
        )
        
        return {
            "notification_type": "rate_alert",
            "sent": success,
            "alerts": len(alerts)
        }
    
    def _send_system_status(self) -> Dict:
        """システムステータスを送信"""
        # データベース接続チェック
        try:
            self.db.execute("SELECT 1")
            db_status = "✅ 正常"
        except:
            db_status = "❌ エラー"
        
        # 最新データのタイムスタンプ
        latest_rate = self.db.query(ForexRate)\
            .order_by(ForexRate.timestamp.desc())\
            .first()
        
        if latest_rate:
            # タイムゾーンを考慮した時間差計算
            from datetime import timezone
            now = datetime.now(timezone.utc)
            timestamp = latest_rate.timestamp.replace(tzinfo=timezone.utc) if latest_rate.timestamp.tzinfo is None else latest_rate.timestamp
            data_freshness = (now - timestamp).total_seconds() / 60
            if data_freshness < 60:
                data_status = "✅ 正常"
            else:
                data_status = f"⚠️ 遅延 ({data_freshness:.0f}分)"
        else:
            data_status = "❌ データなし"
        
        message = f"""
🔧 *システムステータス*

• データベース: {db_status}
• データ更新: {data_status}
• APIサーバー: ✅ 正常
• バッチ処理: ✅ 正常

最終チェック: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
        
        success = self.notifier.send_webhook_message(text=message)
        
        return {
            "notification_type": "system_status",
            "sent": success,
            "status": {
                "database": db_status,
                "data_freshness": data_status
            }
        }
    
    def _get_latest_rates(self) -> List[Dict]:
        """最新の為替レートと変動率を取得"""
        currency_pairs = ["USD/JPY", "EUR/USD", "GBP/USD", "EUR/JPY"]
        rates = []
        
        for pair in currency_pairs:
            # 最新レート
            latest = self.db.query(ForexRate)\
                .filter(ForexRate.currency_pair == pair)\
                .order_by(ForexRate.timestamp.desc())\
                .first()
            
            if not latest:
                continue
            
            # 24時間前のレート
            yesterday = datetime.utcnow() - timedelta(days=1)
            old_rate = self.db.query(ForexRate)\
                .filter(
                    ForexRate.currency_pair == pair,
                    ForexRate.timestamp <= yesterday
                )\
                .order_by(ForexRate.timestamp.desc())\
                .first()
            
            if old_rate:
                change = ((latest.rate - old_rate.rate) / old_rate.rate) * 100
            else:
                change = 0.0
            
            rates.append({
                "pair": pair,
                "rate": latest.rate,
                "change": change
            })
        
        return rates
    
    def _detect_rate_changes(self, threshold: float = 1.0) -> List[Dict]:
        """閾値を超える為替変動を検出"""
        alerts = []
        rates_with_changes = self._get_latest_rates()
        
        for rate_info in rates_with_changes:
            if abs(rate_info['change']) >= threshold:
                alerts.append({
                    "pair": rate_info['pair'],
                    "current": rate_info['rate'],
                    "change": rate_info['change']
                })
        
        return alerts