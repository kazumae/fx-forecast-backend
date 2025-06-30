"""
AI分析用データコレクター
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
import logging

from src.models.forex import ForexRate
from src.models.candlestick import CandlestickData
from src.models.technical_indicator import TechnicalIndicator
from src.models.entry_signal import EntrySignal

logger = logging.getLogger(__name__)


class AnalysisDataCollector:
    """AI分析用データコレクター"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        
    async def collect_all_data(self, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """全データを収集"""
        try:
            # 並列でデータ収集
            market_data_task = self.collect_market_data(symbol)
            candlestick_task = self.collect_candlestick_data(symbol)
            indicators_task = self.collect_technical_indicators(symbol)
            signals_task = self.collect_signal_history(symbol)
            
            # 全タスクを同時実行
            results = await asyncio.gather(
                market_data_task,
                candlestick_task,
                indicators_task,
                signals_task,
                return_exceptions=True
            )
            
            # エラーチェック
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Data collection error in task {i}: {result}")
                    
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "market_data": results[0] if not isinstance(results[0], Exception) else {},
                "candlesticks": results[1] if not isinstance(results[1], Exception) else {},
                "indicators": results[2] if not isinstance(results[2], Exception) else {},
                "signals": results[3] if not isinstance(results[3], Exception) else []
            }
            
        except Exception as e:
            logger.error(f"Failed to collect all data: {e}")
            raise
    
    async def collect_market_data(self, symbol: str) -> Dict[str, Any]:
        """市場データの収集"""
        try:
            now = datetime.now(timezone.utc)
            ago_24h = now - timedelta(hours=24)
            
            # 現在価格
            current_price_query = select(ForexRate).where(
                ForexRate.currency_pair == symbol
            ).order_by(ForexRate.timestamp.desc()).limit(1)
            
            current_result = await self.db.execute(current_price_query)
            current_rate = current_result.scalar_one_or_none()
            
            if not current_rate:
                return {}
            
            # 24時間の統計
            stats_query = select(
                func.max(ForexRate.bid).label('high_bid'),
                func.min(ForexRate.bid).label('low_bid'),
                func.avg(ForexRate.bid).label('avg_bid'),
                func.stddev(ForexRate.bid).label('stddev_bid'),
                func.count(ForexRate.id).label('tick_count')
            ).where(
                and_(
                    ForexRate.currency_pair == symbol,
                    ForexRate.timestamp >= ago_24h
                )
            )
            
            stats_result = await self.db.execute(stats_query)
            stats = stats_result.one()
            
            # 24時間前の価格
            ago_price_query = select(ForexRate).where(
                and_(
                    ForexRate.currency_pair == symbol,
                    ForexRate.timestamp <= ago_24h
                )
            ).order_by(ForexRate.timestamp.desc()).limit(1)
            
            ago_result = await self.db.execute(ago_price_query)
            ago_rate = ago_result.scalar_one_or_none()
            
            current_mid = (current_rate.bid + current_rate.ask) / 2
            ago_mid = (ago_rate.bid + ago_rate.ask) / 2 if ago_rate else current_mid
            change_24h = ((current_mid - ago_mid) / ago_mid) * 100 if ago_mid else 0
            
            volatility = float(stats.stddev_bid) / float(stats.avg_bid) if stats.avg_bid else 0
            
            return {
                "current_price": current_mid,
                "bid": current_rate.bid,
                "ask": current_rate.ask,
                "spread": current_rate.ask - current_rate.bid,
                "24h_high": float(stats.high_bid) if stats.high_bid else current_rate.bid,
                "24h_low": float(stats.low_bid) if stats.low_bid else current_rate.bid,
                "24h_change": change_24h,
                "24h_change_amount": current_mid - ago_mid,
                "volatility": volatility,
                "tick_count": stats.tick_count
            }
            
        except Exception as e:
            logger.error(f"Failed to collect market data: {e}")
            return {}
    
    async def collect_candlestick_data(self, symbol: str) -> Dict[str, List[Dict]]:
        """複数時間枠のローソク足データ収集"""
        try:
            timeframes = ["1m", "5m", "15m", "1h", "4h"]
            limits = {"1m": 60, "5m": 48, "15m": 32, "1h": 24, "4h": 6}
            candles = {}
            
            for tf in timeframes:
                query = select(CandlestickData).where(
                    and_(
                        CandlestickData.symbol == symbol,
                        CandlestickData.timeframe == tf
                    )
                ).order_by(CandlestickData.open_time.desc()).limit(limits[tf])
                
                result = await self.db.execute(query)
                candle_data = result.scalars().all()
                
                candles[tf] = [
                    {
                        "timestamp": c.open_time.isoformat(),
                        "open": c.open_price,
                        "high": c.high_price,
                        "low": c.low_price,
                        "close": c.close_price,
                        "volume": c.tick_count
                    }
                    for c in reversed(candle_data)  # 古い順に並べ替え
                ]
                
            return candles
            
        except Exception as e:
            logger.error(f"Failed to collect candlestick data: {e}")
            return {}
    
    async def collect_technical_indicators(self, symbol: str) -> Dict[str, Any]:
        """技術指標データの収集"""
        try:
            # 最新の指標データを取得
            query = select(TechnicalIndicator).where(
                TechnicalIndicator.symbol == symbol
            ).order_by(TechnicalIndicator.timestamp.desc()).limit(50)
            
            result = await self.db.execute(query)
            indicators = result.scalars().all()
            
            if not indicators:
                return {}
            
            # 時間枠別に整理
            indicators_by_timeframe = {}
            for ind in indicators:
                tf = ind.timeframe
                if tf not in indicators_by_timeframe:
                    indicators_by_timeframe[tf] = []
                    
                indicators_by_timeframe[tf].append({
                    "timestamp": ind.timestamp.isoformat(),
                    "ema_5": ind.ema_5,
                    "ema_10": ind.ema_10,
                    "ema_15": ind.ema_15,
                    "ema_20": ind.ema_20,
                    "ema_50": ind.ema_50,
                    "ema_100": ind.ema_100,
                    "ema_200": ind.ema_200,
                    "rsi": ind.rsi_14,
                    "macd": ind.macd,
                    "macd_signal": ind.macd_signal,
                    "macd_histogram": ind.macd_histogram,
                    "bb_upper": ind.bb_upper,
                    "bb_middle": ind.bb_middle,
                    "bb_lower": ind.bb_lower,
                    "atr": ind.atr_14,
                    "stoch_k": ind.stoch_k,
                    "stoch_d": ind.stoch_d
                })
            
            # 各時間枠で最新のものだけを返す
            latest_indicators = {}
            for tf, ind_list in indicators_by_timeframe.items():
                if ind_list:
                    latest_indicators[tf] = ind_list[0]  # 最新のもの
                    
            return latest_indicators
            
        except Exception as e:
            logger.error(f"Failed to collect technical indicators: {e}")
            return {}
    
    async def collect_signal_history(self, symbol: str, hours: int = 24) -> List[Dict]:
        """直近のエントリーシグナル履歴"""
        try:
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            query = select(EntrySignal).where(
                and_(
                    EntrySignal.symbol == symbol,
                    EntrySignal.created_at >= since
                )
            ).order_by(EntrySignal.created_at.desc())
            
            result = await self.db.execute(query)
            signals = result.scalars().all()
            
            return [
                {
                    "id": s.id,
                    "timestamp": s.created_at.isoformat(),
                    "signal_type": s.signal_type,
                    "pattern_type": s.pattern_type,
                    "timeframe": s.timeframe,
                    "entry_price": s.entry_price,
                    "stop_loss": s.stop_loss,
                    "take_profit": s.take_profit,
                    "confidence_score": s.confidence_score,
                    "status": s.status,
                    "metadata": s.signal_metadata
                }
                for s in signals
            ]
            
        except Exception as e:
            logger.error(f"Failed to collect signal history: {e}")
            return []
    
    async def calculate_volatility(self, symbol: str, hours: int = 24) -> float:
        """ボラティリティの計算"""
        try:
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            query = select(
                func.stddev((ForexRate.bid + ForexRate.ask) / 2).label('price_stddev'),
                func.avg((ForexRate.bid + ForexRate.ask) / 2).label('price_avg')
            ).where(
                and_(
                    ForexRate.currency_pair == symbol,
                    ForexRate.timestamp >= since
                )
            )
            
            result = await self.db.execute(query)
            stats = result.one()
            
            if stats.price_avg and stats.price_stddev:
                return float(stats.price_stddev) / float(stats.price_avg)
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to calculate volatility: {e}")
            return 0.0