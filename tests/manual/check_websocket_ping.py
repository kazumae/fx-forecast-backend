#!/usr/bin/env python3
"""
Check WebSocket ping/pong implementation
"""
import time

# Check how the WebSocket is configured
print("Checking WebSocket configuration...")
print()

print("From the websocket_manager.py code:")
print("- ping_interval = config.heartbeat_interval (30 seconds by default)")
print("- ping_timeout = calculated to be less than ping_interval")
print("- The websocket-client library automatically sends pings at ping_interval")
print("- It expects pongs within ping_timeout seconds")
print()

print("Current implementation:")
print("1. websocket-client library handles automatic ping/pong")
print("2. Our HeartbeatManager is trying to send additional pings")
print("3. This might be causing conflicts")
print()

print("Recommendation:")
print("Since websocket-client already has built-in ping/pong mechanism,")
print("we should rely on that and just monitor the connection state.")
print("The HeartbeatManager should focus on monitoring, not sending pings.")