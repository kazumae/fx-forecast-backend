"""技術指標更新バッチジョブ

定期的に技術指標（EMA等）を計算・更新する
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict
from sqlalchemy import desc
from sqlalchemy.orm import Session
import pandas as pd
import numpy as np

from src.batch.base import BaseBatchJob
from src.models import CandlestickData, TechnicalIndicator

logger = logging.getLogger(__name__)


class UpdateIndicatorsJob(BaseBatchJob):
    """技術指標更新ジョブ"""
    
    def __init__(self):
        super().__init__(job_name="update_indicators")
        
    def execute(self, timeframe: Optional[str] = None, symbol: str = "XAUUSD"):
        """技術指標を更新
        
        Args:
            timeframe: 更新する時間枠（指定しない場合は全て）
            symbol: 対象シンボル
        """
        logger.info(f"Starting indicator update for {symbol} - timeframe: {timeframe or 'all'}")
        
        try:
            # 更新する時間枠のリスト
            if timeframe:
                timeframes = [timeframe]
            else:
                timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
            
            results = {
                'updated_timeframes': [],
                'errors': [],
                'total_updated': 0
            }
            
            for tf in timeframes:
                try:
                    updated = self._update_timeframe_indicators(symbol, tf)
                    if updated:
                        results['updated_timeframes'].append(tf)
                        results['total_updated'] += 1
                        logger.info(f"Updated indicators for {tf}")
                except Exception as e:
                    error_msg = f"Failed to update {tf}: {str(e)}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
            
            # 実行詳細を設定（Slack通知用）
            self.set_execution_detail("indicator_update_result", results)
            
            return {
                'status': 'success' if results['total_updated'] > 0 else 'warning',
                'message': f"Updated {results['total_updated']} timeframes",
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Indicator update failed: {str(e)}")
            raise
    
    def _update_timeframe_indicators(self, symbol: str, timeframe: str) -> bool:
        """特定の時間枠の指標を更新
        
        Args:
            symbol: シンボル
            timeframe: 時間枠
            
        Returns:
            更新成功した場合True
        """
        # 最新のローソク足データを取得（指標計算に必要な分）
        required_candles = 200  # EMA200を計算するのに必要
        
        candles = self.db.query(CandlestickData).filter(
            CandlestickData.symbol == symbol,
            CandlestickData.timeframe == timeframe
        ).order_by(desc(CandlestickData.close_time)).limit(required_candles).all()
        
        if not candles:
            logger.warning(f"No candlestick data found for {symbol} {timeframe}")
            return False
        
        # 最新のローソク足
        latest_candle = candles[0]
        
        # 既に計算済みかチェック
        existing = self.db.query(TechnicalIndicator).filter(
            TechnicalIndicator.symbol == symbol,
            TechnicalIndicator.timeframe == timeframe,
            TechnicalIndicator.timestamp == latest_candle.close_time
        ).first()
        
        if existing:
            logger.debug(f"Indicators already calculated for {symbol} {timeframe} at {latest_candle.close_time}")
            return False
        
        # 指標を計算
        try:
            # ローソク足データを時系列順に並べ替え
            candles_sorted = list(reversed(candles))
            
            # DataFrame作成
            df = self._candles_to_dataframe(candles_sorted)
            
            # 各種指標を計算
            indicators = self._calculate_all_indicators(df)
            
            # 最新の指標を保存
            indicator_obj = TechnicalIndicator(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=latest_candle.close_time,
                **{k: v for k, v in indicators.items() if v is not None}
            )
            
            self.db.add(indicator_obj)
            self.db.commit()
            
            logger.info(f"Saved indicators for {symbol} {timeframe} at {latest_candle.close_time}")
            return True
                
        except Exception as e:
            logger.error(f"Error calculating indicators: {str(e)}")
            self.db.rollback()
            raise
    
    def get_notification_enabled(self) -> bool:
        """通知は無効"""
        return False
    
    def _candles_to_dataframe(self, candles: List[CandlestickData]) -> pd.DataFrame:
        """ローソク足データをDataFrameに変換"""
        data = []
        for candle in candles:
            data.append({
                'timestamp': candle.close_time,
                'open': float(candle.open_price),
                'high': float(candle.high_price),
                'low': float(candle.low_price),
                'close': float(candle.close_price),
                'volume': float(candle.tick_count) if hasattr(candle, 'tick_count') and candle.tick_count else 0
            })
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df
    
    def _calculate_all_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """すべての技術指標を計算"""
        indicators = {}
        
        # EMA (指数移動平均) - ユーザーがEMAを重視しているため、モデルに定義されている期間を計算
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
    
    def _calculate_macd(self, data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        """MACDを計算"""
        ema_fast = data.ewm(span=fast, adjust=False).mean()
        ema_slow = data.ewm(span=slow, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def _calculate_bollinger_bands(self, data: pd.Series, period: int = 20, std_dev: float = 2) -> tuple:
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
    
    def _calculate_stochastic(self, df: pd.DataFrame, period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> tuple:
        """ストキャスティクスを計算"""
        lowest_low = df['low'].rolling(window=period).min()
        highest_high = df['high'].rolling(window=period).max()
        
        k_percent = 100 * ((df['close'] - lowest_low) / (highest_high - lowest_low))
        k_percent = k_percent.rolling(window=smooth_k).mean()
        
        d_percent = k_percent.rolling(window=smooth_d).mean()
        
        return k_percent, d_percent