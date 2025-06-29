#!/usr/bin/env python3
"""
Simple test to verify heartbeat is working
"""
import subprocess
import time
import sys


def test_heartbeat(duration=120):
    """Test heartbeat monitoring for specified duration"""
    print(f"\n=== Testing Heartbeat for {duration} seconds ===")
    print("Monitoring connection health checks...\n")
    
    start_time = time.time()
    health_checks = 0
    
    # Enable debug logging
    print("Setting LOG_LEVEL to DEBUG...")
    subprocess.run(['docker-compose', 'exec', 'tradermade-stream', 'sh', '-c', 
                   'export LOG_LEVEL=DEBUG'])
    
    # Monitor logs
    process = subprocess.Popen(
        ['docker-compose', 'logs', '-f', '--tail=0', 'tradermade-stream'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    try:
        while time.time() - start_time < duration:
            line = process.stdout.readline()
            if not line:
                continue
            
            # Look for heartbeat-related messages
            if "Connection healthy" in line:
                health_checks += 1
                elapsed = time.time() - start_time
                print(f"[{elapsed:6.1f}s] ✅ Health check #{health_checks}: Connection healthy")
            elif "Activity timeout" in line:
                print(f"[{time.time() - start_time:6.1f}s] ⚠️  Activity timeout detected!")
            elif "Heartbeat monitor started" in line:
                print(f"[{time.time() - start_time:6.1f}s] 🚀 Heartbeat monitor started")
            elif "initiating reconnection" in line:
                print(f"[{time.time() - start_time:6.1f}s] 🔄 Reconnection triggered")
            elif "Pong received" in line:
                print(f"[{time.time() - start_time:6.1f}s] 📥 Pong received")
                
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    finally:
        process.terminate()
        process.wait()
    
    # Summary
    elapsed = time.time() - start_time
    expected_checks = int(elapsed / 30)  # One check every 30 seconds
    
    print(f"\n=== Summary ===")
    print(f"Test duration: {elapsed:.1f} seconds")
    print(f"Health checks performed: {health_checks}")
    print(f"Expected checks (30s interval): ~{expected_checks}")
    
    if health_checks > 0:
        print("✅ Heartbeat monitoring is working")
    else:
        print("❌ No heartbeat activity detected")
        print("\nTroubleshooting:")
        print("1. Check if the service is running: docker-compose ps")
        print("2. Check service logs: docker-compose logs tradermade-stream")
        print("3. Verify LOG_LEVEL is set to DEBUG in .env file")


if __name__ == "__main__":
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    test_heartbeat(duration)