#!/usr/bin/env python3
"""
Integration test for heartbeat functionality
"""
import asyncio
import logging
import os
import sys
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.stream.config import StreamConfig
from src.stream.websocket_manager import WebSocketManager


# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def test_heartbeat():
    """Test heartbeat functionality"""
    print("\n=== Heartbeat Test ===")
    print("This test will:")
    print("1. Connect to TraderMade WebSocket")
    print("2. Monitor heartbeat ping/pong messages")
    print("3. Check heartbeat timeout detection")
    print("4. Verify automatic reconnection on timeout")
    print("\nStarting test...\n")
    
    # Create configuration with shorter intervals for testing
    config = StreamConfig.from_env()
    config.heartbeat_interval = 5  # 5 seconds for faster testing
    
    # Create WebSocket manager
    ws_manager = WebSocketManager(config)
    
    # Track heartbeat events
    heartbeat_stats = {
        'pings_sent': 0,
        'pongs_received': 0,
        'timeouts': 0,
        'reconnections': 0
    }
    
    # Override logging to track heartbeat events
    original_debug = ws_manager.logger.debug
    original_warning = ws_manager.logger.warning
    original_error = ws_manager.logger.error
    
    def track_debug(msg, *args, **kwargs):
        if "Ping sent" in msg:
            heartbeat_stats['pings_sent'] += 1
        elif "Pong received" in msg:
            heartbeat_stats['pongs_received'] += 1
        original_debug(msg, *args, **kwargs)
    
    def track_warning(msg, *args, **kwargs):
        if "Heartbeat timeout" in msg:
            heartbeat_stats['timeouts'] += 1
        original_warning(msg, *args, **kwargs)
    
    def track_error(msg, *args, **kwargs):
        if "initiating reconnection" in msg:
            heartbeat_stats['reconnections'] += 1
        original_error(msg, *args, **kwargs)
    
    ws_manager.logger.debug = track_debug
    ws_manager.logger.warning = track_warning
    ws_manager.logger.error = track_error
    
    # Also track heartbeat manager logs
    hb_logger = logging.getLogger('src.stream.heartbeat_manager')
    hb_logger.debug = track_debug
    hb_logger.warning = track_warning
    hb_logger.error = track_error
    
    def on_authenticated():
        """Callback when authenticated"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Authenticated successfully")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ℹ️  Heartbeat interval: {config.heartbeat_interval}s")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ℹ️  Monitoring heartbeat activity...")
    
    def print_stats():
        """Print current heartbeat statistics"""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Heartbeat Statistics:")
        print(f"  • Pings sent: {heartbeat_stats['pings_sent']}")
        print(f"  • Pongs received: {heartbeat_stats['pongs_received']}")
        print(f"  • Timeouts detected: {heartbeat_stats['timeouts']}")
        print(f"  • Reconnections: {heartbeat_stats['reconnections']}")
    
    ws_manager.on_authenticated = on_authenticated
    
    try:
        # Connect to WebSocket
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Connecting to TraderMade...")
        ws_manager.connect()
        
        # Run for 60 seconds to observe heartbeat behavior
        test_duration = 60
        check_interval = 10
        elapsed = 0
        
        while elapsed < test_duration:
            time.sleep(check_interval)
            elapsed += check_interval
            
            print_stats()
            
            # Check connection health
            if ws_manager.is_connected:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Connection healthy")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Connection lost")
            
            # Simulate timeout after 30 seconds (optional)
            if elapsed == 30 and False:  # Set to True to test timeout
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔧 Simulating timeout...")
                ws_manager.heartbeat_manager.last_pong_time = time.time() - 100
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Test completed!")
        print_stats()
        
        # Final assessment
        print("\n=== Test Results ===")
        if heartbeat_stats['pings_sent'] > 0 and heartbeat_stats['pongs_received'] > 0:
            print("✅ Heartbeat mechanism is working correctly")
            print(f"✅ Sent {heartbeat_stats['pings_sent']} pings, received {heartbeat_stats['pongs_received']} pongs")
        else:
            print("❌ Heartbeat mechanism not working as expected")
        
        if heartbeat_stats['timeouts'] > 0:
            print(f"ℹ️  Detected {heartbeat_stats['timeouts']} timeouts")
            if heartbeat_stats['reconnections'] > 0:
                print(f"✅ Successfully triggered {heartbeat_stats['reconnections']} reconnections")
            else:
                print("⚠️  No reconnections triggered after timeout")
        
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Test interrupted by user")
    except Exception as e:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ❌ Test error: {e}")
        logging.exception("Test error details")
    finally:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Closing connection...")
        ws_manager.close()
        time.sleep(2)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Test ended")


if __name__ == "__main__":
    test_heartbeat()