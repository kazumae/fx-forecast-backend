"""
Enhanced Signal Monitor Job with Pattern Detection
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from decimal import Decimal
import redis
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from src.batch.base import BaseBatchJob
from src.core.config import settings
from src.db.session import SessionLocal, AsyncSessionLocal
from src.models.forex import ForexRate
from src.models.candlestick import CandlestickData
from src.models.technical_indicator import TechnicalIndicator
from src.batch.utils.slack_notifier import SlackNotifier
from src.batch.signal_detection import SignalDetector, ValidatedSignal
from src.batch.duplicate_management import DuplicateSignalManager

# Pattern Detectors
from src.services.entry_point.pattern_detection.ema_squeeze_detector import EMASqueezeDetector
from src.services.entry_point.pattern_detection.trend_continuation_detector import TrendContinuationDetector
from src.services.entry_point.pattern_detection.v_shape_detector import VShapeDetector
from src.services.entry_point.pattern_detection.false_breakout_detector import FalseBreakoutDetector

# Domain models
from src.domain.models.market import MarketContext, Indicators
from src.models.candlestick import CandlestickData


class EnhancedSignalMonitorJob(BaseBatchJob):
    """Enhanced Entry Point Monitor with Pattern Detection
    
    1分毎に@docs/logic/のパターンを検出してシグナルを生成
    """
    
    def __init__(self):
        super().__init__(
            job_name="signal_monitor_v2",
            enable_slack_notification=True
        )
        
        # Pattern Detectors
        self.pattern_detectors = [
            EMASqueezeDetector(),
            TrendContinuationDetector(),
            VShapeDetector(),
            FalseBreakoutDetector()
        ]
        
        # Signal validation
        self.signal_detector = SignalDetector()
        
        # Redis for duplicate detection
        try:
            self.redis_client = redis.from_url(
                "redis://redis:6379",
                decode_responses=True
            )
            self.redis_enabled = True
        except Exception as e:
            self.logger.warning(f"Redis connection failed: {e}")
            self.redis_client = None
            self.redis_enabled = False
            
        # Duplicate management
        self.duplicate_manager = DuplicateSignalManager(self.redis_client)
        
        # Configuration
        self.target_symbols = ["XAUUSD"]
        self.timeframes = ["1m", "5m", "15m", "1h"]
        self.min_confidence = 65.0  # 最小信頼度
        
    def execute(self) -> Dict[str, Any]:
        """メイン実行処理"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(self._execute_async())
            return result
        finally:
            loop.close()
            
    async def _execute_async(self) -> Dict[str, Any]:
        """非同期実行処理"""
        start_time = datetime.now(timezone.utc)
        all_detected_signals = []
        errors = []
        
        try:
            # 各シンボルでパターン検出
            for symbol in self.target_symbols:
                try:
                    signals = await self._detect_patterns_for_symbol(symbol)
                    all_detected_signals.extend(signals)
                except Exception as e:
                    self.logger.error(f"Error detecting patterns for {symbol}: {e}")
                    errors.append({
                        "symbol": symbol,
                        "error": str(e),
                        "timestamp": datetime.now(timezone.utc)
                    })
                    
            # 実行詳細を設定
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.set_execution_detail("実行時間", f"{execution_time:.2f}秒")
            self.set_execution_detail("検出シグナル数", len(all_detected_signals))
            self.set_execution_detail("エラー数", len(errors))
            
            # シグナルが検出された場合は通知
            if all_detected_signals:
                await self._notify_signals(all_detected_signals)
                
            return {
                "status": "success",
                "signals": all_detected_signals,
                "errors": errors,
                "execution_time": execution_time
            }
            
        except Exception as e:
            self.logger.error(f"Fatal error in signal monitor: {e}")
            raise
            
    async def _detect_patterns_for_symbol(self, symbol: str) -> List[ValidatedSignal]:
        """特定シンボルのパターンを検出"""
        all_signals = []
        
        # 各時間枠でチェック
        for timeframe in self.timeframes:
            try:
                # マーケットコンテキストを構築
                market_context = await self._build_market_context(symbol, timeframe)
                
                if not market_context:
                    continue
                
                # 各パターン検出器でチェック
                for detector in self.pattern_detectors:
                    try:
                        # パターン検出
                        pattern_signals = await detector.detect(market_context)
                        
                        # 検出されたパターンを処理
                        for pattern_signal in pattern_signals:
                            # 信頼度チェック
                            if pattern_signal.confidence < self.min_confidence:
                                continue
                            
                            # シグナルに変換
                            raw_signal = self._convert_to_raw_signal(pattern_signal)
                            
                            # 検証
                            validated_signals = await self.signal_detector.detect_and_validate(
                                raw_signals=[raw_signal],
                                timeframe=timeframe,
                                symbol=symbol
                            )
                            
                            # 重複チェック
                            for validated in validated_signals:
                                if not self.duplicate_manager.is_duplicate(validated):
                                    all_signals.append(validated)
                                    
                    except Exception as e:
                        self.logger.error(f"Error in {detector.__class__.__name__}: {e}")
                        
            except Exception as e:
                self.logger.error(f"Error processing {symbol} {timeframe}: {e}")
                
        return all_signals
        
    async def _build_market_context(self, symbol: str, timeframe: str) -> Optional[MarketContext]:
        """マーケットコンテキストを構築"""
        async with AsyncSessionLocal() as db:
            try:
                # ローソク足データを取得
                candle_limit = {"1m": 60, "5m": 48, "15m": 32, "1h": 24}.get(timeframe, 60)
                
                candles_query = select(CandlestickData).where(
                    and_(
                        CandlestickData.symbol == symbol,
                        CandlestickData.timeframe == timeframe
                    )
                ).order_by(CandlestickData.open_time.desc()).limit(candle_limit)
                
                result = await db.execute(candles_query)
                candle_data = result.scalars().all()
                
                if not candle_data:
                    return None
                    
                # CandlestickDataオブジェクトのリストを作成（古い順）
                candles = list(reversed(candle_data))
                
                # 最新のテクニカル指標を取得
                indicators_query = select(TechnicalIndicator).where(
                    and_(
                        TechnicalIndicator.symbol == symbol,
                        TechnicalIndicator.timeframe == timeframe
                    )
                ).order_by(TechnicalIndicator.timestamp.desc()).limit(1)
                
                result = await db.execute(indicators_query)
                indicator_data = result.scalar_one_or_none()
                
                # Indicatorsオブジェクトに変換
                indicators = None
                if indicator_data:
                    indicators = Indicators(
                        ema20=Decimal(str(indicator_data.ema_20)) if indicator_data.ema_20 else Decimal("0"),
                        ema75=Decimal(str(indicator_data.ema_50)) if indicator_data.ema_50 else Decimal("0"),  # ema75の代わりにema50を使用
                        ema200=Decimal(str(indicator_data.ema_200)) if indicator_data.ema_200 else Decimal("0"),
                        atr14=Decimal(str(indicator_data.atr_14)) if indicator_data.atr_14 else Decimal("0")
                    )
                
                # 現在価格
                current_candle = candles[-1] if candles else None
                
                if not current_candle or not indicators:
                    return None
                
                # MarketContextを構築
                return MarketContext(
                    symbol=symbol,
                    timestamp=datetime.now(timezone.utc),
                    current_candle=current_candle,
                    recent_candles=candles[:-1],  # 現在のキャンドルを除く
                    indicators=indicators,
                    nearby_zones=[]  # TODO: ゾーン情報を追加
                )
                
            except Exception as e:
                self.logger.error(f"Error building market context: {e}")
                return None
                
    def _get_session_info(self) -> Dict[str, Any]:
        """現在の市場セッション情報を取得"""
        current_hour = datetime.now(timezone.utc).hour
        
        sessions = []
        if 0 <= current_hour < 9:
            sessions.append("Tokyo")
        if 8 <= current_hour < 17:
            sessions.append("London")
        if 13 <= current_hour < 22:
            sessions.append("NewYork")
            
        return {
            "active_sessions": sessions,
            "is_overlap": len(sessions) > 1,
            "hour_utc": current_hour
        }
        
    def _convert_to_raw_signal(self, pattern_signal) -> Dict[str, Any]:
        """PatternSignalを生のシグナル辞書に変換"""
        return {
            "type": pattern_signal.direction.value,
            "score": pattern_signal.confidence,
            "entry_price": float(pattern_signal.price_level),
            "current_price": float(pattern_signal.price_level),
            "pattern_type": pattern_signal.pattern_type.value,
            "timeframe": pattern_signal.timeframe,
            "detected_at": pattern_signal.detected_at,
            "risk_reward_ratio": 1.5,  # デフォルト値
            "metadata": pattern_signal.parameters
        }
        
    async def _notify_signals(self, signals: List[ValidatedSignal]):
        """検出されたシグナルを通知"""
        if not signals:
            return
            
        # 優先度でソート
        priority_order = {"high": 0, "medium": 1, "low": 2}
        sorted_signals = sorted(signals, key=lambda x: priority_order.get(x.priority.value, 3))
        
        # Slack通知の構築
        fields = []
        for signal in sorted_signals[:5]:  # 最大5件
            priority_emoji = {
                "high": "🔴",
                "medium": "🟡", 
                "low": "🟢"
            }.get(signal.priority.value, "⚪")
            
            pattern_type = signal.signal.get('pattern_type', 'Unknown')
            
            fields.append({
                "title": f"{priority_emoji} {signal.metadata['symbol']} - {pattern_type}",
                "value": (
                    f"Direction: {signal.signal.get('type', 'Unknown')}\n"
                    f"Confidence: {signal.confidence_score:.1f}%\n"
                    f"Timeframe: {signal.metadata['timeframe']}"
                ),
                "short": True
            })
            
        # メッセージ作成
        message = (
            f"🎯 {len(signals)}件のエントリーパターンを検出しました\n"
            f"検出時刻: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
            
        self.send_custom_notification(
            title="エントリーポイント検出",
            message=message,
            color="good",
            fields=fields
        )
        
    def should_notify_on_start(self) -> bool:
        return False  # 1分毎なので開始通知は不要
        
    def should_notify_on_complete(self) -> bool:
        return False  # 個別完了通知は不要
        
    def should_notify_on_error(self) -> bool:
        return True