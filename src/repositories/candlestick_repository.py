"""
ローソク足データリポジトリ
時系列データの効率的な検索・集約機能を提供
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func, text

from src.models.candlestick import CandlestickData
from .base import BaseRepository


class CandlestickRepository(BaseRepository[CandlestickData]):
    """ローソク足データ専用リポジトリ"""
    
    def __init__(self, session: Session):
        super().__init__(CandlestickData, session)
    
    def get_latest(self, symbol: str, timeframe: str) -> Optional[CandlestickData]:
        """最新のローソク足データを取得"""
        return self.session.query(CandlestickData).filter(
            CandlestickData.symbol == symbol,
            CandlestickData.timeframe == timeframe
        ).order_by(desc(CandlestickData.open_time)).first()
    
    def get_by_time_range(self, symbol: str, timeframe: str, 
                         start_time: datetime, end_time: datetime,
                         limit: int = 1000) -> List[CandlestickData]:
        """時間範囲でローソク足データを取得"""
        return self.session.query(CandlestickData).filter(
            and_(
                CandlestickData.symbol == symbol,
                CandlestickData.timeframe == timeframe,
                CandlestickData.open_time >= start_time,
                CandlestickData.open_time <= end_time
            )
        ).order_by(CandlestickData.open_time).limit(limit).all()
    
    def get_candlesticks(self, symbol: str, timeframe: str,
                        start_time: datetime, end_time: datetime) -> List[CandlestickData]:
        """時間範囲でローソク足データを取得（エイリアス）"""
        return self.get_by_time_range(symbol, timeframe, start_time, end_time)
    
    def get_recent(self, symbol: str, timeframe: str, count: int = 100) -> List[CandlestickData]:
        """直近のローソク足データを取得"""
        return self.session.query(CandlestickData).filter(
            CandlestickData.symbol == symbol,
            CandlestickData.timeframe == timeframe
        ).order_by(desc(CandlestickData.open_time)).limit(count).all()
    
    def get_for_ai_analysis(self, symbol: str, timeframe: str, 
                           hours_back: int = 24) -> List[CandlestickData]:
        """AI解析用の最適化されたデータ取得"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        return self.session.query(CandlestickData).filter(
            and_(
                CandlestickData.symbol == symbol,
                CandlestickData.timeframe == timeframe,
                CandlestickData.open_time >= cutoff_time
            )
        ).order_by(CandlestickData.open_time).all()
    
    def get_ohlc_data(self, symbol: str, timeframe: str, 
                      start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """OHLC形式でデータを取得"""
        candles = self.get_by_time_range(symbol, timeframe, start_time, end_time)
        
        return [
            {
                'timestamp': candle.open_time.isoformat(),
                'open': float(candle.open_price),
                'high': float(candle.high_price),
                'low': float(candle.low_price),
                'close': float(candle.close_price),
                'volume': candle.tick_count
            }
            for candle in candles
        ]
    
    def aggregate_from_lower_timeframe(self, symbol: str, from_timeframe: str, 
                                     to_timeframe: str, start_time: datetime,
                                     end_time: datetime) -> List[CandlestickData]:
        """
        下位時間枠から上位時間枠のローソク足を生成
        例: 1分足から15分足、1時間足、4時間足を生成
        """
        # 時間枠の間隔をマッピング
        interval_mapping = {
            '15m': 15,  # 15分
            '1h': 60,   # 60分
            '4h': 240,  # 240分
            '1d': 1440  # 1日 = 1440分
        }
        
        if to_timeframe not in interval_mapping:
            raise ValueError(f"サポートされていない時間枠: {to_timeframe}")
        
        interval_minutes = interval_mapping[to_timeframe]
        
        # PostgreSQLのtime_bucketを使用してローソク足を集約
        query = text("""
            SELECT 
                symbol,
                :to_timeframe as timeframe,
                time_bucket(INTERVAL ':interval minutes', open_time) as open_time,
                time_bucket(INTERVAL ':interval minutes', open_time) + INTERVAL ':interval minutes' as close_time,
                (array_agg(open_price ORDER BY open_time))[1] as open_price,
                MAX(high_price) as high_price,
                MIN(low_price) as low_price,
                (array_agg(close_price ORDER BY open_time DESC))[1] as close_price,
                SUM(tick_count) as tick_count,
                NOW() as created_at,
                NOW() as updated_at
            FROM candlestick_data
            WHERE symbol = :symbol 
            AND timeframe = :from_timeframe
            AND open_time >= :start_time 
            AND open_time <= :end_time
            GROUP BY symbol, time_bucket(INTERVAL ':interval minutes', open_time)
            ORDER BY open_time
        """)
        
        result = self.session.execute(query, {
            'symbol': symbol,
            'from_timeframe': from_timeframe,
            'to_timeframe': to_timeframe,
            'start_time': start_time,
            'end_time': end_time,
            'interval': interval_minutes
        })
        
        aggregated_candles = []
        for row in result:
            candle = CandlestickData(
                symbol=row.symbol,
                timeframe=row.timeframe,
                open_time=row.open_time,
                close_time=row.close_time,
                open_price=row.open_price,
                high_price=row.high_price,
                low_price=row.low_price,
                close_price=row.close_price,
                tick_count=row.tick_count,
                created_at=row.created_at,
                updated_at=row.updated_at
            )
            aggregated_candles.append(candle)
        
        return aggregated_candles
    
    def get_price_statistics(self, symbol: str, timeframe: str, 
                           days_back: int = 30) -> Dict[str, float]:
        """価格統計情報を取得"""
        cutoff_time = datetime.utcnow() - timedelta(days=days_back)
        
        result = self.session.query(
            func.avg(CandlestickData.close_price).label('avg_price'),
            func.max(CandlestickData.high_price).label('max_price'),
            func.min(CandlestickData.low_price).label('min_price'),
            func.stddev(CandlestickData.close_price).label('std_price'),
            func.count().label('count')
        ).filter(
            and_(
                CandlestickData.symbol == symbol,
                CandlestickData.timeframe == timeframe,
                CandlestickData.open_time >= cutoff_time
            )
        ).first()
        
        return {
            'avg_price': float(result.avg_price) if result.avg_price else 0.0,
            'max_price': float(result.max_price) if result.max_price else 0.0,
            'min_price': float(result.min_price) if result.min_price else 0.0,
            'std_price': float(result.std_price) if result.std_price else 0.0,
            'count': result.count
        }
    
    def delete_old_data(self, symbol: str, timeframe: str, days_to_keep: int = 30) -> int:
        """古いデータを削除"""
        cutoff_time = datetime.utcnow() - timedelta(days=days_to_keep)
        
        deleted_count = self.session.query(CandlestickData).filter(
            and_(
                CandlestickData.symbol == symbol,
                CandlestickData.timeframe == timeframe,
                CandlestickData.open_time < cutoff_time
            )
        ).delete()
        
        self.session.commit()
        return deleted_count
    
    def upsert_candle(self, symbol: str, timeframe: str, open_time: datetime,
                     open_price: float, high_price: float, low_price: float,
                     close_price: float, tick_count: int = 0) -> CandlestickData:
        """
        ローソク足データのアップサート（存在すれば更新、なければ作成）
        """
        # 既存データを検索
        existing = self.session.query(CandlestickData).filter(
            and_(
                CandlestickData.symbol == symbol,
                CandlestickData.timeframe == timeframe,
                CandlestickData.open_time == open_time
            )
        ).first()
        
        if existing:
            # 更新
            existing.close_price = close_price
            existing.high_price = max(float(existing.high_price), high_price)
            existing.low_price = min(float(existing.low_price), low_price)
            existing.tick_count += tick_count
            existing.updated_at = func.now()
            
            self.session.commit()
            self.session.refresh(existing)
            return existing
        else:
            # 新規作成
            close_time = open_time + self._get_timeframe_delta(timeframe)
            
            candle = CandlestickData(
                symbol=symbol,
                timeframe=timeframe,
                open_time=open_time,
                close_time=close_time,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                tick_count=tick_count
            )
            
            self.session.add(candle)
            self.session.commit()
            self.session.refresh(candle)
            return candle
    
    def _get_timeframe_delta(self, timeframe: str) -> timedelta:
        """時間枠に対応するtimedeltaを取得"""
        timeframe_deltas = {
            '1m': timedelta(minutes=1),
            '15m': timedelta(minutes=15),
            '1h': timedelta(hours=1),
            '4h': timedelta(hours=4),
            '1d': timedelta(days=1)
        }
        
        return timeframe_deltas.get(timeframe, timedelta(minutes=1))