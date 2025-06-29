#!/usr/bin/env python
"""
Test upper timeframe aggregation
"""
import sys
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.db.session import SessionLocal
from src.db.redis_manager import RedisManager
from src.models.candlestick import CandlestickData
from src.repositories.candlestick_repository import CandlestickRepository
from src.stream.candlestick_generator import CandlestickGenerator


def test_aggregation():
    """Test candlestick aggregation logic"""
    print("Testing upper timeframe aggregation...")
    
    # Create session
    db = SessionLocal()
    redis_manager = RedisManager()
    candle_repo = CandlestickRepository(db)
    
    # Create generator for 1m timeframe
    generator = CandlestickGenerator(
        symbol='XAUUSD',
        timeframe='1m',
        db_session=db,
        redis_manager=redis_manager,
        candle_repo=candle_repo
    )
    
    # Test boundary detection
    print("\n1. Testing boundary detection:")
    
    # 15m boundary test
    test_time = datetime(2025, 6, 29, 16, 14, 59, tzinfo=timezone.utc)  # 16:14:59
    is_15m_boundary = generator._is_timeframe_boundary(test_time, '15m')
    print(f"   16:14:59 is 15m boundary: {is_15m_boundary} (should be True)")
    
    # 1h boundary test
    test_time = datetime(2025, 6, 29, 16, 59, 59, tzinfo=timezone.utc)  # 16:59:59
    is_1h_boundary = generator._is_timeframe_boundary(test_time, '1h')
    print(f"   16:59:59 is 1h boundary: {is_1h_boundary} (should be True)")
    
    # 4h boundary test
    test_time = datetime(2025, 6, 29, 19, 59, 59, tzinfo=timezone.utc)  # 19:59:59
    is_4h_boundary = generator._is_timeframe_boundary(test_time, '4h')
    print(f"   19:59:59 is 4h boundary: {is_4h_boundary} (should be True)")
    
    # Non-boundary test
    test_time = datetime(2025, 6, 29, 16, 13, 59, tzinfo=timezone.utc)  # 16:13:59
    is_15m_boundary = generator._is_timeframe_boundary(test_time, '15m')
    print(f"   16:13:59 is 15m boundary: {is_15m_boundary} (should be False)")
    
    print("\n2. Testing existing 1m candles:")
    
    # Get recent 1m candles
    recent_candles = candle_repo.get_recent('XAUUSD', '1m', 100)
    print(f"   Found {len(recent_candles)} 1m candles")
    
    if recent_candles:
        latest = recent_candles[0]
        print(f"   Latest 1m candle: {latest.open_time} - {latest.close_time}")
        
        # Check if we can aggregate
        print("\n3. Checking aggregation opportunities:")
        
        # Check 15m
        if generator._is_timeframe_boundary(latest.close_time, '15m'):
            print("   Can aggregate to 15m!")
            
            # Check existing 15m candles
            recent_15m = candle_repo.get_recent('XAUUSD', '15m', 10)
            print(f"   Found {len(recent_15m)} existing 15m candles")
            
            if recent_15m:
                print(f"   Latest 15m: {recent_15m[0].open_time}")
        
        # Check 1h
        if generator._is_timeframe_boundary(latest.close_time, '1h'):
            print("   Can aggregate to 1h!")
            
            # Check existing 1h candles
            recent_1h = candle_repo.get_recent('XAUUSD', '1h', 10)
            print(f"   Found {len(recent_1h)} existing 1h candles")
            
            if recent_1h:
                print(f"   Latest 1h: {recent_1h[0].open_time}")
        
        # Check 4h
        if generator._is_timeframe_boundary(latest.close_time, '4h'):
            print("   Can aggregate to 4h!")
            
            # Check existing 4h candles
            recent_4h = candle_repo.get_recent('XAUUSD', '4h', 10)
            print(f"   Found {len(recent_4h)} existing 4h candles")
            
            if recent_4h:
                print(f"   Latest 4h: {recent_4h[0].open_time}")
    
    print("\n4. Manual aggregation test:")
    
    # Try to manually aggregate recent 15 minutes
    now = datetime.now(timezone.utc)
    # Round down to last 15m boundary
    last_15m = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
    prev_15m = last_15m - timedelta(minutes=15)
    
    print(f"   Looking for 1m candles from {prev_15m} to {last_15m}")
    
    candles_1m = candle_repo.get_candlesticks(
        'XAUUSD', '1m',
        prev_15m,
        last_15m - timedelta(seconds=1)
    )
    
    print(f"   Found {len(candles_1m)} 1m candles for this period")
    
    if candles_1m:
        print(f"   First: {candles_1m[0].open_time}, Last: {candles_1m[-1].close_time}")
        print(f"   Would aggregate: O={candles_1m[0].open_price}, "
              f"H={max(c.high_price for c in candles_1m)}, "
              f"L={min(c.low_price for c in candles_1m)}, "
              f"C={candles_1m[-1].close_price}")
    
    # Cleanup
    db.close()
    redis_manager.close()
    
    print("\nTest completed!")


if __name__ == "__main__":
    test_aggregation()