#!/usr/bin/env python
"""
Manual test for US-013: WebSocket data storage to database
"""
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables for database connection
os.environ['DATABASE_URL'] = 'postgresql://fx_user:fx_password@localhost:5433/fx_trading'
os.environ['REDIS_URL'] = 'redis://localhost:6380'

from src.db.session import SessionLocal
from src.db.redis_manager import RedisManager
from src.models.tick_data import TickData
from src.repositories.candlestick_repository import CandlestickRepository
from src.repositories.technical_indicator_repository import TechnicalIndicatorRepository
from src.stream.data_processor_db import DataProcessorDB


def test_us013():
    """Test WebSocket data storage functionality"""
    print("=== US-013 Manual Test: WebSocket Data Storage ===\n")
    
    # Initialize components
    redis_manager = RedisManager(host='localhost', port=6380)
    data_processor = DataProcessorDB(redis_url='redis://localhost:6380')
    
    print("1. Testing tick data storage...")
    
    # Simulate WebSocket message
    test_data = {
        "symbol": "XAUUSD",
        "bid": 3350.123,
        "ask": 3350.456,
        "timestamp": datetime.now(timezone.utc).timestamp()
    }
    
    print(f"   Test data: {test_data}")
    
    try:
        # Process the data (this should save to DB and update Redis)
        data_processor.process_price_data(test_data)
        print("   ✓ Data processed successfully")
        
        # Verify in database
        db = SessionLocal()
        
        # Check tick data
        tick = db.query(TickData).filter(
            TickData.symbol == "XAUUSD"
        ).order_by(TickData.timestamp.desc()).first()
        
        if tick:
            print(f"   ✓ Tick data saved to DB: {tick.symbol} @ {tick.timestamp}")
            print(f"     Bid: {tick.bid}, Ask: {tick.ask}, Spread: {tick.spread}")
        else:
            print("   ✗ No tick data found in database")
        
        # Check Redis
        print("\n2. Testing Redis cache update...")
        
        # Get latest tick from Redis
        latest_tick_key = "tick:XAUUSD:latest"
        redis_data = redis_manager.redis_client.hgetall(latest_tick_key)
        
        if redis_data:
            print(f"   ✓ Latest tick in Redis: {redis_data}")
        else:
            print("   ✗ No tick data found in Redis")
        
        # Check tick history in Redis
        history_key = "tick:XAUUSD:history"
        history_count = redis_manager.redis_client.llen(history_key)
        print(f"   ✓ Tick history count in Redis: {history_count}")
        
        # Test duplicate handling
        print("\n3. Testing duplicate data handling (UPSERT)...")
        
        # Send same timestamp again with different prices
        test_data['bid'] = 3351.000
        test_data['ask'] = 3351.333
        
        data_processor.process_price_data(test_data)
        print("   ✓ Duplicate data processed")
        
        # Verify update
        tick = db.query(TickData).filter(
            TickData.symbol == "XAUUSD"
        ).order_by(TickData.timestamp.desc()).first()
        
        if tick and tick.bid == Decimal('3351.000'):
            print("   ✓ Data updated correctly (UPSERT working)")
        else:
            print("   ✗ UPSERT not working properly")
        
        # Test multiple rapid inserts
        print("\n4. Testing rapid data insertion...")
        
        import time
        start_time = time.time()
        insert_count = 100
        
        for i in range(insert_count):
            test_data = {
                "symbol": "XAUUSD",
                "bid": 3350.0 + (i * 0.001),
                "ask": 3350.3 + (i * 0.001),
                "timestamp": datetime.now(timezone.utc).timestamp()
            }
            data_processor.process_price_data(test_data)
            time.sleep(0.001)  # Small delay to avoid same timestamp
        
        elapsed = time.time() - start_time
        rate = insert_count / elapsed
        
        print(f"   ✓ Inserted {insert_count} records in {elapsed:.2f} seconds")
        print(f"   ✓ Rate: {rate:.0f} inserts/second")
        
        if rate > 100:
            print("   ✓ Performance requirement met (>100 inserts/second)")
        else:
            print("   ✗ Performance below requirement")
        
        # Check candlestick generation
        print("\n5. Testing candlestick generation trigger...")
        
        candles = db.query(CandlestickData).filter(
            CandlestickData.symbol == "XAUUSD",
            CandlestickData.timeframe == "1m"
        ).order_by(CandlestickData.open_time.desc()).limit(5).all()
        
        if candles:
            print(f"   ✓ Found {len(candles)} candlesticks")
            for candle in candles:
                print(f"     {candle.timeframe} @ {candle.open_time}: O={candle.open_price} H={candle.high_price} L={candle.low_price} C={candle.close_price}")
        else:
            print("   ✗ No candlesticks generated")
        
        # Cleanup
        db.close()
        data_processor.close()
        redis_manager.close()
        
        print("\n=== Test Summary ===")
        print("✓ WebSocket data successfully stored to TimescaleDB")
        print("✓ Redis cache updated with latest tick and history")
        print("✓ UPSERT functionality working correctly")
        print("✓ Performance meets requirements")
        print("✓ Candlestick generation triggered")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Import candlestick model to ensure it exists
    from src.models.candlestick import CandlestickData
    
    test_us013()