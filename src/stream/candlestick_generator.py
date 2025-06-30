"""
ローソク足生成クラス
リアルタイムティックデータから各時間枠のローソク足を生成
"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from src.models.candlestick import CandlestickData
from src.models.forex import ForexRate

logger = logging.getLogger(__name__)


class CandlestickGenerator:
    """ローソク足生成クラス"""
    
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        self.current_candles: Dict[str, Dict[str, Optional[CandlestickData]]] = {}
        
    async def process_tick(self, tick_data: Dict) -> None:
        """ティックデータを処理してローソク足を更新"""
        async with self.session_factory() as db_session:
            try:
                symbol = tick_data['symbol']
                # Handle timestamp - it might already be in seconds or milliseconds
                ts = tick_data['timestamp']
                if isinstance(ts, (int, float)):
                    # If timestamp is greater than year 3000 in seconds, it's probably in milliseconds
                    if ts > 32503680000:  # Jan 1, 3000 in seconds
                        ts = ts / 1000
                    timestamp = datetime.fromtimestamp(ts, tz=timezone.utc)
                else:
                    # If it's already a datetime, use it directly
                    timestamp = ts if isinstance(ts, datetime) else datetime.now(timezone.utc)
                price = Decimal(str(tick_data['mid']))
                
                # 各時間枠でローソク足を更新
                for timeframe in self.timeframes:
                    await self._update_or_create_candle(db_session, symbol, timeframe, timestamp, price)
                    
            except Exception as e:
                logger.error(f"Error processing tick for candlestick: {e}")
                await db_session.rollback()
            
    async def _update_or_create_candle(self, db_session: AsyncSession, symbol: str, timeframe: str, 
                                     timestamp: datetime, price: Decimal) -> None:
        """ローソク足を更新または作成"""
        # 現在のローソク足の開始時間を計算
        open_time = self._get_candle_open_time(timestamp, timeframe)
        close_time = self._get_candle_close_time(open_time, timeframe)
        
        # キャッシュキー
        cache_key = f"{symbol}:{timeframe}:{open_time.isoformat()}"
        
        # キャッシュから現在のローソク足を取得
        if cache_key in self.current_candles.get(symbol, {}):
            candle = self.current_candles[symbol][cache_key]
            # 既存のローソク足を更新
            candle.high_price = max(candle.high_price, price)
            candle.low_price = min(candle.low_price, price)
            candle.close_price = price
            candle.tick_count += 1
        else:
            # DBから既存のローソク足を検索
            stmt = select(CandlestickData).where(
                and_(
                    CandlestickData.symbol == symbol,
                    CandlestickData.timeframe == timeframe,
                    CandlestickData.open_time == open_time
                )
            )
            result = await db_session.execute(stmt)
            candle = result.scalar_one_or_none()
            
            if candle:
                # 既存のローソク足を更新
                candle.high_price = max(candle.high_price, price)
                candle.low_price = min(candle.low_price, price)
                candle.close_price = price
                candle.tick_count += 1
            else:
                # 新しいローソク足を作成
                candle = CandlestickData(
                    symbol=symbol,
                    timeframe=timeframe,
                    open_time=open_time,
                    close_time=close_time,
                    open_price=price,
                    high_price=price,
                    low_price=price,
                    close_price=price,
                    tick_count=1
                )
                db_session.add(candle)
            
            # キャッシュに保存
            if symbol not in self.current_candles:
                self.current_candles[symbol] = {}
            self.current_candles[symbol][cache_key] = candle
            
        # 定期的にDBに保存
        if candle.tick_count % 10 == 0:  # 10ティックごとに保存
            await db_session.commit()
            
    def _get_candle_open_time(self, timestamp: datetime, timeframe: str) -> datetime:
        """ローソク足の開始時間を計算"""
        if timeframe == '1m':
            return timestamp.replace(second=0, microsecond=0)
        elif timeframe == '5m':
            minutes = (timestamp.minute // 5) * 5
            return timestamp.replace(minute=minutes, second=0, microsecond=0)
        elif timeframe == '15m':
            minutes = (timestamp.minute // 15) * 15
            return timestamp.replace(minute=minutes, second=0, microsecond=0)
        elif timeframe == '1h':
            return timestamp.replace(minute=0, second=0, microsecond=0)
        elif timeframe == '4h':
            hours = (timestamp.hour // 4) * 4
            return timestamp.replace(hour=hours, minute=0, second=0, microsecond=0)
        elif timeframe == '1d':
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            return timestamp.replace(second=0, microsecond=0)
            
    def _get_candle_close_time(self, open_time: datetime, timeframe: str) -> datetime:
        """ローソク足の終了時間を計算"""
        if timeframe == '1m':
            return open_time + timedelta(minutes=1)
        elif timeframe == '5m':
            return open_time + timedelta(minutes=5)
        elif timeframe == '15m':
            return open_time + timedelta(minutes=15)
        elif timeframe == '1h':
            return open_time + timedelta(hours=1)
        elif timeframe == '4h':
            return open_time + timedelta(hours=4)
        elif timeframe == '1d':
            return open_time + timedelta(days=1)
        else:
            return open_time + timedelta(minutes=1)
            
    async def generate_from_historical_data(self, symbol: str, start_date: datetime, 
                                          end_date: datetime) -> None:
        """履歴データからローソク足を生成"""
        async with self.session_factory() as db_session:
            try:
                logger.info(f"Generating candlesticks for {symbol} from {start_date} to {end_date}")
                
                # forex_ratesから履歴データを取得
                stmt = select(ForexRate).where(
                    and_(
                        ForexRate.currency_pair == symbol,
                        ForexRate.timestamp >= start_date,
                        ForexRate.timestamp <= end_date
                    )
                ).order_by(ForexRate.timestamp)
                
                result = await db_session.execute(stmt)
                forex_rates = result.scalars().all()
                
                logger.info(f"Found {len(forex_rates)} forex rates to process")
                
                # ティックデータとして処理
                for rate in forex_rates:
                    tick_data = {
                        'symbol': rate.currency_pair,
                        'timestamp': int(rate.timestamp.timestamp() * 1000),
                        'mid': float(rate.rate)  # ForexRateではrateがmid価格
                    }
                    await self.process_tick(tick_data)
                    
                # 最終的にコミット
                await db_session.commit()
                logger.info(f"Completed generating candlesticks for {symbol}")
            except Exception as e:
                logger.error(f"Error in generate_from_historical_data: {e}")
                await db_session.rollback()
        
    async def cleanup_cache(self, older_than_minutes: int = 60) -> None:
        """古いキャッシュをクリーンアップ"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
        
        for symbol in list(self.current_candles.keys()):
            for cache_key in list(self.current_candles[symbol].keys()):
                # cache_keyから時間を抽出
                time_str = cache_key.split(':')[2]
                candle_time = datetime.fromisoformat(time_str)
                
                if candle_time < cutoff_time:
                    del self.current_candles[symbol][cache_key]
                    
            # シンボルのキャッシュが空になったら削除
            if not self.current_candles[symbol]:
                del self.current_candles[symbol]