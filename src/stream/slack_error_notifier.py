"""
Slack Error Notifier for TraderMade Streaming
"""
import time
import logging
import json
import urllib.request
from datetime import datetime
from typing import Dict, Optional
from enum import Enum
import os


class SlackErrorNotifier:
    """Slack error notification handler with rate limiting"""
    
    def __init__(self, notification_cooldown: int = 300):
        """
        Initialize Slack error notifier
        
        Args:
            notification_cooldown: Cooldown period in seconds between notifications of same type
        """
        self.webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        self.last_notification: Dict[str, float] = {}
        self.notification_cooldown = notification_cooldown
        self.logger = logging.getLogger(__name__)
        
        # Check if Slack is configured
        if not self.webhook_url:
            self.logger.warning("Slack webhook URL not configured - notifications disabled")
            self.enabled = False
        else:
            self.enabled = True
            self.logger.info(f"Slack error notifications enabled (cooldown: {notification_cooldown}s)")
    
    def _send_webhook_message(self, payload: dict) -> bool:
        """Send message via webhook"""
        try:
            req = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req) as response:
                return response.status == 200
                
        except Exception as e:
            self.logger.error(f"Failed to send Slack webhook message: {e}")
            return False
    
    def notify_error(self, error_type: str, error_message: str, 
                    severity: str = "ERROR", details: Optional[Dict] = None) -> bool:
        """
        Send error notification to Slack
        
        Args:
            error_type: Type of error (e.g., "AUTH_ERROR", "NETWORK_ERROR")
            error_message: Human-readable error message
            severity: Severity level (INFO, WARNING, ERROR, CRITICAL)
            details: Additional error details
            
        Returns:
            True if notification was sent, False otherwise
        """
        if not self.enabled:
            return False
            
        # Check rate limiting
        if not self._can_notify(error_type):
            self.logger.debug(f"Skipping notification for {error_type} - cooldown active")
            return False
        
        try:
            # Determine color based on severity
            color_map = {
                "INFO": "good",
                "WARNING": "warning", 
                "ERROR": "danger",
                "CRITICAL": "danger"
            }
            color = color_map.get(severity, "danger")
            
            # Emoji based on error type
            emoji_map = {
                "AUTH_ERROR": "🔐",
                "NETWORK_ERROR": "🌐",
                "DATA_ERROR": "📊",
                "TIMEOUT_ERROR": "⏱️",
                "RATE_LIMIT_ERROR": "🚦",
                "REPEATED_CONNECTION_FAILURE": "🔄",
                "UNKNOWN_ERROR": "❓"
            }
            emoji = emoji_map.get(error_type, "🚨")
            
            # Format fields
            fields = [
                {"title": "Error Type", "value": error_type, "short": True},
                {"title": "Severity", "value": severity, "short": True},
                {"title": "Environment", "value": "TraderMade Streaming", "short": True},
                {"title": "Timestamp", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S JST"), "short": True}
            ]
            
            # Add details if provided
            if details:
                for key, value in details.items():
                    fields.append({
                        "title": key.replace("_", " ").title(),
                        "value": str(value),
                        "short": False
                    })
            
            # Build payload
            text = f"{emoji} TraderMade Streaming Alert"
            attachments = [{
                "color": color,
                "title": "TraderMade Streaming Alert",
                "text": error_message,
                "fields": fields,
                "footer": "FX Forecast System",
                "ts": int(time.time())
            }]
            
            payload = {
                "text": text,
                "attachments": attachments
            }
            
            # Send notification
            success = self._send_webhook_message(payload)
            
            if success:
                self.last_notification[error_type] = time.time()
                self.logger.info(f"Slack notification sent for {error_type}")
            else:
                self.logger.error(f"Failed to send Slack notification for {error_type}")
                
            return success
            
        except Exception as e:
            # Don't let Slack errors crash the main process
            self.logger.error(f"Error sending Slack notification: {e}")
            return False
    
    def _can_notify(self, error_type: str) -> bool:
        """
        Check if notification can be sent (rate limiting)
        
        Args:
            error_type: Type of error
            
        Returns:
            True if notification can be sent
        """
        if error_type not in self.last_notification:
            return True
            
        elapsed = time.time() - self.last_notification[error_type]
        return elapsed >= self.notification_cooldown
    
    def notify_auth_failure(self, error: Exception) -> bool:
        """Convenience method for authentication failures"""
        return self.notify_error(
            "AUTH_ERROR",
            "TraderMade API authentication failed. Please check API key configuration.",
            severity="CRITICAL",
            details={
                "error": str(error),
                "action": "Check TRADERMADE_STREAMING_API_KEY in .env file"
            }
        )
    
    def notify_repeated_connection_failure(self, failure_count: int, last_error: Exception) -> bool:
        """Convenience method for repeated connection failures"""
        return self.notify_error(
            "REPEATED_CONNECTION_FAILURE",
            f"WebSocket connection failed {failure_count} times consecutively",
            severity="ERROR",
            details={
                "failure_count": failure_count,
                "last_error": str(last_error),
                "action": "Check network connectivity and TraderMade service status"
            }
        )
    
    def notify_unexpected_error(self, error: Exception, context: str = "") -> bool:
        """Convenience method for unexpected errors"""
        return self.notify_error(
            "UNKNOWN_ERROR",
            f"Unexpected error in TraderMade streaming{f': {context}' if context else ''}",
            severity="ERROR",
            details={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context or "N/A"
            }
        )
    
    def notify_data_format_errors(self, error_count: int, sample_error: str) -> bool:
        """Convenience method for data format errors"""
        return self.notify_error(
            "DATA_ERROR",
            f"Multiple data format errors detected ({error_count} occurrences)",
            severity="WARNING",
            details={
                "error_count": error_count,
                "sample_error": sample_error,
                "action": "TraderMade may have changed their data format"
            }
        )