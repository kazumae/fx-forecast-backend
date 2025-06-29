"""テストヘルパー関数"""
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
from src.domain.models.market_data import Candlestick
from src.domain.models.zone import Zone, ZoneType, ZoneStatus
from src.domain.models.pattern import PatternSignal, PatternType, PatternStrength
from src.domain.models.entry_signal import (
    EntrySignal, SignalDirection, OrderType,
    EntryOrderInfo, StopLossInfo, TakeProfitLevel,
    RiskRewardInfo, SignalMetadata, ExecutionInfo
)


class CandlestickFactory:
    """ローソク足データファクトリー"""
    
    @staticmethod
    def create_candlestick(
        open_price: float,
        close_price: float,
        high_price: Optional[float] = None,
        low_price: Optional[float] = None,
        timestamp: Optional[datetime] = None,
        symbol: str = "XAUUSD",
        timeframe: str = "1m",
        volume: int = 1000
    ) -> Candlestick:
        """単一のローソク足を作成"""
        if high_price is None:
            high_price = max(open_price, close_price) + 0.5
        if low_price is None:
            low_price = min(open_price, close_price) - 0.5
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        return Candlestick(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            open=Decimal(str(open_price)),
            close=Decimal(str(close_price)),
            high=Decimal(str(high_price)),
            low=Decimal(str(low_price)),
            volume=volume
        )
    
    @staticmethod
    def create_v_shape_candles(
        drop_size: float = 10.0,
        recovery_size: float = 8.0,
        num_drop_candles: int = 5,
        num_recovery_candles: int = 4
    ) -> List[Candlestick]:
        """V字型パターンのローソク足を作成"""
        candles = []
        base_price = 3280.0
        base_time = datetime.now(timezone.utc)
        
        # 下落フェーズ
        for i in range(num_drop_candles):
            price_drop = (drop_size / num_drop_candles) * i
            open_p = base_price - price_drop
            close_p = base_price - price_drop - (drop_size / num_drop_candles)
            
            candle = CandlestickFactory.create_candlestick(
                open_price=open_p,
                close_price=close_p,
                timestamp=base_time + timedelta(minutes=i)
            )
            candles.append(candle)
        
        # 反転フェーズ
        bottom_price = base_price - drop_size
        for i in range(num_recovery_candles):
            price_rise = (recovery_size / num_recovery_candles) * i
            open_p = bottom_price + price_rise
            close_p = bottom_price + price_rise + (recovery_size / num_recovery_candles)
            
            candle = CandlestickFactory.create_candlestick(
                open_price=open_p,
                close_price=close_p,
                timestamp=base_time + timedelta(minutes=num_drop_candles + i)
            )
            candles.append(candle)
        
        return candles
    
    @staticmethod
    def create_trend_candles(
        direction: str = "up",
        num_candles: int = 10,
        price_change: float = 0.5
    ) -> List[Candlestick]:
        """トレンドのローソク足を作成"""
        candles = []
        base_price = 3275.0
        base_time = datetime.now(timezone.utc)
        
        for i in range(num_candles):
            if direction == "up":
                open_p = base_price + (price_change * i)
                close_p = open_p + price_change * 0.8
            else:
                open_p = base_price - (price_change * i)
                close_p = open_p - price_change * 0.8
            
            candle = CandlestickFactory.create_candlestick(
                open_price=open_p,
                close_price=close_p,
                timestamp=base_time + timedelta(minutes=i)
            )
            candles.append(candle)
        
        return candles


class ZoneFactory:
    """ゾーンデータファクトリー"""
    
    @staticmethod
    def create_zone(
        upper: float,
        lower: float,
        zone_type: ZoneType = ZoneType.RESISTANCE,
        strength: float = 0.85,
        touch_count: int = 3,
        symbol: str = "XAUUSD",
        zone_id: Optional[str] = None
    ) -> Zone:
        """単一のゾーンを作成"""
        if zone_id is None:
            zone_id = f"test_zone_{uuid.uuid4().hex[:8]}"
        
        return Zone(
            id=zone_id,
            symbol=symbol,
            upper_bound=Decimal(str(upper)),
            lower_bound=Decimal(str(lower)),
            zone_type=zone_type,
            strength=strength,
            touch_count=touch_count,
            status=ZoneStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            last_touched=datetime.now(timezone.utc)
        )
    
    @staticmethod
    def create_major_zones(base_price: float = 3275.0) -> List[Zone]:
        """主要なゾーンセットを作成"""
        zones = []
        
        # レジスタンスゾーン
        zones.append(ZoneFactory.create_zone(
            upper=base_price + 10,
            lower=base_price + 8,
            zone_type=ZoneType.RESISTANCE,
            strength=0.9,
            touch_count=5
        ))
        
        zones.append(ZoneFactory.create_zone(
            upper=base_price + 5,
            lower=base_price + 3,
            zone_type=ZoneType.RESISTANCE,
            strength=0.75,
            touch_count=3
        ))
        
        # サポートゾーン
        zones.append(ZoneFactory.create_zone(
            upper=base_price - 3,
            lower=base_price - 5,
            zone_type=ZoneType.SUPPORT,
            strength=0.8,
            touch_count=4
        ))
        
        zones.append(ZoneFactory.create_zone(
            upper=base_price - 8,
            lower=base_price - 10,
            zone_type=ZoneType.SUPPORT,
            strength=0.95,
            touch_count=6
        ))
        
        return zones


class SignalFactory:
    """シグナルデータファクトリー"""
    
    @staticmethod
    def create_pattern_signal(
        pattern_type: PatternType = PatternType.V_SHAPE_REVERSAL,
        confidence: float = 85.0,
        direction: str = "bullish",
        detected_at: Optional[datetime] = None
    ) -> PatternSignal:
        """パターンシグナルを作成"""
        if detected_at is None:
            detected_at = datetime.now(timezone.utc)
        
        return PatternSignal(
            pattern_type=pattern_type,
            symbol="XAUUSD",
            timeframe="1m",
            detected_at=detected_at,
            confidence=confidence,
            strength=PatternStrength.STRONG if confidence >= 80 else PatternStrength.MODERATE,
            direction=direction,
            parameters={
                "drop_angle": 55.0,
                "recovery_ratio": 0.8,
                "volume_increase": 1.5
            },
            entry_point=Decimal("3275.50"),
            stop_loss=Decimal("3270.00"),
            take_profit=Decimal("3285.00")
        )
    
    @staticmethod
    def create_entry_signal(
        direction: SignalDirection = SignalDirection.LONG,
        entry_price: float = 3275.50,
        sl_price: float = 3270.00,
        tp_prices: List[float] = None,
        pattern_type: str = "V_SHAPE_REVERSAL"
    ) -> EntrySignal:
        """エントリーシグナルを作成"""
        if tp_prices is None:
            tp_prices = [3280.00, 3285.00, 3290.00]
        
        now = datetime.now(timezone.utc)
        
        # SL距離計算
        sl_distance = abs(entry_price - sl_price) * 100  # pips
        
        # TP作成
        take_profits = []
        tp_percentages = [50.0, 30.0, 20.0]
        for i, (tp_price, percentage) in enumerate(zip(tp_prices, tp_percentages)):
            tp_distance = abs(tp_price - entry_price) * 100
            take_profits.append(TakeProfitLevel(
                level=i + 1,
                price=Decimal(str(tp_price)),
                distance_pips=tp_distance,
                percentage=percentage,
                reason=f"TP{i+1}"
            ))
        
        # RR比計算
        rr_ratios = [tp.distance_pips / sl_distance for tp in take_profits]
        weighted_rr = sum(rr * (tp.percentage / 100) for rr, tp in zip(rr_ratios, take_profits))
        
        return EntrySignal(
            id=f"test_signal_{uuid.uuid4().hex[:8]}",
            symbol="XAUUSD",
            timestamp=now,
            direction=direction,
            entry=EntryOrderInfo(
                price=Decimal(str(entry_price)),
                order_type=OrderType.MARKET,
                valid_until=now + timedelta(hours=1),
                slippage_pips=1.0
            ),
            stop_loss=StopLossInfo(
                price=Decimal(str(sl_price)),
                distance_pips=sl_distance,
                reason="Zone-based SL"
            ),
            take_profits=take_profits,
            risk_reward=RiskRewardInfo(
                risk_pips=sl_distance,
                tp1_reward_pips=take_profits[0].distance_pips if take_profits else 0,
                tp2_reward_pips=take_profits[1].distance_pips if len(take_profits) > 1 else None,
                tp3_reward_pips=take_profits[2].distance_pips if len(take_profits) > 2 else None,
                tp1_rr_ratio=rr_ratios[0] if rr_ratios else 0,
                tp2_rr_ratio=rr_ratios[1] if len(rr_ratios) > 1 else None,
                tp3_rr_ratio=rr_ratios[2] if len(rr_ratios) > 2 else None,
                weighted_rr_ratio=weighted_rr
            ),
            metadata=SignalMetadata(
                pattern_type=pattern_type,
                confidence_score=0.85,
                zone_strength=0.9,
                timeframe="1m",
                analysis_version="1.0"
            ),
            execution=ExecutionInfo(
                priority="high",
                max_slippage=2.0,
                retry_count=3,
                execution_mode="immediate"
            )
        )


class MarketDataGenerator:
    """市場データジェネレーター"""
    
    @staticmethod
    def generate_random_walk(
        num_points: int = 100,
        start_price: float = 3275.0,
        volatility: float = 0.5,
        trend: float = 0.01
    ) -> List[Candlestick]:
        """ランダムウォークデータを生成"""
        import random
        
        candles = []
        base_time = datetime.now(timezone.utc)
        current_price = start_price
        
        for i in range(num_points):
            # トレンド付きランダムウォーク
            change = random.gauss(trend, volatility)
            open_p = current_price
            close_p = current_price + change
            
            # 高値・安値も追加
            high_p = max(open_p, close_p) + abs(random.gauss(0, volatility * 0.5))
            low_p = min(open_p, close_p) - abs(random.gauss(0, volatility * 0.5))
            
            candle = CandlestickFactory.create_candlestick(
                open_price=open_p,
                close_price=close_p,
                high_price=high_p,
                low_price=low_p,
                timestamp=base_time + timedelta(minutes=i),
                volume=int(1000 + random.gauss(0, 200))
            )
            candles.append(candle)
            
            current_price = close_p
        
        return candles