#!/usr/bin/env python3
"""Test logging utilities"""

import os
import sys
import logging
from io import StringIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from src.stream.logging_utils import SensitiveDataFilter, ContextLogger


def test_sensitive_data_filter():
    """Test sensitive data masking"""
    print("=== Testing Sensitive Data Filter ===")
    
    # Setup test logger
    logger = logging.getLogger("test_filter")
    logger.setLevel(logging.DEBUG)
    
    # String handler to capture output
    string_handler = logging.StreamHandler(StringIO())
    string_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(message)s')
    string_handler.setFormatter(formatter)
    logger.addHandler(string_handler)
    
    # Add sensitive data filter
    test_api_key = "wsOqQRQFTbCluWfkNdmw"
    filter = SensitiveDataFilter([test_api_key])
    string_handler.addFilter(filter)
    
    # Test cases
    test_cases = [
        {
            "message": f"Connecting with API key: {test_api_key}",
            "expected": "Connecting with API key: wsOq...Ndmw",
            "description": "Direct API key masking"
        },
        {
            "message": 'Config: {"api_key": "secret123456789", "url": "example.com"}',
            "expected": 'Config: {"api_key": "***MASKED***", "url": "example.com"}',
            "description": "JSON key masking"
        },
        {
            "message": "Authorization: Bearer abc123def456ghi789",
            "expected": "Authorization: Bearer ***MASKED***",
            "description": "Bearer token masking"
        },
        {
            "message": "WebSocket URL: wss://user:password123@example.com/ws",
            "expected": "WebSocket URL: wss://user:***MASKED***@example.com/ws",
            "description": "WebSocket URL credential masking"
        },
        {
            "message": "Normal log message without secrets",
            "expected": "Normal log message without secrets",
            "description": "Normal message unchanged"
        }
    ]
    
    for test in test_cases:
        # Clear the string buffer
        string_handler.stream = StringIO()
        
        # Log the message
        logger.info(test["message"])
        
        # Get the output
        output = string_handler.stream.getvalue().strip()
        
        # Check if masking worked
        if test["expected"] in output:
            print(f"✓ {test['description']}")
        else:
            print(f"✗ {test['description']}")
            print(f"  Expected: {test['expected']}")
            print(f"  Got: {output}")
    
    # Remove handler
    logger.removeHandler(string_handler)
    print()


def test_context_logger():
    """Test context logger"""
    print("=== Testing Context Logger ===")
    
    # Setup base logger
    base_logger = logging.getLogger("test_context")
    base_logger.setLevel(logging.DEBUG)
    
    # String handler to capture output
    string_handler = logging.StreamHandler(StringIO())
    string_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(levelname)s] %(message)s')
    string_handler.setFormatter(formatter)
    base_logger.addHandler(string_handler)
    
    # Create context logger
    context_logger = ContextLogger(base_logger, "WebSocket")
    
    # Test different log levels
    test_messages = [
        (context_logger.debug, "Debug message"),
        (context_logger.info, "Info message"),
        (context_logger.warning, "Warning message"),
        (context_logger.error, "Error message"),
    ]
    
    for log_method, message in test_messages:
        # Clear buffer
        string_handler.stream = StringIO()
        
        # Log message
        log_method(message)
        
        # Check output
        output = string_handler.stream.getvalue().strip()
        if "[WebSocket]" in output and message in output:
            print(f"✓ Context added to {log_method.__name__}: {output}")
        else:
            print(f"✗ Context missing from {log_method.__name__}")
    
    # Remove handler
    base_logger.removeHandler(string_handler)
    print()


def test_log_levels():
    """Test log level filtering"""
    print("=== Testing Log Levels ===")
    
    # Setup logger
    logger = logging.getLogger("test_levels")
    logger.setLevel(logging.DEBUG)
    
    # Console handler (INFO level)
    console_stream = StringIO()
    console_handler = logging.StreamHandler(console_stream)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    
    # File handler (DEBUG level)
    file_stream = StringIO()
    file_handler = logging.StreamHandler(file_stream)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    # Log at different levels
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    
    # Check console output (should not have DEBUG)
    console_output = console_stream.getvalue()
    if "DEBUG" not in console_output and "INFO" in console_output:
        print("✓ Console handler filters DEBUG messages")
    else:
        print("✗ Console handler filtering failed")
    
    # Check file output (should have all levels)
    file_output = file_stream.getvalue()
    if all(level in file_output for level in ["DEBUG", "INFO", "WARNING", "ERROR"]):
        print("✓ File handler captures all log levels")
    else:
        print("✗ File handler missing some levels")
    
    # Clean up
    logger.removeHandler(console_handler)
    logger.removeHandler(file_handler)
    print()


def test_error_with_traceback():
    """Test error logging with traceback"""
    print("=== Testing Error with Traceback ===")
    
    # Setup logger
    logger = logging.getLogger("test_traceback")
    logger.setLevel(logging.DEBUG)
    
    # String handler
    string_handler = logging.StreamHandler(StringIO())
    string_handler.setLevel(logging.DEBUG)
    logger.addHandler(string_handler)
    
    # Generate an error with traceback
    try:
        # Intentionally cause an error
        result = 1 / 0
    except ZeroDivisionError as e:
        logger.error("Division by zero error", exc_info=True)
    
    # Check output
    output = string_handler.stream.getvalue()
    if "Traceback" in output and "ZeroDivisionError" in output:
        print("✓ Error logged with full traceback")
    else:
        print("✗ Traceback missing from error log")
    
    # Clean up
    logger.removeHandler(string_handler)
    print()


if __name__ == "__main__":
    test_sensitive_data_filter()
    test_context_logger()
    test_log_levels()
    test_error_with_traceback()
    print("✅ All logging tests completed!")