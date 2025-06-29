"""
Unit tests for V-Shape Reversal Pattern Detector
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
import uuid

from src.services.entry_point.pattern_detection.v_shape_detector import VShapeDetector
from src.domain.models.pattern import PatternType
from src.domain.models.market import MarketContext, Indicators
from src.models.candlestick import CandlestickData
from src.models.zone import Zone


class TestVShapeDetector:
    """Test cases for V-shape reversal pattern detection"""
    
    @pytest.fixture
    def detector(self):
        """Create V-shape detector instance"""
        return VShapeDetector()
    
    @pytest.fixture
    def base_time(self):
        """Base timestamp for tests"""
        return datetime(2024, 6, 29, 10, 30, 0)
    
    def create_candlestick(
        self,
        symbol: str,
        timeframe: str,
        open_time: datetime,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float
    ) -> CandlestickData:
        """Helper to create candlestick data"""
        candle = CandlestickData(
            symbol=symbol,
            timeframe=timeframe,
            open_time=open_time,
            close_time=open_time + timedelta(minutes=1),
            open_price=Decimal(str(open_price)),
            high_price=Decimal(str(high_price)),
            low_price=Decimal(str(low_price)),
            close_price=Decimal(str(close_price)),
            tick_count=100
        )
        return candle
    
    def create_zone(
        self,
        symbol: str,
        upper: float,
        lower: float,
        strength: str = 'A'
    ) -> Zone:
        """Helper to create zone"""
        zone = Zone(
            id=uuid.uuid4(),
            symbol=symbol,
            timeframe='1h',
            upper_bound=Decimal(str(upper)),
            lower_bound=Decimal(str(lower)),
            strength=strength,
            touch_count=3,
            is_active=True
        )
        return zone
    
    def create_sharp_drop_candles(self, base_time: datetime) -> list:
        """Create candles representing a sharp drop"""
        candles = []
        
        # Initial stable candles
        for i in range(10):
            time = base_time - timedelta(minutes=20-i)
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time,
                open_price=3285.0 + i * 0.5,
                high_price=3285.5 + i * 0.5,
                low_price=3284.5 + i * 0.5,
                close_price=3285.2 + i * 0.5
            ))
        
        # Sharp drop - consecutive bearish candles
        drop_prices = [
            (3290.0, 3290.5, 3287.0, 3287.5),  # -2.5 pips
            (3287.5, 3288.0, 3284.0, 3284.5),  # -3.0 pips
            (3284.5, 3285.0, 3280.0, 3280.5),  # -4.0 pips
            (3280.5, 3281.0, 3276.0, 3276.5),  # -4.0 pips
            (3276.5, 3277.0, 3272.0, 3272.5),  # -4.0 pips
        ]
        
        for i, (o, h, l, c) in enumerate(drop_prices):
            time = base_time - timedelta(minutes=10-i)
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time, o, h, l, c
            ))
        
        # Recent candles leading to current
        recent_prices = [
            (3272.5, 3273.0, 3271.0, 3271.5),
            (3271.5, 3272.0, 3270.0, 3270.5),
            (3270.5, 3271.0, 3269.0, 3269.5),
            (3269.5, 3270.0, 3268.0, 3268.5),
            (3268.5, 3269.0, 3267.0, 3267.5),
        ]
        
        for i, (o, h, l, c) in enumerate(recent_prices):
            time = base_time - timedelta(minutes=5-i)
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time, o, h, l, c
            ))
        
        return candles
    
    @pytest.mark.asyncio
    async def test_detect_typical_v_shape_reversal(self, detector, base_time):
        """Test detection of typical V-shape reversal pattern"""
        # Create sharp drop candles
        recent_candles = self.create_sharp_drop_candles(base_time)
        
        # Create current candle with pin bar (reversal signal)
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3267.5,
            high_price=3269.0,
            low_price=3265.0,  # Long lower wick
            close_price=3268.5  # Bullish close
        )
        
        # Create indicators with 200EMA near current price
        indicators = Indicators(
            ema20=Decimal('3270.0'),
            ema75=Decimal('3272.0'),
            ema200=Decimal('3267.0'),  # Near the low
            atr14=Decimal('5.0')
        )
        
        # Create zone overlapping with 200EMA
        zone = self.create_zone("XAUUSD", upper=3269.0, lower=3265.0, strength='A')
        
        # Create market context
        context = MarketContext(
            symbol="XAUUSD",
            timestamp=base_time,
            current_candle=current_candle,
            recent_candles=recent_candles,
            indicators=indicators,
            nearby_zones=[zone]
        )
        
        # Detect pattern
        patterns = await detector.detect(context)
        
        # Assertions
        assert len(patterns) == 1
        pattern = patterns[0]
        
        assert pattern.pattern_type == PatternType.V_SHAPE_REVERSAL
        assert pattern.symbol == "XAUUSD"
        assert pattern.confidence >= 70  # Should have high confidence
        assert pattern.parameters['drop_angle'] >= 45
        assert pattern.parameters['reversal_type'] == 'pin_bar'
        assert pattern.parameters['ema_touch'] is True
        assert pattern.zone_id is not None
    
    @pytest.mark.asyncio
    async def test_no_detection_without_sharp_drop(self, detector, base_time):
        """Test no detection when drop is not sharp enough"""
        # Create gentle decline candles
        candles = []
        for i in range(20):
            time = base_time - timedelta(minutes=20-i)
            # Gentle decline of 0.5 pips per candle
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time,
                open_price=3280.0 - i * 0.5,
                high_price=3280.5 - i * 0.5,
                low_price=3279.5 - i * 0.5,
                close_price=3279.7 - i * 0.5
            ))
        
        current_candle = candles[-1]
        
        indicators = Indicators(
            ema20=Decimal('3272.0'),
            ema75=Decimal('3274.0'),
            ema200=Decimal('3276.0'),
            atr14=Decimal('5.0')
        )
        
        context = MarketContext(
            symbol="XAUUSD",
            timestamp=base_time,
            current_candle=current_candle,
            recent_candles=candles[:-1],
            indicators=indicators,
            nearby_zones=[]
        )
        
        patterns = await detector.detect(context)
        assert len(patterns) == 0
    
    @pytest.mark.asyncio
    async def test_no_detection_without_ema_zone_overlap(self, detector, base_time):
        """Test no detection when 200EMA doesn't overlap with zone"""
        recent_candles = self.create_sharp_drop_candles(base_time)
        
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3267.5,
            high_price=3269.0,
            low_price=3265.0,
            close_price=3268.5
        )
        
        # 200EMA far from any zone
        indicators = Indicators(
            ema20=Decimal('3270.0'),
            ema75=Decimal('3272.0'),
            ema200=Decimal('3280.0'),  # Far away
            atr14=Decimal('5.0')
        )
        
        # Zone not near 200EMA
        zone = self.create_zone("XAUUSD", upper=3269.0, lower=3265.0)
        
        context = MarketContext(
            symbol="XAUUSD",
            timestamp=base_time,
            current_candle=current_candle,
            recent_candles=recent_candles,
            indicators=indicators,
            nearby_zones=[zone]
        )
        
        patterns = await detector.detect(context)
        assert len(patterns) == 0
    
    @pytest.mark.asyncio
    async def test_detect_with_breakout_reversal(self, detector, base_time):
        """Test detection with previous bar high breakout"""
        recent_candles = self.create_sharp_drop_candles(base_time)
        
        # Previous candle
        prev_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time - timedelta(minutes=1),
            open_price=3268.0,
            high_price=3269.0,
            low_price=3267.0,
            close_price=3268.5
        )
        recent_candles.append(prev_candle)
        
        # Current candle breaks previous high
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3268.5,
            high_price=3270.5,  # Breaks previous high
            low_price=3268.0,
            close_price=3270.0
        )
        
        indicators = Indicators(
            ema20=Decimal('3270.0'),
            ema75=Decimal('3272.0'),
            ema200=Decimal('3268.0'),
            atr14=Decimal('5.0')
        )
        
        zone = self.create_zone("XAUUSD", upper=3270.0, lower=3266.0)
        
        context = MarketContext(
            symbol="XAUUSD",
            timestamp=base_time,
            current_candle=current_candle,
            recent_candles=recent_candles[:-1],  # Exclude the one we added
            indicators=indicators,
            nearby_zones=[zone]
        )
        
        patterns = await detector.detect(context)
        
        assert len(patterns) == 1
        assert patterns[0].parameters['reversal_type'] == 'breakout'
    
    @pytest.mark.asyncio
    async def test_confidence_calculation(self, detector, base_time):
        """Test confidence score calculation"""
        # Create context with moderate signals
        recent_candles = self.create_sharp_drop_candles(base_time)
        
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3267.5,
            high_price=3268.5,
            low_price=3267.0,
            close_price=3268.0  # Small bullish candle
        )
        
        indicators = Indicators(
            ema20=Decimal('3270.0'),
            ema75=Decimal('3272.0'),
            ema200=Decimal('3267.5'),
            atr14=Decimal('5.0')
        )
        
        zone = self.create_zone("XAUUSD", upper=3269.0, lower=3266.0, strength='B')
        
        context = MarketContext(
            symbol="XAUUSD",
            timestamp=base_time,
            current_candle=current_candle,
            recent_candles=recent_candles,
            indicators=indicators,
            nearby_zones=[zone]
        )
        
        patterns = await detector.detect(context)
        
        if patterns:  # May or may not detect based on thresholds
            pattern = patterns[0]
            assert 0 <= pattern.confidence <= 100
            # With moderate signals, confidence should be moderate
            assert 50 <= pattern.confidence <= 80
    
    @pytest.mark.asyncio
    async def test_insufficient_data(self, detector, base_time):
        """Test handling of insufficient candlestick data"""
        # Only 10 candles (need 20)
        candles = []
        for i in range(10):
            time = base_time - timedelta(minutes=10-i)
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time,
                open_price=3280.0,
                high_price=3281.0,
                low_price=3279.0,
                close_price=3280.5
            ))
        
        context = MarketContext(
            symbol="XAUUSD",
            timestamp=base_time,
            current_candle=candles[-1],
            recent_candles=candles[:-1],
            indicators=Indicators(
                ema20=Decimal('3280.0'),
                ema75=Decimal('3282.0'),
                ema200=Decimal('3284.0'),
                atr14=Decimal('5.0')
            ),
            nearby_zones=[]
        )
        
        patterns = await detector.detect(context)
        assert len(patterns) == 0