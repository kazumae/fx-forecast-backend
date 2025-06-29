#!/usr/bin/env python3
"""
Manual test to monitor heartbeat in running service
"""
import subprocess
import time
import re
from datetime import datetime


def monitor_heartbeat(duration=60):
    """Monitor heartbeat messages in service logs"""
    print(f"\n=== Monitoring Heartbeat for {duration} seconds ===")
    print("Looking for ping/pong messages in service logs...\n")
    
    start_time = time.time()
    ping_count = 0
    pong_count = 0
    last_ping_time = None
    last_pong_time = None
    
    try:
        # Start monitoring logs
        process = subprocess.Popen(
            ['docker-compose', 'logs', '-f', '--tail=0', 'tradermade-stream'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        while time.time() - start_time < duration:
            line = process.stdout.readline()
            if not line:
                continue
            
            # Look for ping/pong messages
            if "Ping sent" in line:
                ping_count += 1
                last_ping_time = datetime.now()
                print(f"[{last_ping_time.strftime('%H:%M:%S')}] 📤 Ping sent (#{ping_count})")
            
            elif "Pong received" in line:
                pong_count += 1
                last_pong_time = datetime.now()
                print(f"[{last_pong_time.strftime('%H:%M:%S')}] 📥 Pong received (#{pong_count})")
                
                # Calculate round-trip time if we have both times
                if last_ping_time and last_pong_time:
                    rtt = (last_pong_time - last_ping_time).total_seconds()
                    print(f"                  └─ Round-trip time: {rtt:.3f}s")
            
            elif "Heartbeat timeout" in line:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Heartbeat timeout detected!")
            
            elif "Heartbeat started" in line:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Heartbeat started")
            
            elif "initiating reconnection" in line and "Heartbeat" in line:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 Heartbeat triggered reconnection")
        
        process.terminate()
        process.wait()
        
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Monitoring interrupted by user")
        if 'process' in locals():
            process.terminate()
    
    # Print summary
    elapsed = time.time() - start_time
    print(f"\n=== Summary after {elapsed:.1f} seconds ===")
    print(f"Total pings sent: {ping_count}")
    print(f"Total pongs received: {pong_count}")
    
    if ping_count > 0:
        success_rate = (pong_count / ping_count) * 100
        print(f"Success rate: {success_rate:.1f}%")
        
        expected_pings = int(elapsed / 30)  # Default 30s interval
        print(f"Expected pings (30s interval): ~{expected_pings}")
        
        if ping_count >= expected_pings - 1:
            print("✅ Heartbeat frequency is correct")
        else:
            print("⚠️  Heartbeat frequency seems low")
    else:
        print("❌ No heartbeat activity detected")
    
    return ping_count, pong_count


if __name__ == "__main__":
    import sys
    
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    monitor_heartbeat(duration)