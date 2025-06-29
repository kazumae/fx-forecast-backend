#!/usr/bin/env python3
"""
Test script for Slack error notifications
"""
import os
import sys
import time

# Add backend directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.stream.slack_error_notifier import SlackErrorNotifier
from src.stream.error_handler import ErrorHandler, ErrorType


def test_slack_notifications():
    """Test various Slack notification scenarios"""
    print("Testing Slack Error Notifications...")
    
    # Create notifier with short cooldown for testing
    slack_notifier = SlackErrorNotifier(notification_cooldown=5)
    error_handler = ErrorHandler(slack_notifier=slack_notifier)
    
    # Test 1: Authentication Error
    print("\n1. Testing Authentication Error...")
    auth_error = Exception("401 Unauthorized: Invalid API key")
    error_info = error_handler.handle_error(auth_error, context="WebSocket authentication")
    print(f"   Result: {error_info}")
    
    # Test 2: Network Error (single)
    print("\n2. Testing Single Network Error...")
    network_error = ConnectionError("Connection refused")
    error_info = error_handler.handle_error(network_error, context="WebSocket connection")
    print(f"   Result: {error_info}")
    
    # Test 3: Repeated Network Errors (should trigger notification on 5th)
    print("\n3. Testing Repeated Network Errors...")
    for i in range(6):
        print(f"   Network error #{i+1}")
        error_info = error_handler.handle_error(
            ConnectionError(f"Connection failed attempt {i+1}"),
            context="WebSocket reconnection"
        )
        time.sleep(0.5)
    
    # Test 4: Data Format Errors (should trigger on 10th)
    print("\n4. Testing Data Format Errors...")
    for i in range(12):
        print(f"   Data error #{i+1}")
        error_info = error_handler.handle_error(
            ValueError(f"Invalid JSON data: {i+1}"),
            context="Message parsing"
        )
        time.sleep(0.2)
    
    # Test 5: Unknown Error
    print("\n5. Testing Unknown Error...")
    unknown_error = RuntimeError("Something unexpected happened")
    error_info = error_handler.handle_error(unknown_error, context="WebSocket handler")
    print(f"   Result: {error_info}")
    
    # Test 6: Rate Limiting (try same error type within cooldown)
    print("\n6. Testing Rate Limiting...")
    print("   First notification (should send):")
    error_handler.handle_error(auth_error, context="First auth error")
    print("   Second notification within cooldown (should skip):")
    time.sleep(2)
    error_handler.handle_error(auth_error, context="Second auth error")
    
    # Test 7: Error Summary
    print("\n7. Error Summary:")
    summary = error_handler.get_error_summary()
    print(f"   {summary}")
    
    print("\n✅ Slack notification tests completed!")
    print("\nCheck your Slack channel for the notifications.")


if __name__ == "__main__":
    test_slack_notifications()