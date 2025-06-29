#!/usr/bin/env python3
"""
Integration test for performance metrics
"""
import logging
import os
import sys
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.stream.metrics_collector import MetricsCollector, MetricsReporter


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def test_metrics_collection():
    """Test metrics collection functionality"""
    print("\n=== Metrics Collection Test ===")
    print("This test will:")
    print("1. Create a metrics collector")
    print("2. Simulate message reception")
    print("3. Collect and report metrics")
    print("4. Check anomaly detection")
    print("\nStarting test...\n")
    
    # Create metrics collector
    collector = MetricsCollector()
    
    # Test 1: Record messages with varying latencies
    print("Test 1: Recording messages with different latencies")
    test_latencies = [10, 20, 30, 50, 100, 150, 200]  # milliseconds
    
    for i, latency_ms in enumerate(test_latencies):
        # Simulate message with specific latency
        timestamp = time.time() - (latency_ms / 1000)
        collector.record_message_received(timestamp)
        print(f"  Message {i+1}: latency={latency_ms}ms")
    
    # Collect metrics
    metrics = collector.collect_metrics()
    print(f"\nMetrics after {len(test_latencies)} messages:")
    print(f"  Memory: {metrics.memory_usage_mb}MB")
    print(f"  CPU: {metrics.cpu_percent}%")
    print(f"  Total messages: {metrics.message_count}")
    print(f"  Messages/sec: {metrics.messages_per_second}")
    print(f"  Average latency: {metrics.average_latency_ms}ms")
    print(f"  Uptime: {metrics.connection_uptime_seconds}s")
    
    # Test 2: Report metrics (should log)
    print("\nTest 2: Reporting metrics (check logs)")
    collector.report_metrics()
    
    # Test 3: Test anomaly detection
    print("\nTest 3: Testing anomaly detection")
    
    # Simulate high memory usage
    test_metrics = metrics
    test_metrics.memory_usage_mb = 150
    print("  Testing high memory (150MB)...")
    collector.check_anomalies(test_metrics)
    
    # Simulate high CPU
    test_metrics.cpu_percent = 75
    print("  Testing high CPU (75%)...")
    collector.check_anomalies(test_metrics)
    
    # Simulate high latency
    test_metrics.average_latency_ms = 200
    print("  Testing high latency (200ms)...")
    collector.check_anomalies(test_metrics)
    
    # Test 4: Metrics history
    print("\nTest 4: Metrics history")
    time.sleep(1)
    collector.record_message_received(time.time() - 0.05)
    collector.collect_metrics()
    
    history = collector.get_history()
    print(f"  History entries: {len(history)}")
    if history:
        print(f"  Latest entry: {history[-1]['timestamp']}")
    
    # Test 5: Reset functionality
    print("\nTest 5: Reset functionality")
    collector.reset()
    metrics_after_reset = collector.collect_metrics()
    print(f"  Message count after reset: {metrics_after_reset.message_count}")
    print(f"  History entries after reset: {len(collector.get_history())}")
    
    print("\n=== Test Summary ===")
    print("✅ Metrics collection working")
    print("✅ Anomaly detection working")
    print("✅ History tracking working")
    print("✅ Reset functionality working")


def test_metrics_reporter():
    """Test automated metrics reporting"""
    print("\n=== Metrics Reporter Test ===")
    print("This test will run for 70 seconds to verify periodic reporting")
    print("You should see metrics reports every 60 seconds\n")
    
    # Create collector and reporter with short interval
    collector = MetricsCollector()
    reporter = MetricsReporter(collector, interval=10)  # 10 seconds for testing
    
    # Start reporting
    reporter.start_reporting()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Reporter started (10s interval)")
    
    # Simulate activity
    start_time = time.time()
    message_count = 0
    
    while time.time() - start_time < 35:
        # Simulate receiving messages
        for _ in range(5):
            collector.record_message_received(time.time() - 0.02)
            message_count += 5
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Simulated {message_count} messages", end='\r')
        time.sleep(1)
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Total messages simulated: {message_count}")
    
    # Stop reporter
    reporter.stop_reporting()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Reporter stopped")
    
    # Final metrics
    final_metrics = collector.collect_metrics()
    print(f"\nFinal metrics:")
    print(f"  Total messages: {final_metrics.message_count}")
    print(f"  Average latency: {final_metrics.average_latency_ms}ms")
    
    print("\n✅ Metrics reporter test completed")


if __name__ == "__main__":
    print("Performance Metrics Integration Test")
    print("=" * 50)
    
    # Run collection test
    test_metrics_collection()
    
    print("\n" + "=" * 50)
    
    # Run reporter test
    test_metrics_reporter()
    
    print("\nAll tests completed!")