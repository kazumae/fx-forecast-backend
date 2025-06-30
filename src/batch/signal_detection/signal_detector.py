"""
Signal Detection and Validation
高品質なシグナルのみをフィルタリングして通知する
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from src.services.entry_point.signal_validation import SignalValidationService


class SignalPriority(Enum):
    """シグナル優先度"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ValidatedSignal:
    """検証済みシグナル"""
    signal: Dict[str, Any]
    detected_at: datetime
    confidence_score: float
    priority: SignalPriority
    metadata: Dict[str, Any]
    validation_passed: bool = True
    rejection_reason: Optional[str] = None


class SignalDetector:
    """シグナル検出と検証"""
    
    def __init__(self):
        self.validation_service = SignalValidationService()
        self.min_score_threshold = 65.0
        self.min_interval_minutes = 5
        self.min_price_change_percent = 0.1  # 最小価格変動幅（%）
        self.last_signal_times = {}
        
        # 市場時間（UTC）
        self.market_hours = {
            "tokyo": {"open": 0, "close": 9},     # 00:00 - 09:00 UTC
            "london": {"open": 8, "close": 17},   # 08:00 - 17:00 UTC
            "newyork": {"open": 13, "close": 22}  # 13:00 - 22:00 UTC
        }
        
    async def detect_and_validate(
        self, 
        raw_signals: List[Dict[str, Any]],
        timeframe: str,
        symbol: str
    ) -> List[ValidatedSignal]:
        """シグナルを検出して検証"""
        validated_signals = []
        
        for signal in raw_signals:
            # 基本検証
            if not await self._basic_validation(signal):
                continue
                
            # スコア閾値チェック
            score = signal.get('score', 0)
            if score < self.min_score_threshold:
                continue
                
            # 時間間隔チェック
            if not self._check_time_interval(signal, timeframe, symbol):
                continue
                
            # 市場時間チェック
            if not self._is_market_active():
                continue
                
            # 価格変動幅チェック
            if not self._check_price_movement(signal):
                continue
                
            # 4層検証（SignalValidationService）
            validation_result = self.validation_service.validate_signal(signal)
            if not validation_result:
                continue
                
            # 検証済みシグナルの作成
            validated = ValidatedSignal(
                signal=signal,
                detected_at=datetime.utcnow(),
                confidence_score=score,
                priority=self._calculate_priority(signal),
                metadata={
                    "timeframe": timeframe,
                    "symbol": symbol,
                    "market_session": self._get_market_session(),
                    "validation_layers_passed": 4,
                    "score": score,
                    "risk_reward_ratio": signal.get('risk_reward_ratio', 0)
                }
            )
            
            validated_signals.append(validated)
            self._update_last_signal_time(signal, timeframe, symbol)
            
        return validated_signals
        
    async def _basic_validation(self, signal: Dict[str, Any]) -> bool:
        """基本的な検証"""
        # 必須フィールドの確認
        required_fields = ['type', 'score', 'entry_price']
        for field in required_fields:
            if field not in signal:
                return False
                
        # シグナルタイプの確認
        if signal.get('type') not in ['BUY', 'SELL', 'LONG', 'SHORT']:
            return False
            
        return True
        
    def _check_time_interval(self, signal: Dict[str, Any], timeframe: str, symbol: str) -> bool:
        """前回シグナルからの時間間隔をチェック"""
        signal_type = signal.get('type', 'unknown')
        key = f"{symbol}:{timeframe}:{signal_type}"
        last_time = self.last_signal_times.get(key)
        
        if last_time:
            elapsed = datetime.utcnow() - last_time
            if elapsed < timedelta(minutes=self.min_interval_minutes):
                return False
                
        return True
        
    def _update_last_signal_time(self, signal: Dict[str, Any], timeframe: str, symbol: str):
        """最終シグナル時刻を更新"""
        signal_type = signal.get('type', 'unknown')
        key = f"{symbol}:{timeframe}:{signal_type}"
        self.last_signal_times[key] = datetime.utcnow()
        
    def _is_market_active(self) -> bool:
        """主要市場の営業時間をチェック"""
        current_hour = datetime.utcnow().hour
        
        # いずれかの主要市場が開いているか確認
        for market, hours in self.market_hours.items():
            if hours["open"] <= current_hour < hours["close"]:
                return True
                
        # 市場が重なる時間（ロンドン/ニューヨーク）は特に活発
        if 13 <= current_hour < 17:
            return True
            
        return False
        
    def _get_market_session(self) -> str:
        """現在の市場セッションを取得"""
        current_hour = datetime.utcnow().hour
        sessions = []
        
        for market, hours in self.market_hours.items():
            if hours["open"] <= current_hour < hours["close"]:
                sessions.append(market)
                
        return ", ".join(sessions) if sessions else "closed"
        
    def _check_price_movement(self, signal: Dict[str, Any]) -> bool:
        """価格変動幅をチェック"""
        # エントリー価格と現在価格の差を確認
        entry_price = signal.get('entry_price', 0)
        current_price = signal.get('current_price', signal.get('price', entry_price))
        
        if entry_price == 0:
            return False
            
        price_change_percent = abs((current_price - entry_price) / entry_price) * 100
        
        # 最小変動幅以上かチェック
        return price_change_percent >= self.min_price_change_percent
        
    def _calculate_priority(self, signal: Dict[str, Any]) -> SignalPriority:
        """シグナルの優先度を計算"""
        score = signal.get('score', 0)
        risk_reward_ratio = signal.get('risk_reward_ratio', 0)
        
        # スコアとリスク・リワード比を考慮
        if score >= 85 and risk_reward_ratio >= 2.0:
            return SignalPriority.HIGH
        elif score >= 75 or risk_reward_ratio >= 1.5:
            return SignalPriority.MEDIUM
        else:
            return SignalPriority.LOW
            
    def get_validation_summary(self, validated_signals: List[ValidatedSignal]) -> Dict[str, Any]:
        """検証結果のサマリーを取得"""
        if not validated_signals:
            return {
                "total_validated": 0,
                "by_priority": {"high": 0, "medium": 0, "low": 0},
                "average_score": 0,
                "market_sessions": []
            }
            
        priority_counts = {"high": 0, "medium": 0, "low": 0}
        total_score = 0
        market_sessions = set()
        
        for signal in validated_signals:
            priority_counts[signal.priority.value] += 1
            total_score += signal.confidence_score
            market_sessions.add(signal.metadata.get("market_session", ""))
            
        return {
            "total_validated": len(validated_signals),
            "by_priority": priority_counts,
            "average_score": total_score / len(validated_signals),
            "market_sessions": list(market_sessions)
        }