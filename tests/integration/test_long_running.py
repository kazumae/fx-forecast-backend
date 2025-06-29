#!/usr/bin/env python3
"""
Integration test for long-running support
"""
import gc
import logging
import os
import sys
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.stream.resource_manager import ResourceManager, LongRunningOptimizations
from src.stream.data_processor import DataProcessor
from src.stream.metrics_collector import MetricsCollector


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def test_resource_manager():
    """Test resource management functionality"""
    print("\n=== Resource Manager Test ===")
    print("This test will:")
    print("1. Create a resource manager")
    print("2. Register resources")
    print("3. Test garbage collection")
    print("4. Check memory optimization")
    print("\nStarting test...\n")
    
    # Setup optimizations
    LongRunningOptimizations.setup_optimizations()
    print("✅ Long-running optimizations applied")
    
    # Create resource manager
    manager = ResourceManager()
    
    # Test 1: Register resources
    print("\nTest 1: Registering resources")
    data_processor = DataProcessor()
    metrics_collector = MetricsCollector()
    
    manager.register_resource('data_processor', data_processor)
    manager.register_resource('metrics_collector', metrics_collector)
    print("  Registered: data_processor, metrics_collector")
    
    # Check resource health
    manager.check_resource_health()
    
    # Test 2: Start GC cycle
    print("\nTest 2: Starting GC cycle (5s interval for testing)")
    manager.start_gc_cycle(interval=5)
    
    # Wait for first GC
    time.sleep(6)
    
    # Test 3: Force cleanup
    print("\nTest 3: Forcing cleanup")
    collected = manager.force_cleanup()
    print(f"  Force cleanup collected: {collected} objects")
    
    # Test 4: Get stats
    print("\nTest 4: Getting GC stats")
    stats = manager.get_stats()
    print(f"  Total collections: {stats['total_collections']}")
    print(f"  Total objects collected: {stats['total_objects_collected']}")
    print(f"  Active resources: {stats['active_resources']}")
    print(f"  GC thresholds: {stats['gc_thresholds']}")
    
    # Test 5: Unregister resource
    print("\nTest 5: Unregistering resource")
    manager.unregister_resource('data_processor')
    print("  Unregistered: data_processor")
    
    # Stop GC cycle
    manager.stop_gc_cycle()
    print("\n✅ Resource manager test completed")


def test_memory_efficiency():
    """Test memory-efficient data processing"""
    print("\n=== Memory Efficiency Test ===")
    print("This test will:")
    print("1. Create a data processor with limited buffer")
    print("2. Process many price updates")
    print("3. Verify buffer management")
    print("\nStarting test...\n")
    
    # Create data processor with small buffer
    processor = DataProcessor(max_buffer_size=100)
    
    # Test 1: Fill buffer beyond capacity
    print("Test 1: Processing 200 price updates (buffer size: 100)")
    for i in range(200):
        data = {
            'symbol': 'BTCUSD',
            'bid': 107000 + i,
            'ask': 107100 + i,
            'timestamp': time.time()
        }
        processor.process_price_data(data)
    
    # Check buffer statistics
    stats = processor.get_buffer_statistics()
    print(f"\nBuffer statistics:")
    print(f"  Current size: {stats['buffer_size']}")
    print(f"  Max size: {stats['max_buffer_size']}")
    print(f"  Oldest timestamp: {datetime.fromtimestamp(stats['oldest_timestamp']).strftime('%H:%M:%S') if stats['oldest_timestamp'] else 'N/A'}")
    print(f"  Newest timestamp: {datetime.fromtimestamp(stats['newest_timestamp']).strftime('%H:%M:%S') if stats['newest_timestamp'] else 'N/A'}")
    
    # Test 2: Clear buffer
    print("\nTest 2: Clearing buffer")
    processor.clear_buffer()
    stats_after = processor.get_buffer_statistics()
    print(f"  Buffer size after clear: {stats_after['buffer_size']}")
    
    print("\n✅ Memory efficiency test completed")


def test_gc_impact():
    """Test garbage collection impact"""
    print("\n=== Garbage Collection Impact Test ===")
    print("This test will create and destroy many objects to test GC")
    print("\nStarting test...\n")
    
    # Get initial memory info
    initial_info = LongRunningOptimizations.get_memory_info()
    print(f"Initial state:")
    print(f"  Total objects: {initial_info['total_objects']}")
    print(f"  GC enabled: {initial_info['gc_enabled']}")
    print(f"  GC counts: {initial_info['gc_counts']}")
    
    # Create many temporary objects
    print("\nCreating 10000 temporary objects...")
    temp_objects = []
    for i in range(10000):
        temp_objects.append({
            'id': i,
            'data': f'test_data_{i}' * 10,
            'timestamp': time.time()
        })
    
    # Clear references
    print("Clearing references...")
    temp_objects.clear()
    
    # Force GC
    print("Forcing garbage collection...")
    gc.collect()
    
    # Get final memory info
    final_info = LongRunningOptimizations.get_memory_info()
    print(f"\nFinal state:")
    print(f"  Total objects: {final_info['total_objects']}")
    print(f"  GC counts: {final_info['gc_counts']}")
    print(f"  Objects collected: {final_info['gc_counts'][0] - initial_info['gc_counts'][0]}")
    
    # Show top object types
    print(f"\nTop object types:")
    for obj_type, count in list(final_info['top_object_types'].items())[:5]:
        print(f"  {obj_type}: {count}")
    
    print("\n✅ GC impact test completed")


def simulate_long_running(duration=30):
    """Simulate long-running operation"""
    print(f"\n=== Long-Running Simulation ({duration}s) ===")
    print("Simulating continuous data processing with resource management\n")
    
    # Setup
    LongRunningOptimizations.setup_optimizations()
    manager = ResourceManager()
    processor = DataProcessor(max_buffer_size=500)
    collector = MetricsCollector()
    
    # Register resources
    manager.register_resource('processor', processor)
    manager.register_resource('collector', collector)
    
    # Start GC cycle
    manager.start_gc_cycle(interval=10)  # Every 10s for testing
    
    start_time = time.time()
    message_count = 0
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Simulation started")
    
    try:
        while time.time() - start_time < duration:
            # Simulate price data
            for _ in range(10):
                data = {
                    'symbol': 'BTCUSD',
                    'bid': 107000 + (message_count % 100),
                    'ask': 107100 + (message_count % 100),
                    'timestamp': time.time()
                }
                processor.process_price_data(data)
                collector.record_message_received(data['timestamp'])
                message_count += 1
            
            # Periodic status
            if message_count % 100 == 0:
                elapsed = time.time() - start_time
                buffer_stats = processor.get_buffer_statistics()
                gc_stats = manager.get_stats()
                
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Status after {elapsed:.0f}s:")
                print(f"  Messages processed: {message_count}")
                print(f"  Buffer size: {buffer_stats['buffer_size']}/{buffer_stats['max_buffer_size']}")
                print(f"  GC collections: {gc_stats['total_collections']}")
                print(f"  Objects collected: {gc_stats['total_objects_collected']}")
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nSimulation interrupted")
    
    # Cleanup
    manager.stop_gc_cycle()
    
    # Final report
    elapsed = time.time() - start_time
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Simulation completed")
    print(f"\nFinal statistics:")
    print(f"  Duration: {elapsed:.1f}s")
    print(f"  Total messages: {message_count}")
    print(f"  Messages/second: {message_count/elapsed:.1f}")
    
    # Memory info
    mem_info = LongRunningOptimizations.get_memory_info()
    print(f"  Total objects in memory: {mem_info['total_objects']}")
    
    print("\n✅ Long-running simulation completed")


if __name__ == "__main__":
    print("Long-Running Support Integration Test")
    print("=" * 50)
    
    # Run tests
    test_resource_manager()
    print("\n" + "=" * 50)
    
    test_memory_efficiency()
    print("\n" + "=" * 50)
    
    test_gc_impact()
    print("\n" + "=" * 50)
    
    # Run simulation
    simulate_long_running(duration=30)
    
    print("\nAll tests completed!")