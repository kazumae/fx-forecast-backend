"""
技術指標計算クラス
ローソク足データから各種技術指標を計算
"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import logging
import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from src.models.candlestick import CandlestickData
from src.models.technical_indicator import TechnicalIndicator

logger = logging.getLogger(__name__)


class IndicatorCalculator:
    """技術指標計算クラス"""
    
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.min_periods = {
            'ema': 200,  # 最大EMA期間
            'rsi': 14,
            'macd': 26,
            'bb': 20,
            'atr': 14,
            'stoch': 14
        }
        
    async def calculate_indicators(self, symbol: str, timeframe: str) -> None:
        """指定されたシンボルと時間枠の技術指標を計算"""
        async with self.session_factory() as db_session:
            try:
                # 必要な期間のローソク足データを取得
                candles = await self._get_candles(db_session, symbol, timeframe, limit=500)
                
                if len(candles) < self.min_periods['ema']:
                    logger.warning(f"Not enough data for {symbol} {timeframe}. Need at least {self.min_periods['ema']} candles")
                    return
                    
                # データフレームに変換
                df = self._candles_to_dataframe(candles)
                
                # 各種指標を計算
                indicators = await self._calculate_all_indicators(df)
                
                # 最新のローソク足に対する指標を保存
                latest_candle = candles[0]  # ORDER BY timestamp DESC なので最初が最新
                await self._save_indicators(db_session, symbol, timeframe, latest_candle.open_time, indicators)
                
            except Exception as e:
                logger.error(f"Error calculating indicators for {symbol} {timeframe}: {e}")
                await db_session.rollback()
            
    async def _get_candles(self, db_session: AsyncSession, symbol: str, timeframe: str, limit: int) -> List[CandlestickData]:
        """ローソク足データを取得"""
        stmt = select(CandlestickData).where(
            and_(
                CandlestickData.symbol == symbol,
                CandlestickData.timeframe == timeframe
            )
        ).order_by(desc(CandlestickData.open_time)).limit(limit)
        
        result = await db_session.execute(stmt)
        candles = result.scalars().all()
        
        # 古い順に並び替え（計算用）
        return list(reversed(candles))
        
    def _candles_to_dataframe(self, candles: List[CandlestickData]) -> pd.DataFrame:
        """ローソク足データをDataFrameに変換"""
        data = []
        for candle in candles:
            data.append({
                'timestamp': candle.open_time,
                'open': float(candle.open_price),
                'high': float(candle.high_price),
                'low': float(candle.low_price),
                'close': float(candle.close_price),
                'tick_count': candle.tick_count
            })
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df
        
    async def _calculate_all_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """すべての技術指標を計算"""
        indicators = {}
        
        # EMA (指数移動平均)
        for period in [5, 10, 15, 20, 50, 100, 200]:
            ema_values = self._calculate_ema(df['close'], period)
            indicators[f'ema_{period}'] = ema_values.iloc[-1] if not ema_values.empty else None
            
        # RSI (相対力指数)
        rsi_values = self._calculate_rsi(df['close'], 14)
        indicators['rsi_14'] = rsi_values.iloc[-1] if not rsi_values.empty else None
        
        # MACD
        macd, signal, histogram = self._calculate_macd(df['close'])
        indicators['macd'] = macd.iloc[-1] if not macd.empty else None
        indicators['macd_signal'] = signal.iloc[-1] if not signal.empty else None
        indicators['macd_histogram'] = histogram.iloc[-1] if not histogram.empty else None
        
        # ボリンジャーバンド
        bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(df['close'])
        indicators['bb_upper'] = bb_upper.iloc[-1] if not bb_upper.empty else None
        indicators['bb_middle'] = bb_middle.iloc[-1] if not bb_middle.empty else None
        indicators['bb_lower'] = bb_lower.iloc[-1] if not bb_lower.empty else None
        
        # ATR (Average True Range)
        atr_values = self._calculate_atr(df)
        indicators['atr_14'] = atr_values.iloc[-1] if not atr_values.empty else None
        
        # ストキャスティクス
        stoch_k, stoch_d = self._calculate_stochastic(df)
        indicators['stoch_k'] = stoch_k.iloc[-1] if not stoch_k.empty else None
        indicators['stoch_d'] = stoch_d.iloc[-1] if not stoch_d.empty else None
        
        return indicators
        
    def _calculate_ema(self, data: pd.Series, period: int) -> pd.Series:
        """指数移動平均を計算"""
        return data.ewm(span=period, adjust=False).mean()
        
    def _calculate_rsi(self, data: pd.Series, period: int = 14) -> pd.Series:
        """RSIを計算"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
        
    def _calculate_macd(self, data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACDを計算"""
        ema_fast = data.ewm(span=fast, adjust=False).mean()
        ema_slow = data.ewm(span=slow, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
        
    def _calculate_bollinger_bands(self, data: pd.Series, period: int = 20, std_dev: float = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """ボリンジャーバンドを計算"""
        middle = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return upper, middle, lower
        
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """ATRを計算"""
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        
        return atr
        
    def _calculate_stochastic(self, df: pd.DataFrame, period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> Tuple[pd.Series, pd.Series]:
        """ストキャスティクスを計算"""
        lowest_low = df['low'].rolling(window=period).min()
        highest_high = df['high'].rolling(window=period).max()
        
        k_percent = 100 * ((df['close'] - lowest_low) / (highest_high - lowest_low))
        k_percent = k_percent.rolling(window=smooth_k).mean()
        
        d_percent = k_percent.rolling(window=smooth_d).mean()
        
        return k_percent, d_percent
        
    async def _save_indicators(self, db_session: AsyncSession, symbol: str, timeframe: str, timestamp: datetime, indicators: Dict[str, float]) -> None:
        """技術指標をデータベースに保存"""
        # 既存のレコードを確認
        stmt = select(TechnicalIndicator).where(
            and_(
                TechnicalIndicator.symbol == symbol,
                TechnicalIndicator.timeframe == timeframe,
                TechnicalIndicator.timestamp == timestamp
            )
        )
        result = await db_session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            # 既存レコードを更新
            for key, value in indicators.items():
                if value is not None:
                    setattr(existing, key, value)
        else:
            # 新規レコードを作成
            new_indicator = TechnicalIndicator(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                **{k: v for k, v in indicators.items() if v is not None}
            )
            db_session.add(new_indicator)
            
        await db_session.commit()
        
    async def calculate_for_all_timeframes(self, symbol: str) -> None:
        """すべての時間枠で技術指標を計算"""
        timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        
        for timeframe in timeframes:
            await self.calculate_indicators(symbol, timeframe)
            logger.info(f"Calculated indicators for {symbol} {timeframe}")
            
    async def batch_calculate_historical(self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime) -> None:
        """履歴データに対してバッチで技術指標を計算"""
        async with self.session_factory() as db_session:
            try:
                logger.info(f"Batch calculating indicators for {symbol} {timeframe} from {start_date} to {end_date}")
                
                # 期間内のローソク足を取得
                stmt = select(CandlestickData).where(
                    and_(
                        CandlestickData.symbol == symbol,
                        CandlestickData.timeframe == timeframe,
                        CandlestickData.open_time >= start_date,
                        CandlestickData.open_time <= end_date
                    )
                ).order_by(CandlestickData.open_time)
                
                result = await db_session.execute(stmt)
                target_candles = result.scalars().all()
                
                logger.info(f"Found {len(target_candles)} candles to process")
                
                # 各ローソク足に対して技術指標を計算
                for i, candle in enumerate(target_candles):
                    # 計算に必要な過去のローソク足を含めて取得
                    candles = await self._get_candles_before(db_session, symbol, timeframe, candle.open_time, limit=500)
                    
                    if len(candles) >= self.min_periods['ema']:
                        df = self._candles_to_dataframe(candles)
                        indicators = await self._calculate_all_indicators(df)
                        await self._save_indicators(db_session, symbol, timeframe, candle.open_time, indicators)
                        
                        if (i + 1) % 100 == 0:
                            logger.info(f"Processed {i + 1}/{len(target_candles)} candles")
                            
                logger.info(f"Completed batch calculation for {symbol} {timeframe}")
            except Exception as e:
                logger.error(f"Error in batch_calculate_historical: {e}")
                await db_session.rollback()
        
    async def _get_candles_before(self, db_session: AsyncSession, symbol: str, timeframe: str, before_time: datetime, limit: int) -> List[CandlestickData]:
        """指定時刻以前のローソク足を取得"""
        stmt = select(CandlestickData).where(
            and_(
                CandlestickData.symbol == symbol,
                CandlestickData.timeframe == timeframe,
                CandlestickData.open_time <= before_time
            )
        ).order_by(desc(CandlestickData.open_time)).limit(limit)
        
        result = await db_session.execute(stmt)
        candles = result.scalars().all()
        
        # 古い順に並び替え（計算用）
        return list(reversed(candles))