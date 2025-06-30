"""ローソク足生成バッチジョブ

forex_ratesテーブルのデータから欠けているローソク足を生成する
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict
from sqlalchemy import desc, func, and_
from sqlalchemy.orm import Session
from decimal import Decimal

from src.batch.base import BaseBatchJob
from src.models import ForexRate, CandlestickData

logger = logging.getLogger(__name__)


class GenerateCandlesticksJob(BaseBatchJob):
    """ローソク足生成ジョブ"""
    
    def __init__(self):
        super().__init__(job_name="generate_candlesticks")
        self.timeframes = {
            '1m': timedelta(minutes=1),
            '5m': timedelta(minutes=5),
            '15m': timedelta(minutes=15),
            '1h': timedelta(hours=1),
            '4h': timedelta(hours=4),
            '1d': timedelta(days=1)
        }
        
    def execute(self, symbol: str = "XAUUSD", hours: int = 24):
        """ローソク足を生成
        
        Args:
            symbol: 対象シンボル
            hours: 過去何時間分のデータを処理するか
        """
        logger.info(f"Starting candlestick generation for {symbol} - last {hours} hours")
        
        try:
            start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            results = {
                'created_candles': {},
                'errors': [],
                'total_created': 0
            }
            
            for timeframe, interval in self.timeframes.items():
                try:
                    created = self._generate_candles_for_timeframe(
                        symbol, timeframe, interval, start_time
                    )
                    results['created_candles'][timeframe] = created
                    results['total_created'] += created
                    logger.info(f"Generated {created} candles for {timeframe}")
                except Exception as e:
                    error_msg = f"Failed to generate {timeframe} candles: {str(e)}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
            
            # 実行詳細を設定
            self.set_execution_detail("candlestick_generation_result", results)
            
            return {
                'status': 'success' if results['total_created'] > 0 else 'warning',
                'message': f"Generated {results['total_created']} candles",
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Candlestick generation failed: {str(e)}")
            raise
    
    def _generate_candles_for_timeframe(
        self, symbol: str, timeframe: str, interval: timedelta, start_time: datetime
    ) -> int:
        """特定の時間枠のローソク足を生成"""
        created_count = 0
        
        # 最新のローソク足を取得
        latest_candle = self.db.query(CandlestickData).filter(
            CandlestickData.symbol == symbol,
            CandlestickData.timeframe == timeframe
        ).order_by(desc(CandlestickData.close_time)).first()
        
        # 開始時刻を決定
        if latest_candle:
            current_time = latest_candle.close_time + interval
        else:
            current_time = self._align_to_timeframe(start_time, interval)
        
        # 現在時刻まで処理
        end_time = datetime.now(timezone.utc)
        
        while current_time < end_time:
            candle_start = current_time - interval
            candle_end = current_time
            
            # この期間のティックデータを取得
            ticks = self.db.query(ForexRate).filter(
                ForexRate.currency_pair == symbol,
                ForexRate.timestamp >= candle_start,
                ForexRate.timestamp < candle_end
            ).order_by(ForexRate.timestamp).all()
            
            if ticks:
                # ローソク足を作成
                candle = self._create_candle_from_ticks(
                    symbol, timeframe, candle_start, candle_end, ticks
                )
                
                # 既存のローソク足をチェック
                existing = self.db.query(CandlestickData).filter(
                    CandlestickData.symbol == symbol,
                    CandlestickData.timeframe == timeframe,
                    CandlestickData.close_time == candle_end
                ).first()
                
                if not existing:
                    self.db.add(candle)
                    created_count += 1
                else:
                    # 既存のローソク足を更新
                    existing.open_price = candle.open_price
                    existing.high_price = candle.high_price
                    existing.low_price = candle.low_price
                    existing.close_price = candle.close_price
                    existing.tick_count = candle.tick_count
            
            current_time += interval
        
        self.db.commit()
        return created_count
    
    def _create_candle_from_ticks(
        self, symbol: str, timeframe: str, 
        start_time: datetime, end_time: datetime,
        ticks: List[ForexRate]
    ) -> CandlestickData:
        """ティックデータからローソク足を作成"""
        open_price = Decimal(str(ticks[0].rate))
        close_price = Decimal(str(ticks[-1].rate))
        high_price = max(Decimal(str(tick.rate)) for tick in ticks)
        low_price = min(Decimal(str(tick.rate)) for tick in ticks)
        
        return CandlestickData(
            symbol=symbol,
            timeframe=timeframe,
            open_time=start_time,
            close_time=end_time,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            tick_count=len(ticks)
        )
    
    def _align_to_timeframe(self, dt: datetime, interval: timedelta) -> datetime:
        """時刻を時間枠に合わせる"""
        if interval == timedelta(minutes=1):
            return dt.replace(second=0, microsecond=0)
        elif interval == timedelta(minutes=5):
            return dt.replace(minute=dt.minute // 5 * 5, second=0, microsecond=0)
        elif interval == timedelta(minutes=15):
            return dt.replace(minute=dt.minute // 15 * 15, second=0, microsecond=0)
        elif interval == timedelta(hours=1):
            return dt.replace(minute=0, second=0, microsecond=0)
        elif interval == timedelta(hours=4):
            return dt.replace(hour=dt.hour // 4 * 4, minute=0, second=0, microsecond=0)
        elif interval == timedelta(days=1):
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return dt
    
    def get_notification_enabled(self) -> bool:
        """通知は無効"""
        return False