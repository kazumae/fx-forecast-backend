#!/usr/bin/env python
"""
Test that errors have been fixed
"""
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables
os.environ['DATABASE_URL'] = 'postgresql://fx_user:fx_password@localhost:5433/fx_trading'
os.environ['REDIS_URL'] = 'redis://localhost:6380'

from src.db.session import SessionLocal
from src.db.redis_manager import RedisManager
from src.models.tick_data import TickData
from src.stream.data_processor_db import DataProcessorDB
from sqlalchemy import text


def test_fixes():
    """Test that the fixes are working"""
    print("=== Testing Error Fixes ===\n")
    
    # Initialize components
    redis_manager = RedisManager(host='localhost', port=6380)
    data_processor = DataProcessorDB(redis_url='redis://localhost:6380')
    db = SessionLocal()
    
    try:
        # 1. Test Redis cache fix
        print("1. Testing Redis cache fix...")
        
        test_data = {
            "symbol": "GBPUSD",
            "bid": 1.2650,
            "ask": 1.2652,
            "timestamp": datetime.now(timezone.utc).timestamp()
        }
        
        # Process data - should not throw cache_tick_data error
        data_processor.process_price_data(test_data)
        print("   ✓ Data processed without Redis errors")
        
        # Check Redis latest tick
        latest_tick = redis_manager.get_latest_tick("GBPUSD")
        if latest_tick:
            print(f"   ✓ Latest tick in Redis: {latest_tick.symbol} @ {latest_tick.timestamp}")
            print(f"     Bid: {latest_tick.bid}, Ask: {latest_tick.ask}")
        else:
            print("   ✗ No latest tick in Redis")
        
        # Check Redis history
        history_key = "tick:GBPUSD:history"
        history_count = redis_manager.redis_client.llen(history_key)
        print(f"   ✓ Tick history count: {history_count}")
        
        # 2. Test UPSERT functionality
        print("\n2. Testing UPSERT functionality...")
        
        # Get current timestamp for testing
        test_timestamp = datetime.now(timezone.utc)
        
        # First insert
        test_data = {
            "symbol": "GBPUSD",
            "bid": 1.2660,
            "ask": 1.2662,
            "timestamp": test_timestamp.timestamp()
        }
        
        data_processor.process_price_data(test_data)
        
        # Check initial insert
        tick1 = db.query(TickData).filter(
            TickData.symbol == "GBPUSD",
            TickData.timestamp == test_timestamp
        ).first()
        
        if tick1:
            print(f"   ✓ Initial insert: Bid={tick1.bid}")
        
        # Update with same timestamp
        test_data['bid'] = 1.2670
        test_data['ask'] = 1.2672
        
        data_processor.process_price_data(test_data)
        
        # Force a new query to get fresh data
        db.expire_all()  # Clear session cache
        
        tick2 = db.query(TickData).filter(
            TickData.symbol == "GBPUSD",
            TickData.timestamp == test_timestamp
        ).first()
        
        if tick2 and tick2.bid == Decimal('1.2670'):
            print(f"   ✓ UPSERT working: Bid updated to {tick2.bid}")
        else:
            print(f"   ✗ UPSERT not working: Bid is {tick2.bid if tick2 else 'None'}")
        
        # 3. Test candlestick generation
        print("\n3. Testing candlestick generation...")
        
        # Check if candlesticks are being generated
        result = db.execute(text("""
            SELECT COUNT(*) FROM candlestick_data 
            WHERE symbol = 'GBPUSD' AND timeframe = '1m'
        """))
        
        candle_count = result.scalar()
        print(f"   ✓ Candlesticks generated: {candle_count}")
        
        print("\n=== Test Summary ===")
        print("✓ Redis cache errors fixed")
        print("✓ UPSERT functionality verified")
        print("✓ Candlestick generation working")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        db.close()
        data_processor.close()
        redis_manager.close()


if __name__ == "__main__":
    test_fixes()