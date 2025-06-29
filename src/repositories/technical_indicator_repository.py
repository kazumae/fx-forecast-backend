"""
技術指標リポジトリ
移動平均線等の技術指標データの管理
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func

from src.models.technical_indicator import TechnicalIndicator
from .base import BaseRepository


class TechnicalIndicatorRepository(BaseRepository[TechnicalIndicator]):
    """技術指標専用リポジトリ"""
    
    def __init__(self, session: Session):
        super().__init__(TechnicalIndicator, session)
    
    def get_latest(self, symbol: str, timeframe: str, 
                   indicator_type: str) -> Optional[TechnicalIndicator]:
        """最新の技術指標値を取得"""
        return self.session.query(TechnicalIndicator).filter(
            and_(
                TechnicalIndicator.symbol == symbol,
                TechnicalIndicator.timeframe == timeframe,
                TechnicalIndicator.indicator_type == indicator_type
            )
        ).order_by(desc(TechnicalIndicator.timestamp)).first()
    
    def get_by_time_range(self, symbol: str, timeframe: str, indicator_type: str,
                         start_time: datetime, end_time: datetime) -> List[TechnicalIndicator]:
        """時間範囲で技術指標を取得"""
        return self.session.query(TechnicalIndicator).filter(
            and_(
                TechnicalIndicator.symbol == symbol,
                TechnicalIndicator.timeframe == timeframe,
                TechnicalIndicator.indicator_type == indicator_type,
                TechnicalIndicator.timestamp >= start_time,
                TechnicalIndicator.timestamp <= end_time
            )
        ).order_by(TechnicalIndicator.timestamp).all()
    
    def get_recent_series(self, symbol: str, timeframe: str, indicator_type: str,
                         count: int = 50) -> List[TechnicalIndicator]:
        """直近の技術指標時系列データを取得"""
        return self.session.query(TechnicalIndicator).filter(
            and_(
                TechnicalIndicator.symbol == symbol,
                TechnicalIndicator.timeframe == timeframe,
                TechnicalIndicator.indicator_type == indicator_type
            )
        ).order_by(desc(TechnicalIndicator.timestamp)).limit(count).all()
    
    def get_all_indicators_at_time(self, symbol: str, timeframe: str,
                                  timestamp: datetime) -> Dict[str, float]:
        """指定時刻での全技術指標値を取得"""
        indicators = self.session.query(TechnicalIndicator).filter(
            and_(
                TechnicalIndicator.symbol == symbol,
                TechnicalIndicator.timeframe == timeframe,
                TechnicalIndicator.timestamp == timestamp
            )
        ).all()
        
        return {
            indicator.indicator_type: float(indicator.value)
            for indicator in indicators
        }
    
    def get_latest_indicators(self, symbol: str, timeframe: str,
                            indicator_types: List[str]) -> Dict[str, Optional[float]]:
        """複数の技術指標の最新値を一括取得"""
        result = {}
        
        for indicator_type in indicator_types:
            latest = self.get_latest(symbol, timeframe, indicator_type)
            result[indicator_type] = float(latest.value) if latest else None
        
        return result
    
    def get_sma_values(self, symbol: str, timeframe: str, periods: List[int],
                      count: int = 20) -> Dict[str, List[float]]:
        """複数期間のSMA値を取得"""
        result = {}
        
        for period in periods:
            indicator_type = f'sma_{period}'
            indicators = self.get_recent_series(symbol, timeframe, indicator_type, count)
            
            # 時系列順に並び替え
            indicators.sort(key=lambda x: x.timestamp)
            result[indicator_type] = [float(ind.value) for ind in indicators]
        
        return result
    
    def get_ema_values(self, symbol: str, timeframe: str, periods: List[int],
                      count: int = 20) -> Dict[str, List[float]]:
        """複数期間のEMA値を取得"""
        result = {}
        
        for period in periods:
            indicator_type = f'ema_{period}'
            indicators = self.get_recent_series(symbol, timeframe, indicator_type, count)
            
            # 時系列順に並び替え
            indicators.sort(key=lambda x: x.timestamp)
            result[indicator_type] = [float(ind.value) for ind in indicators]
        
        return result
    
    def get_indicators_for_ai(self, symbol: str, timeframe: str,
                             hours_back: int = 24) -> Dict[str, List[Dict[str, Any]]]:
        """AI解析用の技術指標データを取得"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        # 主要な技術指標タイプ
        indicator_types = ['sma_20', 'sma_50', 'ema_12', 'ema_26']
        
        result = {}
        
        for indicator_type in indicator_types:
            indicators = self.session.query(TechnicalIndicator).filter(
                and_(
                    TechnicalIndicator.symbol == symbol,
                    TechnicalIndicator.timeframe == timeframe,
                    TechnicalIndicator.indicator_type == indicator_type,
                    TechnicalIndicator.timestamp >= cutoff_time
                )
            ).order_by(TechnicalIndicator.timestamp).all()
            
            result[indicator_type] = [
                {
                    'timestamp': ind.timestamp.isoformat(),
                    'value': float(ind.value),
                    'metadata': ind.extra_metadata
                }
                for ind in indicators
            ]
        
        return result
    
    def calculate_trend_analysis(self, symbol: str, timeframe: str,
                               periods: List[int] = [20, 50]) -> Dict[str, Any]:
        """トレンド分析を実行"""
        trends = {}
        
        for period in periods:
            sma_type = f'sma_{period}'
            recent_smas = self.get_recent_series(symbol, timeframe, sma_type, 5)
            
            if len(recent_smas) >= 2:
                # 時系列順に並び替え
                recent_smas.sort(key=lambda x: x.timestamp)
                
                latest_value = float(recent_smas[-1].value)
                previous_value = float(recent_smas[-2].value)
                
                # トレンド判定
                if latest_value > previous_value:
                    trend = 'up'
                elif latest_value < previous_value:
                    trend = 'down'
                else:
                    trend = 'flat'
                
                # 変化率計算
                change_rate = ((latest_value - previous_value) / previous_value) * 100
                
                trends[sma_type] = {
                    'trend': trend,
                    'latest_value': latest_value,
                    'previous_value': previous_value,
                    'change_rate': change_rate,
                    'timestamp': recent_smas[-1].timestamp.isoformat()
                }
        
        return trends
    
    def get_cross_signals(self, symbol: str, timeframe: str,
                         fast_period: int = 12, slow_period: int = 26,
                         count: int = 10) -> List[Dict[str, Any]]:
        """移動平均線のクロスシグナルを検出"""
        fast_type = f'ema_{fast_period}'
        slow_type = f'ema_{slow_period}'
        
        fast_indicators = self.get_recent_series(symbol, timeframe, fast_type, count)
        slow_indicators = self.get_recent_series(symbol, timeframe, slow_type, count)
        
        if not fast_indicators or not slow_indicators:
            return []
        
        # 時系列順に並び替え
        fast_indicators.sort(key=lambda x: x.timestamp)
        slow_indicators.sort(key=lambda x: x.timestamp)
        
        signals = []
        
        # 同じタイムスタンプのデータを対応付け
        for i in range(1, min(len(fast_indicators), len(slow_indicators))):
            current_fast = float(fast_indicators[i].value)
            current_slow = float(slow_indicators[i].value)
            prev_fast = float(fast_indicators[i-1].value)
            prev_slow = float(slow_indicators[i-1].value)
            
            # ゴールデンクロス（上昇シグナル）
            if prev_fast <= prev_slow and current_fast > current_slow:
                signals.append({
                    'type': 'golden_cross',
                    'signal': 'BUY',
                    'timestamp': fast_indicators[i].timestamp.isoformat(),
                    'fast_value': current_fast,
                    'slow_value': current_slow
                })
            
            # デッドクロス（下降シグナル）
            elif prev_fast >= prev_slow and current_fast < current_slow:
                signals.append({
                    'type': 'dead_cross',
                    'signal': 'SELL',
                    'timestamp': fast_indicators[i].timestamp.isoformat(),
                    'fast_value': current_fast,
                    'slow_value': current_slow
                })
        
        return signals
    
    def bulk_upsert_indicators(self, indicators_data: List[Dict[str, Any]]) -> int:
        """技術指標データの一括アップサート"""
        upserted_count = 0
        
        for data in indicators_data:
            # 既存データ確認
            existing = self.session.query(TechnicalIndicator).filter(
                and_(
                    TechnicalIndicator.symbol == data['symbol'],
                    TechnicalIndicator.timeframe == data['timeframe'],
                    TechnicalIndicator.timestamp == data['timestamp'],
                    TechnicalIndicator.indicator_type == data['indicator_type']
                )
            ).first()
            
            if existing:
                # 更新
                existing.value = data['value']
                existing.extra_metadata = data.get('metadata', existing.extra_metadata)
            else:
                # 新規作成
                indicator = TechnicalIndicator(**data)
                self.session.add(indicator)
            
            upserted_count += 1
        
        self.session.commit()
        return upserted_count
    
    def delete_old_indicators(self, symbol: str, timeframe: str,
                            days_to_keep: int = 90) -> int:
        """古い技術指標データを削除"""
        cutoff_time = datetime.utcnow() - timedelta(days=days_to_keep)
        
        deleted_count = self.session.query(TechnicalIndicator).filter(
            and_(
                TechnicalIndicator.symbol == symbol,
                TechnicalIndicator.timeframe == timeframe,
                TechnicalIndicator.timestamp < cutoff_time
            )
        ).delete()
        
        self.session.commit()
        return deleted_count
    
    def save_indicator(self, indicator: TechnicalIndicator) -> Optional[TechnicalIndicator]:
        """技術指標を保存（UPSERT対応）"""
        try:
            # Check if indicator already exists
            existing = self.session.query(TechnicalIndicator).filter(
                and_(
                    TechnicalIndicator.symbol == indicator.symbol,
                    TechnicalIndicator.timeframe == indicator.timeframe,
                    TechnicalIndicator.timestamp == indicator.timestamp,
                    TechnicalIndicator.indicator_type == indicator.indicator_type
                )
            ).first()
            
            if existing:
                # Update existing
                existing.value = indicator.value
                if hasattr(indicator, 'extra_metadata') and indicator.extra_metadata:
                    existing.extra_metadata = indicator.extra_metadata
                self.session.commit()
                return existing
            else:
                # Create new
                self.session.add(indicator)
                self.session.commit()
                self.session.refresh(indicator)
                return indicator
                
        except Exception as e:
            self.session.rollback()
            raise e
    
    def get_latest_indicator(self, symbol: str, timeframe: str,
                           indicator_type: str, before_timestamp: Optional[datetime] = None) -> Optional[TechnicalIndicator]:
        """Get latest indicator before a specific timestamp"""
        query = self.session.query(TechnicalIndicator).filter(
            and_(
                TechnicalIndicator.symbol == symbol,
                TechnicalIndicator.timeframe == timeframe,
                TechnicalIndicator.indicator_type == indicator_type
            )
        )
        
        if before_timestamp:
            query = query.filter(TechnicalIndicator.timestamp < before_timestamp)
        
        return query.order_by(desc(TechnicalIndicator.timestamp)).first()