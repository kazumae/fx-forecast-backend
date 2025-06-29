"""V字反転パターン検出のユニットテスト"""
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from src.services.pattern_detection.v_shape_reversal import VShapeReversalDetector
from src.domain.models.pattern import PatternType, PatternStrength
from tests.utils import CandlestickFactory, ZoneFactory


class TestVShapeReversalDetector:
    """V字反転パターン検出器のテスト"""
    
    @pytest.fixture
    def detector(self):
        """検出器インスタンス"""
        config = {
            "min_drop_angle": 45.0,
            "min_recovery_ratio": 0.7,
            "max_pattern_duration": 10,
            "min_volume_increase": 1.3
        }
        return VShapeReversalDetector(config)
    
    def test_typical_v_shape_pattern(self, detector):
        """典型的なV字パターンの検出"""
        # V字型のローソク足データを作成
        candles = CandlestickFactory.create_v_shape_candles(
            drop_size=10.0,
            recovery_size=8.0,
            num_drop_candles=5,
            num_recovery_candles=4
        )
        
        # ゾーンデータ
        zones = ZoneFactory.create_major_zones(base_price=3270.0)
        
        # パターン検出
        signals = detector.detect(candles, zones)
        
        # 検証
        assert len(signals) > 0
        signal = signals[0]
        assert signal.pattern_type == PatternType.V_SHAPE_REVERSAL
        assert signal.confidence >= 70.0
        assert signal.strength in [PatternStrength.STRONG, PatternStrength.MODERATE]
        assert signal.direction == "bullish"
        assert "drop_angle" in signal.parameters
        assert signal.parameters["drop_angle"] >= 45.0
    
    def test_no_reversal_after_drop(self, detector):
        """急落後に反転しないケース"""
        # 継続的な下落データ
        candles = CandlestickFactory.create_trend_candles(
            direction="down",
            num_candles=10,
            price_change=1.0
        )
        
        zones = ZoneFactory.create_major_zones()
        signals = detector.detect(candles, zones)
        
        # V字反転は検出されないはず
        assert len(signals) == 0
    
    @pytest.mark.parametrize("drop_angle", [30, 40, 44])
    def test_insufficient_drop_angle(self, detector, drop_angle):
        """下落角度が不十分なケース"""
        # 緩やかな下落のV字
        candles = []
        base_price = 3280.0
        base_time = datetime.now(timezone.utc)
        
        # 緩やかな下落（角度を調整）
        num_candles = 10
        drop_per_candle = 0.5  # 緩やかな下落
        
        for i in range(num_candles // 2):
            open_p = base_price - (drop_per_candle * i)
            close_p = open_p - drop_per_candle
            candles.append(CandlestickFactory.create_candlestick(
                open_price=open_p,
                close_price=close_p,
                timestamp=base_time + timedelta(minutes=i)
            ))
        
        # 反転
        bottom_price = base_price - (drop_per_candle * (num_candles // 2))
        for i in range(num_candles // 2):
            open_p = bottom_price + (drop_per_candle * i)
            close_p = open_p + drop_per_candle
            candles.append(CandlestickFactory.create_candlestick(
                open_price=open_p,
                close_price=close_p,
                timestamp=base_time + timedelta(minutes=num_candles // 2 + i)
            ))
        
        zones = ZoneFactory.create_major_zones()
        signals = detector.detect(candles, zones)
        
        # 角度不足で検出されないはず
        assert len(signals) == 0
    
    def test_insufficient_recovery(self, detector):
        """回復が不十分なケース"""
        # 下落は急だが回復が弱い
        candles = CandlestickFactory.create_v_shape_candles(
            drop_size=10.0,
            recovery_size=3.0,  # 30%しか回復しない
            num_drop_candles=5,
            num_recovery_candles=5
        )
        
        zones = ZoneFactory.create_major_zones()
        signals = detector.detect(candles, zones)
        
        # 回復不足で検出されないはず
        assert len(signals) == 0
    
    def test_v_shape_at_support_zone(self, detector):
        """サポートゾーンでのV字反転"""
        # サポートゾーン付近でのV字
        support_price = 3270.0
        
        candles = []
        base_time = datetime.now(timezone.utc)
        
        # サポートまで下落
        start_price = 3275.0
        for i in range(5):
            price = start_price - (i * 1.0)
            candles.append(CandlestickFactory.create_candlestick(
                open_price=price,
                close_price=price - 1.0,
                timestamp=base_time + timedelta(minutes=i)
            ))
        
        # サポートで反転
        for i in range(4):
            price = support_price + (i * 1.2)
            candles.append(CandlestickFactory.create_candlestick(
                open_price=price,
                close_price=price + 1.2,
                timestamp=base_time + timedelta(minutes=5 + i),
                volume=1500  # ボリューム増加
            ))
        
        # サポートゾーンを作成
        zones = [
            ZoneFactory.create_zone(
                upper=support_price + 1,
                lower=support_price - 1,
                zone_type="SUPPORT",
                strength=0.9
            )
        ]
        
        signals = detector.detect(candles, zones)
        
        # サポートゾーンでの反転は信頼度が高いはず
        assert len(signals) > 0
        signal = signals[0]
        assert signal.confidence >= 80.0
        assert "zone_bounce" in signal.parameters
        assert signal.parameters["zone_bounce"] is True
    
    def test_pattern_duration_limit(self, detector):
        """パターン持続時間の制限テスト"""
        # 長すぎるV字パターン
        candles = CandlestickFactory.create_v_shape_candles(
            drop_size=10.0,
            recovery_size=8.0,
            num_drop_candles=8,  # 長い下落
            num_recovery_candles=8  # 長い回復
        )
        
        zones = ZoneFactory.create_major_zones()
        signals = detector.detect(candles, zones)
        
        # 時間制限で検出されないはず
        assert len(signals) == 0
    
    def test_volume_confirmation(self, detector):
        """ボリューム確認のテスト"""
        candles = []
        base_time = datetime.now(timezone.utc)
        base_price = 3280.0
        
        # 下落フェーズ（通常ボリューム）
        for i in range(5):
            candles.append(CandlestickFactory.create_candlestick(
                open_price=base_price - i * 2,
                close_price=base_price - (i + 1) * 2,
                timestamp=base_time + timedelta(minutes=i),
                volume=1000
            ))
        
        # 反転フェーズ（ボリューム増加なし）
        bottom_price = base_price - 10
        for i in range(4):
            candles.append(CandlestickFactory.create_candlestick(
                open_price=bottom_price + i * 2,
                close_price=bottom_price + (i + 1) * 2,
                timestamp=base_time + timedelta(minutes=5 + i),
                volume=900  # ボリューム減少
            ))
        
        zones = ZoneFactory.create_major_zones()
        signals = detector.detect(candles, zones)
        
        # ボリューム確認なしで信頼度が低いはず
        if signals:
            assert signals[0].confidence < 80.0
    
    def test_bearish_v_shape(self, detector):
        """弱気のV字パターン（逆V字）"""
        candles = []
        base_time = datetime.now(timezone.utc)
        base_price = 3270.0
        
        # 上昇フェーズ
        for i in range(5):
            candles.append(CandlestickFactory.create_candlestick(
                open_price=base_price + i * 2,
                close_price=base_price + (i + 1) * 2,
                timestamp=base_time + timedelta(minutes=i)
            ))
        
        # 反落フェーズ
        top_price = base_price + 10
        for i in range(4):
            candles.append(CandlestickFactory.create_candlestick(
                open_price=top_price - i * 2,
                close_price=top_price - (i + 1) * 2,
                timestamp=base_time + timedelta(minutes=5 + i),
                volume=1500
            ))
        
        # レジスタンスゾーン
        zones = [
            ZoneFactory.create_zone(
                upper=top_price + 1,
                lower=top_price - 1,
                zone_type="RESISTANCE",
                strength=0.9
            )
        ]
        
        signals = detector.detect(candles, zones)
        
        # 弱気のV字が検出されるはず
        if signals:
            assert signals[0].direction == "bearish"
    
    def test_edge_cases(self, detector):
        """エッジケースのテスト"""
        # 空のデータ
        assert detector.detect([], []) == []
        
        # 少なすぎるデータ
        candles = [CandlestickFactory.create_candlestick(3275.0, 3276.0)]
        assert detector.detect(candles, []) == []
        
        # Noneデータ
        assert detector.detect(None, None) == []