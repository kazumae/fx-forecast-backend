"""
Duplicate Signal Management
重複シグナルの検出と管理を行う
"""
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional, List
import redis
from datetime import datetime

from src.batch.signal_detection import ValidatedSignal


class DuplicateSignalManager:
    """重複シグナル管理"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.ttl_seconds = 300  # 5分
        self.price_tolerance = Decimal("0.001")  # 0.1%
        self.enabled = self.redis is not None
        
    def is_duplicate(self, signal: ValidatedSignal) -> bool:
        """シグナルが重複かチェック"""
        if not self.enabled:
            return False
            
        fingerprint = self._generate_fingerprint(signal)
        
        # Redisでチェック
        if self.redis.exists(fingerprint):
            # 重複カウンターを増加
            timeframe = signal.metadata.get('timeframe', 'unknown')
            self.redis.incr(f"duplicate_count:{timeframe}")
            self.redis.incr(f"duplicate_count:daily:{datetime.utcnow().strftime('%Y%m%d')}")
            return True
            
        # 新規シグナルとして登録
        self._register_signal(fingerprint, signal)
        return False
        
    def _generate_fingerprint(self, signal: ValidatedSignal) -> str:
        """シグナルのフィンガープリントを生成"""
        # 価格を丸める（許容誤差を考慮）
        entry_price = signal.signal.get('entry_price', 0)
        rounded_entry = self._round_price(Decimal(str(entry_price)))
        
        # フィンガープリントの要素
        elements = [
            signal.metadata.get('symbol', 'unknown'),
            signal.metadata.get('timeframe', 'unknown'),
            signal.signal.get('type', 'unknown'),
            str(rounded_entry),
            signal.signal.get('pattern_type', 'unknown')
        ]
        
        # ハッシュ生成
        fingerprint_str = ":".join(elements)
        hash_value = hashlib.md5(fingerprint_str.encode()).hexdigest()
        return f"signal:fp:{hash_value}"
        
    def _round_price(self, price: Decimal) -> Decimal:
        """価格を許容誤差で丸める"""
        if price == 0:
            return Decimal("0")
        
        # 価格帯に応じた刻み幅を決定
        # XAUUSDなどの価格帯（1000-9999）では1.0刻み
        if price < 10:
            step = Decimal("0.01")
        elif price < 100:
            step = Decimal("0.1")
        elif price < 10000:
            step = Decimal("1")  # 主要な通貨ペア・金の価格帯
        else:
            step = Decimal("10")
        
        # 最も近い刻み幅の倍数に丸める（四捨五入）
        factor = (price / step).quantize(Decimal("1"), rounding="ROUND_HALF_UP")
        return factor * step
        
    def _register_signal(self, fingerprint: str, signal: ValidatedSignal):
        """新規シグナルを登録"""
        # シグナルデータを準備
        signal_data = {
            "signal": signal.signal,
            "metadata": signal.metadata,
            "detected_at": signal.detected_at.isoformat(),
            "confidence_score": float(signal.confidence_score),
            "priority": signal.priority.value
        }
        
        # フィンガープリントを保存
        self.redis.setex(
            fingerprint,
            self.ttl_seconds,
            json.dumps(signal_data)
        )
        
        # 統計情報を更新
        timeframe = signal.metadata.get('timeframe', 'unknown')
        self.redis.incr(f"signal_count:{timeframe}")
        self.redis.incr(f"signal_count:daily:{datetime.utcnow().strftime('%Y%m%d')}")
        
    async def get_duplicate_stats(self, timeframe: str = None) -> Dict:
        """重複統計を取得"""
        if not self.enabled:
            return {
                "total_signals": 0,
                "duplicate_signals": 0,
                "duplicate_rate": 0.0,
                "timeframe": timeframe or "all",
                "redis_enabled": False
            }
            
        if timeframe:
            signal_count = int(self.redis.get(f"signal_count:{timeframe}") or 0)
            duplicate_count = int(self.redis.get(f"duplicate_count:{timeframe}") or 0)
        else:
            # 全時間軸の合計
            timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
            signal_count = sum(
                int(self.redis.get(f"signal_count:{tf}") or 0)
                for tf in timeframes
            )
            duplicate_count = sum(
                int(self.redis.get(f"duplicate_count:{tf}") or 0)
                for tf in timeframes
            )
            
        duplicate_rate = 0.0
        total_checks = signal_count + duplicate_count
        if total_checks > 0:
            duplicate_rate = (duplicate_count / total_checks) * 100
            
        return {
            "total_signals": signal_count,
            "duplicate_signals": duplicate_count,
            "duplicate_rate": duplicate_rate,
            "timeframe": timeframe or "all",
            "redis_enabled": True
        }
        
    async def get_daily_stats(self, date: str = None) -> Dict:
        """日次統計を取得"""
        if not self.enabled:
            return {
                "date": date or datetime.utcnow().strftime('%Y%m%d'),
                "total_signals": 0,
                "duplicate_signals": 0,
                "duplicate_rate": 0.0,
                "redis_enabled": False
            }
            
        if not date:
            date = datetime.utcnow().strftime('%Y%m%d')
            
        signal_count = int(self.redis.get(f"signal_count:daily:{date}") or 0)
        duplicate_count = int(self.redis.get(f"duplicate_count:daily:{date}") or 0)
        
        duplicate_rate = 0.0
        total_checks = signal_count + duplicate_count
        if total_checks > 0:
            duplicate_rate = (duplicate_count / total_checks) * 100
            
        return {
            "date": date,
            "total_signals": signal_count,
            "duplicate_signals": duplicate_count,
            "duplicate_rate": duplicate_rate,
            "redis_enabled": True
        }
        
    def clear_stats(self):
        """統計情報をクリア（テスト用）"""
        if not self.enabled:
            return
            
        # パターンマッチングでキーを取得
        for key in self.redis.scan_iter(match="signal_count:*"):
            self.redis.delete(key)
        for key in self.redis.scan_iter(match="duplicate_count:*"):
            self.redis.delete(key)
            
    def get_recent_signals(self, limit: int = 10) -> List[Dict]:
        """最近のシグナルを取得"""
        if not self.enabled:
            return []
            
        signals = []
        # フィンガープリントパターンでスキャン
        for key in self.redis.scan_iter(match="signal:fp:*"):
            ttl = self.redis.ttl(key)
            if ttl > 0:
                signal_data = self.redis.get(key)
                if signal_data:
                    try:
                        data = json.loads(signal_data)
                        data['ttl_remaining'] = ttl
                        data['fingerprint'] = key
                        signals.append(data)
                    except json.JSONDecodeError:
                        continue
                        
        # 検出時刻でソート（新しい順）
        signals.sort(key=lambda x: x.get('detected_at', ''), reverse=True)
        
        return signals[:limit]