"""
Error Handler for TraderMade Stream
"""
import logging
from enum import Enum
from typing import Optional, Any, TYPE_CHECKING
import websocket

if TYPE_CHECKING:
    from .slack_error_notifier import SlackErrorNotifier


class ErrorType(Enum):
    """Error classification"""
    NETWORK_ERROR = "network_error"
    AUTH_ERROR = "auth_error"
    DATA_ERROR = "data_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    UNKNOWN_ERROR = "unknown_error"


class ErrorSeverity(Enum):
    """Error severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorHandler:
    """Centralized error handling for WebSocket streaming"""
    
    def __init__(self, slack_notifier: Optional['SlackErrorNotifier'] = None):
        """Initialize error handler
        
        Args:
            slack_notifier: Optional Slack notifier for error alerts
        """
        self.logger = logging.getLogger(__name__)
        self.error_counts = {}  # Track error counts by type
        self.slack_notifier = slack_notifier
        self.consecutive_network_failures = 0
        
    def classify_error(self, error: Exception) -> ErrorType:
        """Classify error into appropriate type
        
        Args:
            error: The exception to classify
            
        Returns:
            ErrorType classification
        """
        error_str = str(error).lower()
        error_type_name = type(error).__name__
        
        # Network errors
        if isinstance(error, (
            websocket.WebSocketConnectionClosedException,
            websocket.WebSocketTimeoutException,
            ConnectionError,
            OSError
        )):
            return ErrorType.NETWORK_ERROR
            
        # Authentication errors
        if any(auth_indicator in error_str for auth_indicator in [
            "401", "403", "unauthorized", "forbidden", "auth"
        ]):
            return ErrorType.AUTH_ERROR
            
        # Data format errors
        if "json" in error_str or isinstance(error, (ValueError, TypeError)):
            return ErrorType.DATA_ERROR
            
        # Timeout errors
        if "timeout" in error_str:
            return ErrorType.TIMEOUT_ERROR
            
        # Rate limit errors
        if any(rate_indicator in error_str for rate_indicator in [
            "429", "rate limit", "too many requests"
        ]):
            return ErrorType.RATE_LIMIT_ERROR
            
        return ErrorType.UNKNOWN_ERROR
    
    def get_severity(self, error_type: ErrorType) -> ErrorSeverity:
        """Determine error severity based on type
        
        Args:
            error_type: The error type
            
        Returns:
            ErrorSeverity level
        """
        severity_map = {
            ErrorType.NETWORK_ERROR: ErrorSeverity.WARNING,
            ErrorType.AUTH_ERROR: ErrorSeverity.CRITICAL,
            ErrorType.DATA_ERROR: ErrorSeverity.WARNING,
            ErrorType.TIMEOUT_ERROR: ErrorSeverity.WARNING,
            ErrorType.RATE_LIMIT_ERROR: ErrorSeverity.ERROR,
            ErrorType.UNKNOWN_ERROR: ErrorSeverity.ERROR
        }
        return severity_map.get(error_type, ErrorSeverity.ERROR)
    
    def handle_error(
        self, 
        error: Exception, 
        context: Optional[str] = None,
        error_type: Optional[ErrorType] = None
    ) -> dict:
        """Handle error with appropriate logging and actions
        
        Args:
            error: The exception to handle
            context: Additional context about where error occurred
            error_type: Override error classification if known
            
        Returns:
            Dictionary with error details and recommended action
        """
        # Classify error if not provided
        if error_type is None:
            error_type = self.classify_error(error)
            
        # Get severity
        severity = self.get_severity(error_type)
        
        # Track error count
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        # Create error info
        error_info = {
            "type": error_type.value,
            "severity": severity.value,
            "message": str(error),
            "error_class": type(error).__name__,
            "context": context,
            "count": self.error_counts[error_type]
        }
        
        # Log based on severity
        log_message = f"[{error_type.value}] {error}"
        if context:
            log_message = f"{context}: {log_message}"
            
        if severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message, exc_info=True)
            error_info["action"] = "terminate"
            # Send Slack notification for critical errors
            if self.slack_notifier and error_type == ErrorType.AUTH_ERROR:
                self.slack_notifier.notify_auth_failure(error)
        elif severity == ErrorSeverity.ERROR:
            self.logger.error(log_message, exc_info=True)
            error_info["action"] = "reconnect"
        elif severity == ErrorSeverity.WARNING:
            self.logger.warning(log_message)
            error_info["action"] = "continue"
        else:
            self.logger.info(log_message)
            error_info["action"] = "continue"
            
        # Track consecutive network failures
        if error_type == ErrorType.NETWORK_ERROR:
            self.consecutive_network_failures += 1
            # Send notification if too many consecutive failures
            if self.consecutive_network_failures >= 5 and self.slack_notifier:
                self.slack_notifier.notify_repeated_connection_failure(
                    self.consecutive_network_failures, error
                )
        else:
            self.consecutive_network_failures = 0
            
        # Send notification for unexpected errors
        if error_type == ErrorType.UNKNOWN_ERROR and self.slack_notifier:
            self.slack_notifier.notify_unexpected_error(error, context)
            
        # Send notification for repeated data errors
        if (error_type == ErrorType.DATA_ERROR and 
            self.error_counts.get(error_type, 0) >= 10 and 
            self.error_counts.get(error_type, 0) % 10 == 0 and 
            self.slack_notifier):
            self.slack_notifier.notify_data_format_errors(
                self.error_counts[error_type], str(error)
            )
            
        # Add specific recommendations
        error_info["recommendation"] = self._get_recommendation(error_type)
        
        return error_info
    
    def _get_recommendation(self, error_type: ErrorType) -> str:
        """Get specific recommendation for error type
        
        Args:
            error_type: The error type
            
        Returns:
            Recommendation string
        """
        recommendations = {
            ErrorType.NETWORK_ERROR: "Check network connection and retry",
            ErrorType.AUTH_ERROR: "Verify API key and credentials",
            ErrorType.DATA_ERROR: "Skip malformed data and continue",
            ErrorType.TIMEOUT_ERROR: "Increase timeout or retry",
            ErrorType.RATE_LIMIT_ERROR: "Reduce request frequency",
            ErrorType.UNKNOWN_ERROR: "Log details and retry with backoff"
        }
        return recommendations.get(error_type, "Log error and continue")
    
    def should_reconnect(self, error_type: ErrorType) -> bool:
        """Determine if reconnection should be attempted
        
        Args:
            error_type: The error type
            
        Returns:
            True if reconnection is recommended
        """
        # Don't reconnect for authentication errors
        if error_type == ErrorType.AUTH_ERROR:
            return False
            
        # Don't reconnect for repeated data errors
        if error_type == ErrorType.DATA_ERROR and self.error_counts.get(error_type, 0) > 10:
            return False
            
        return error_type in [
            ErrorType.NETWORK_ERROR,
            ErrorType.TIMEOUT_ERROR,
            ErrorType.UNKNOWN_ERROR
        ]
    
    def reset_error_counts(self):
        """Reset error counts (call after successful connection)"""
        self.error_counts = {}
        self.consecutive_network_failures = 0
        self.logger.debug("Error counts reset")
    
    def get_error_summary(self) -> dict:
        """Get summary of errors encountered
        
        Returns:
            Dictionary with error statistics
        """
        total_errors = sum(self.error_counts.values())
        return {
            "total_errors": total_errors,
            "error_counts": dict(self.error_counts),
            "most_common": max(self.error_counts.items(), key=lambda x: x[1])[0].value if self.error_counts else None
        }