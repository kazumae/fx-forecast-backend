"""
Logging utilities for TraderMade Stream
"""
import logging
import re
from typing import List, Optional, Pattern


class SensitiveDataFilter(logging.Filter):
    """Filter to mask sensitive information in logs"""
    
    def __init__(self, patterns: Optional[List[str]] = None, name: str = ''):
        """
        Initialize sensitive data filter
        
        Args:
            patterns: List of exact strings to mask
            name: Logger name to filter
        """
        super().__init__(name)
        self.patterns = patterns or []
        
        # Common patterns for sensitive data
        self.regex_patterns: List[Pattern] = [
            # API keys (various formats)
            re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([A-Za-z0-9_\-]{10,})(["\']?)', re.IGNORECASE),
            # Bearer tokens
            re.compile(r'(bearer\s+)([A-Za-z0-9_\-\.]+)', re.IGNORECASE),
            # Basic auth
            re.compile(r'(basic\s+)([A-Za-z0-9+/=]+)', re.IGNORECASE),
            # WebSocket URLs with credentials
            re.compile(r'(wss?://[^@]+:)([^@]+)(@)'),
            # JSON keys for secrets
            re.compile(r'(["\'](?:password|secret|token|key)["\']:\s*["\'])([^"\']+)(["\'])', re.IGNORECASE),
        ]
        
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log record and mask sensitive data
        
        Args:
            record: Log record to filter
            
        Returns:
            True (always passes the record through)
        """
        # Get the formatted message
        msg = record.getMessage()
        
        # Mask exact patterns
        for pattern in self.patterns:
            if pattern and pattern in msg:
                # Keep first 4 and last 4 characters for debugging
                if len(pattern) > 8:
                    masked = f"{pattern[:4]}...{pattern[-4:]}"
                else:
                    masked = "***MASKED***"
                msg = msg.replace(pattern, masked)
        
        # Mask regex patterns
        for regex in self.regex_patterns:
            def replace_match(match):
                groups = match.groups()
                if len(groups) >= 2:
                    # Keep prefix and suffix, mask the sensitive part
                    prefix = groups[0] if groups else ''
                    sensitive = groups[1] if len(groups) > 1 else ''
                    suffix = groups[2] if len(groups) > 2 else ''
                    
                    # Mask the sensitive part
                    if len(sensitive) > 8:
                        masked = f"{sensitive[:4]}...{sensitive[-4:]}"
                    else:
                        masked = "***MASKED***"
                    
                    return f"{prefix}{masked}{suffix}"
                return match.group(0)
            
            msg = regex.sub(replace_match, msg)
        
        # Update the record's message
        record.msg = msg
        record.args = ()  # Clear args to prevent formatting issues
        
        return True


class ContextLogger:
    """Logger wrapper that adds context to log messages"""
    
    def __init__(self, logger: logging.Logger, context: str):
        """
        Initialize context logger
        
        Args:
            logger: Base logger instance
            context: Context string to prepend to messages
        """
        self.logger = logger
        self.context = context
    
    def _log(self, level: int, msg: str, *args, **kwargs):
        """Internal log method with context"""
        self.logger.log(level, f"[{self.context}] {msg}", *args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs):
        """Log debug message with context"""
        self._log(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        """Log info message with context"""
        self._log(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        """Log warning message with context"""
        self._log(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        """Log error message with context"""
        self._log(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        """Log critical message with context"""
        self._log(logging.CRITICAL, msg, *args, **kwargs)


def setup_logger_with_filter(
    logger: logging.Logger,
    sensitive_patterns: Optional[List[str]] = None
) -> logging.Logger:
    """
    Setup logger with sensitive data filter
    
    Args:
        logger: Logger instance to configure
        sensitive_patterns: List of patterns to mask
        
    Returns:
        Configured logger
    """
    # Add sensitive data filter
    filter = SensitiveDataFilter(sensitive_patterns)
    
    # Add filter to all handlers
    for handler in logger.handlers:
        handler.addFilter(filter)
    
    # Also add to the logger itself
    logger.addFilter(filter)
    
    return logger