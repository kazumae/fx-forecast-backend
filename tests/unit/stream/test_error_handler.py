#!/usr/bin/env python3
"""Error Handler単体テスト"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from src.stream.error_handler import ErrorHandler, ErrorType, ErrorSeverity
import websocket


def test_error_classification():
    """エラー分類のテスト"""
    print("=== Error Classification Tests ===")
    handler = ErrorHandler()
    
    # Network errors
    network_errors = [
        websocket.WebSocketConnectionClosedException(),
        ConnectionError("Connection refused"),
        OSError("Network unreachable")
    ]
    
    for error in network_errors:
        error_type = handler.classify_error(error)
        assert error_type == ErrorType.NETWORK_ERROR, f"Expected NETWORK_ERROR, got {error_type}"
        print(f"✓ {type(error).__name__} -> {error_type.value}")
    
    # Auth errors
    auth_errors = [
        Exception("401 Unauthorized"),
        Exception("403 Forbidden"),
        Exception("Authentication failed")
    ]
    
    for error in auth_errors:
        error_type = handler.classify_error(error)
        assert error_type == ErrorType.AUTH_ERROR, f"Expected AUTH_ERROR, got {error_type}"
        print(f"✓ {str(error)} -> {error_type.value}")
    
    # Data errors
    data_errors = [
        ValueError("Invalid JSON"),
        TypeError("Expected string")
    ]
    
    for error in data_errors:
        error_type = handler.classify_error(error)
        assert error_type == ErrorType.DATA_ERROR, f"Expected DATA_ERROR, got {error_type}"
        print(f"✓ {type(error).__name__} -> {error_type.value}")
    
    print("\nAll classification tests passed!")


def test_severity_levels():
    """セベリティレベルのテスト"""
    print("\n=== Severity Level Tests ===")
    handler = ErrorHandler()
    
    severity_map = {
        ErrorType.NETWORK_ERROR: ErrorSeverity.WARNING,
        ErrorType.AUTH_ERROR: ErrorSeverity.CRITICAL,
        ErrorType.DATA_ERROR: ErrorSeverity.WARNING,
        ErrorType.TIMEOUT_ERROR: ErrorSeverity.WARNING,
        ErrorType.RATE_LIMIT_ERROR: ErrorSeverity.ERROR,
        ErrorType.UNKNOWN_ERROR: ErrorSeverity.ERROR
    }
    
    for error_type, expected_severity in severity_map.items():
        severity = handler.get_severity(error_type)
        assert severity == expected_severity, f"Expected {expected_severity}, got {severity}"
        print(f"✓ {error_type.value} -> {severity.value}")
    
    print("\nAll severity tests passed!")


def test_error_counting():
    """エラーカウントのテスト"""
    print("\n=== Error Counting Tests ===")
    handler = ErrorHandler()
    
    # Generate some errors
    for i in range(3):
        handler.handle_error(ConnectionError("Test"), context="Test context")
    
    for i in range(2):
        handler.handle_error(ValueError("Test"), context="Test context")
    
    summary = handler.get_error_summary()
    assert summary["total_errors"] == 5
    assert summary["error_counts"][ErrorType.NETWORK_ERROR] == 3
    assert summary["error_counts"][ErrorType.DATA_ERROR] == 2
    print(f"✓ Total errors: {summary['total_errors']}")
    print(f"✓ Network errors: {summary['error_counts'][ErrorType.NETWORK_ERROR]}")
    print(f"✓ Data errors: {summary['error_counts'][ErrorType.DATA_ERROR]}")
    
    # Reset and verify
    handler.reset_error_counts()
    summary = handler.get_error_summary()
    assert summary["total_errors"] == 0
    print("✓ Error counts reset successfully")
    
    print("\nAll counting tests passed!")


def test_reconnection_logic():
    """再接続ロジックのテスト"""
    print("\n=== Reconnection Logic Tests ===")
    handler = ErrorHandler()
    
    # Should reconnect for network errors
    assert handler.should_reconnect(ErrorType.NETWORK_ERROR) == True
    print("✓ Network error -> should reconnect")
    
    # Should not reconnect for auth errors
    assert handler.should_reconnect(ErrorType.AUTH_ERROR) == False
    print("✓ Auth error -> should not reconnect")
    
    # Should not reconnect for repeated data errors
    for i in range(11):
        handler.handle_error(ValueError("Test"))
    assert handler.should_reconnect(ErrorType.DATA_ERROR) == False
    print("✓ Repeated data errors -> should not reconnect")
    
    print("\nAll reconnection tests passed!")


if __name__ == "__main__":
    test_error_classification()
    test_severity_levels()
    test_error_counting()
    test_reconnection_logic()
    print("\n✅ All tests passed!")