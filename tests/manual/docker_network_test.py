#!/usr/bin/env python3
"""
Test script to simulate WebSocket disconnection for reconnection testing
"""
import time
import docker
import sys


def main():
    """Test auto-reconnection by simulating network issues"""
    client = docker.from_env()
    
    try:
        # Get the container
        container = client.containers.get("tradermade-stream")
        
        print("Starting reconnection test...")
        print(f"Container status: {container.status}")
        
        # Wait for normal operation
        print("\nWaiting 10 seconds for normal operation...")
        time.sleep(10)
        
        # Simulate network disconnection by pausing the container
        print("\nSimulating network disconnection (pausing container)...")
        container.pause()
        
        # Keep paused for 15 seconds
        print("Container paused. Waiting 15 seconds...")
        time.sleep(15)
        
        # Resume container
        print("\nResuming container...")
        container.unpause()
        
        # Wait to see reconnection
        print("Waiting 30 seconds to observe reconnection behavior...")
        time.sleep(30)
        
        print("\nTest completed. Check logs for reconnection behavior.")
        
    except docker.errors.NotFound:
        print("Container 'tradermade-stream' not found. Make sure it's running.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()