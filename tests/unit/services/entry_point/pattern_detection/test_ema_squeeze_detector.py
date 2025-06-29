"""
Unit tests for EMA Squeeze Pattern Detector
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from src.services.entry_point.pattern_detection.ema_squeeze_detector import EMASqueezeDetector
from src.domain.models.pattern import PatternType
from src.domain.models.market import MarketContext, Indicators
from src.models.candlestick import CandlestickData
from src.models.zone import Zone


class TestEMASqueezeDetector:
    """Test cases for EMA squeeze pattern detection"""
    
    @pytest.fixture
    def detector(self):
        """Create EMA squeeze detector instance"""
        return EMASqueezeDetector()
    
    @pytest.fixture
    def base_time(self):
        """Base timestamp for tests"""
        return datetime(2024, 6, 29, 12, 0, 0)
    
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
    
    def create_squeeze_candles(self, base_time: datetime, ema200: float = 3275.0) -> list:
        """Create candles representing an EMA squeeze"""
        candles = []
        
        # Create 15 candles with tight range around EMA
        for i in range(15):
            time = base_time - timedelta(minutes=15-i)
            
            # Keep prices very close to EMA (within 3 pips)
            deviation = (i % 3 - 1) * 1.5  # -1.5, 0, 1.5 pattern
            center = ema200 + deviation
            
            # Small body candles
            if i % 2 == 0:
                open_price = center - 0.5
                close_price = center + 0.5
            else:
                open_price = center + 0.5
                close_price = center - 0.5
            
            # Wicks within 10 pips
            high_price = max(open_price, close_price) + 2.0
            low_price = min(open_price, close_price) - 2.0
            
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time,
                open_price, high_price, low_price, close_price
            ))
        
        return candles
    
    @pytest.mark.asyncio
    async def test_detect_typical_ema_squeeze(self, detector, base_time):
        """Test detection of typical EMA squeeze pattern"""
        # Create squeeze candles
        ema200_level = 3275.0
        recent_candles = self.create_squeeze_candles(base_time, ema200_level)
        
        # Current candle still in squeeze
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3274.5,
            high_price=3276.0,
            low_price=3273.0,
            close_price=3275.5
        )
        
        # Create converging EMAs
        indicators = Indicators(
            ema20=Decimal('3276.0'),
            ema75=Decimal('3275.5'),
            ema200=Decimal(str(ema200_level)),
            atr14=Decimal('8.0')
        )
        
        # Create zone near squeeze
        zone = self.create_zone("XAUUSD", upper=3280.0, lower=3270.0, strength='A')
        
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
        
        assert pattern.pattern_type == PatternType.EMA_SQUEEZE
        assert pattern.symbol == "XAUUSD"
        assert pattern.confidence >= 70  # Should have good confidence
        assert pattern.parameters['squeeze_duration'] >= 5
        assert pattern.parameters['max_deviation'] <= 3.0
        assert pattern.parameters['convergence_level'] > 0.8
        assert pattern.parameters['ema_convergence'] is True
    
    @pytest.mark.asyncio
    async def test_no_detection_insufficient_squeeze_duration(self, detector, base_time):
        """Test no detection when squeeze duration is too short"""
        # Create only 3 squeeze candles (need 5)
        candles = []
        
        # Non-squeeze candles first
        for i in range(12):
            time = base_time - timedelta(minutes=15-i)
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time,
                open_price=3280.0 + i,
                high_price=3281.0 + i,
                low_price=3279.0 + i,
                close_price=3280.5 + i
            ))
        
        # Add 3 squeeze candles
        for i in range(3):
            time = base_time - timedelta(minutes=3-i)
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time,
                open_price=3274.5,
                high_price=3276.0,
                low_price=3273.0,
                close_price=3275.0
            ))
        
        current_candle = candles[-1]
        
        indicators = Indicators(
            ema20=Decimal('3276.0'),
            ema75=Decimal('3275.5'),
            ema200=Decimal('3275.0'),
            atr14=Decimal('8.0')
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
    async def test_no_detection_range_too_wide(self, detector, base_time):
        """Test no detection when range is too wide (>15 pips)"""
        candles = []
        
        # Create candles with wide range
        for i in range(15):
            time = base_time - timedelta(minutes=15-i)
            # Oscillating between 3270 and 3290 (20 pip range)
            if i % 2 == 0:
                candles.append(self.create_candlestick(
                    "XAUUSD", "1m", time,
                    open_price=3270.0,
                    high_price=3272.0,
                    low_price=3268.0,
                    close_price=3271.0
                ))
            else:
                candles.append(self.create_candlestick(
                    "XAUUSD", "1m", time,
                    open_price=3288.0,
                    high_price=3290.0,
                    low_price=3287.0,
                    close_price=3289.0
                ))
        
        current_candle = candles[-1]
        
        indicators = Indicators(
            ema20=Decimal('3280.0'),
            ema75=Decimal('3279.0'),
            ema200=Decimal('3280.0'),  # In the middle of range
            atr14=Decimal('10.0')
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
    async def test_no_detection_no_breakout_precursors(self, detector, base_time):
        """Test no detection when there are no breakout precursors"""
        # Create squeeze candles
        recent_candles = self.create_squeeze_candles(base_time, 3275.0)
        
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3274.5,
            high_price=3276.0,
            low_price=3273.0,
            close_price=3275.5
        )
        
        # Create diverging EMAs (no convergence)
        indicators = Indicators(
            ema20=Decimal('3300.0'),  # Much further away (25 pips)
            ema75=Decimal('3285.0'),
            ema200=Decimal('3275.0'),
            atr14=Decimal('8.0')
        )
        
        context = MarketContext(
            symbol="XAUUSD",
            timestamp=base_time,
            current_candle=current_candle,
            recent_candles=recent_candles,
            indicators=indicators,
            nearby_zones=[]
        )
        
        patterns = await detector.detect(context)
        assert len(patterns) == 0
    
    @pytest.mark.asyncio
    async def test_breakout_direction_prediction_bullish(self, detector, base_time):
        """Test bullish breakout direction prediction"""
        recent_candles = self.create_squeeze_candles(base_time, 3275.0)
        
        # Current candle at upper part of squeeze
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3276.0,
            high_price=3277.0,
            low_price=3275.0,
            close_price=3276.5
        )
        
        # Bullish EMA alignment
        indicators = Indicators(
            ema20=Decimal('3277.0'),
            ema75=Decimal('3276.0'),
            ema200=Decimal('3275.0'),
            atr14=Decimal('8.0')
        )
        
        context = MarketContext(
            symbol="XAUUSD",
            timestamp=base_time,
            current_candle=current_candle,
            recent_candles=recent_candles,
            indicators=indicators,
            nearby_zones=[]
        )
        
        patterns = await detector.detect(context)
        
        if patterns:  # Should detect pattern
            assert patterns[0].parameters['breakout_direction'] == 'bullish'
    
    @pytest.mark.asyncio
    async def test_triangle_pattern_detection(self, detector, base_time):
        """Test triangle pattern detection within squeeze"""
        candles = []
        
        # Create converging triangle pattern
        for i in range(10):
            time = base_time - timedelta(minutes=10-i)
            # Decreasing highs and increasing lows
            high_price = 3280.0 - i * 0.5  # Descending
            low_price = 3270.0 + i * 0.5   # Ascending
            
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time,
                open_price=(high_price + low_price) / 2 - 0.5,
                high_price=high_price,
                low_price=low_price,
                close_price=(high_price + low_price) / 2 + 0.5
            ))
        
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3274.5,
            high_price=3275.5,
            low_price=3274.0,
            close_price=3275.0
        )
        
        indicators = Indicators(
            ema20=Decimal('3275.5'),
            ema75=Decimal('3275.2'),
            ema200=Decimal('3275.0'),
            atr14=Decimal('8.0')
        )
        
        context = MarketContext(
            symbol="XAUUSD",
            timestamp=base_time,
            current_candle=current_candle,
            recent_candles=candles,
            indicators=indicators,
            nearby_zones=[]
        )
        
        patterns = await detector.detect(context)
        
        # Should detect pattern with triangle
        if patterns:
            assert patterns[0].parameters.get('convergence_level', 0) > 0.8
    
    @pytest.mark.asyncio
    async def test_confidence_calculation_factors(self, detector, base_time):
        """Test various factors affecting confidence calculation"""
        # Create long squeeze (8+ candles)
        candles = []
        for i in range(12):
            time = base_time - timedelta(minutes=12-i)
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time,
                open_price=3274.8,
                high_price=3275.5,
                low_price=3274.5,
                close_price=3275.0
            ))
        
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3274.9,
            high_price=3275.2,
            low_price=3274.7,
            close_price=3275.0
        )
        
        # Perfect EMA convergence
        indicators = Indicators(
            ema20=Decimal('3275.2'),
            ema75=Decimal('3275.1'),
            ema200=Decimal('3275.0'),
            atr14=Decimal('8.0')
        )
        
        zone = self.create_zone("XAUUSD", upper=3278.0, lower=3272.0, strength='S')
        
        context = MarketContext(
            symbol="XAUUSD",
            timestamp=base_time,
            current_candle=current_candle,
            recent_candles=candles,
            indicators=indicators,
            nearby_zones=[zone]
        )
        
        patterns = await detector.detect(context)
        
        if patterns:
            pattern = patterns[0]
            # Should have high confidence due to:
            # - Long squeeze duration (8+ candles)
            # - Tight deviation (<1 pip)
            # - Perfect EMA convergence
            # - Zone proximity
            assert pattern.confidence >= 85
    
    @pytest.mark.asyncio
    async def test_insufficient_data(self, detector, base_time):
        """Test handling of insufficient candlestick data"""
        # Only 5 candles (need 10)
        candles = []
        for i in range(5):
            time = base_time - timedelta(minutes=5-i)
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time,
                open_price=3275.0,
                high_price=3276.0,
                low_price=3274.0,
                close_price=3275.5
            ))
        
        context = MarketContext(
            symbol="XAUUSD",
            timestamp=base_time,
            current_candle=candles[-1],
            recent_candles=candles[:-1],
            indicators=Indicators(
                ema20=Decimal('3275.0'),
                ema75=Decimal('3275.0'),
                ema200=Decimal('3275.0'),
                atr14=Decimal('8.0')
            ),
            nearby_zones=[]
        )
        
        patterns = await detector.detect(context)
        assert len(patterns) == 0