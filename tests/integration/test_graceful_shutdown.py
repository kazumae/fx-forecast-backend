#!/usr/bin/env python3
"""
Test graceful shutdown functionality
"""
import os
import sys
import time
import signal
import subprocess
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def test_graceful_shutdown_local():
    """Test graceful shutdown in local environment"""
    print("=== Testing Graceful Shutdown (Local) ===")
    
    from src.stream.graceful_shutdown import GracefulShutdownHandler
    from src.stream.websocket_manager import WebSocketManager
    from src.stream.data_processor import DataProcessor
    from src.stream.config import StreamConfig
    
    # Mock components
    class MockWebSocketManager:
        def __init__(self):
            self._should_run = True
            self.error_handler = type('obj', (object,), {
                'get_error_summary': lambda: {"total_errors": 5, "errors": ["test1", "test2"]}
            })
            
        def close(self):
            print("  WebSocket manager closed")
            self._should_run = False
    
    class MockDataProcessor:
        def display_summary(self):
            print("  Data processor summary displayed")
    
    # Create components
    ws_manager = MockWebSocketManager()
    data_processor = MockDataProcessor()
    
    # Create shutdown handler
    handler = GracefulShutdownHandler(
        websocket_manager=ws_manager,
        data_processor=data_processor,
        timeout=5
    )
    
    # Setup signal handlers
    handler.setup_signal_handlers()
    print("✓ Signal handlers registered")
    
    # Test manual trigger
    print("\nTesting manual shutdown trigger...")
    
    def trigger_shutdown():
        time.sleep(1)
        handler.trigger_shutdown("Test trigger")
    
    trigger_thread = threading.Thread(target=trigger_shutdown)
    trigger_thread.start()
    
    # Wait for shutdown
    shutdown_completed = handler.wait_for_shutdown(timeout=3)
    
    if shutdown_completed:
        print("✓ Graceful shutdown completed successfully")
    else:
        print("✗ Shutdown timeout or failed")
    
    # Cleanup
    handler.restore_signal_handlers()
    print("\n✓ Test completed")


def test_signal_handling():
    """Test signal handling"""
    print("\n=== Testing Signal Handling ===")
    
    # Create a test script that handles signals
    test_script = """
import signal
import time
import sys

def handle_signal(signum, frame):
    print(f"Received signal {signum}")
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

print("Process started, PID:", os.getpid())
for i in range(10):
    print(f"Running... {i}")
    time.sleep(1)
"""
    
    # Write test script
    with open('/tmp/test_signal.py', 'w') as f:
        f.write(test_script)
    
    # Start process
    proc = subprocess.Popen(
        [sys.executable, '/tmp/test_signal.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    print(f"Started test process with PID: {proc.pid}")
    
    # Give it time to start
    time.sleep(2)
    
    # Send SIGTERM
    print("Sending SIGTERM...")
    proc.send_signal(signal.SIGTERM)
    
    # Wait for process to exit
    try:
        stdout, stderr = proc.communicate(timeout=5)
        print(f"Process exited with code: {proc.returncode}")
        if "Received signal" in stdout:
            print("✓ Signal was handled correctly")
        else:
            print("✗ Signal handling failed")
    except subprocess.TimeoutExpired:
        print("✗ Process did not exit within timeout")
        proc.kill()
    
    # Cleanup
    os.unlink('/tmp/test_signal.py')
    

def test_docker_shutdown():
    """Test instructions for Docker environment"""
    print("\n=== Docker Shutdown Test Instructions ===")
    print("""
To test graceful shutdown in Docker:

1. Start the service:
   docker-compose up tradermade-stream

2. In another terminal, send SIGTERM:
   docker-compose exec tradermade-stream kill -TERM 1

3. Or use Ctrl+C in the first terminal

4. Check the logs for:
   - "Received SIGTERM, initiating graceful shutdown"
   - "Step 1/5: Stopping new data reception"
   - "Step 2/5: Processing remaining data"
   - "Step 3/5: Closing WebSocket connection"
   - "Step 4/5: Generating error summary"
   - "Step 5/5: Final cleanup"
   - "Graceful shutdown completed in X.XX seconds"

5. Verify exit code:
   docker-compose ps
   # Should show Exit 0 for graceful shutdown
""")


if __name__ == "__main__":
    test_graceful_shutdown_local()
    test_signal_handling()
    test_docker_shutdown()
    print("\n✅ All local tests completed!")