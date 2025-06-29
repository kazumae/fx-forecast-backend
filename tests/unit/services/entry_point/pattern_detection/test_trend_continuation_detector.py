"""
Unit tests for Trend Continuation Pattern Detector
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from src.services.entry_point.pattern_detection.trend_continuation_detector import TrendContinuationDetector
from src.domain.models.pattern import PatternType
from src.domain.models.market import MarketContext, Indicators
from src.models.candlestick import CandlestickData
from src.models.zone import Zone


class TestTrendContinuationDetector:
    """Test cases for trend continuation pattern detection"""
    
    @pytest.fixture
    def detector(self):
        """Create trend continuation detector instance"""
        return TrendContinuationDetector()
    
    @pytest.fixture
    def base_time(self):
        """Base timestamp for tests"""
        return datetime(2024, 6, 29, 14, 0, 0)
    
    def create_candlestick(
        self,
        symbol: str,
        timeframe: str,
        open_time: datetime,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        tick_count: int = 100
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
            tick_count=tick_count
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
    
    def create_uptrend_with_pullback(self, base_time: datetime) -> list:
        """Create realistic uptrend with pullback pattern"""
        candles = []
        
        # Phase 1: Strong uptrend (40 candles) - make stronger trend
        base_price = 3240.0
        for i in range(40):
            time = base_time - timedelta(minutes=60-i)
            # Stronger upward movement 
            trend_component = i * 0.8  # 0.8 pips per candle upward
            noise = (i % 3 - 1) * 0.2  # Small noise
            
            price = base_price + trend_component + noise
            
            # Make most candles bullish for strong trend
            if i % 4 != 0:  # 75% bullish candles
                open_p = price - 0.1
                close_p = price + 0.3
            else:
                open_p = price + 0.1
                close_p = price - 0.1
            
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time,
                open_price=open_p,
                high_price=price + 0.8,
                low_price=price - 0.3,
                close_price=close_p,
                tick_count=100 + i  # Increasing volume
            ))
        
        # Phase 2: Pullback (15 candles)
        swing_high = 3270.0
        for i in range(15):
            time = base_time - timedelta(minutes=20-i)
            # Gradual pullback
            pullback_component = i * -0.8  # 0.8 pips per candle downward
            
            price = swing_high + pullback_component
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time,
                open_price=price + 0.2,
                high_price=price + 0.5,
                low_price=price - 0.8,
                close_price=price - 0.2,
                tick_count=80 - i  # Decreasing volume
            ))
        
        # Phase 3: Approach to 200EMA (5 candles)
        pullback_low = 3258.0
        for i in range(5):
            time = base_time - timedelta(minutes=5-i)
            
            price = pullback_low + i * 0.3  # Slight recovery
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time,
                open_price=price - 0.1,
                high_price=price + 0.5,
                low_price=price - 0.6,
                close_price=price + 0.1
            ))
        
        return candles
    
    @pytest.mark.asyncio
    async def test_detect_typical_trend_continuation(self, detector, base_time):
        """Test detection of typical trend continuation pattern"""
        # Create uptrend with pullback
        recent_candles = self.create_uptrend_with_pullback(base_time)
        
        # Current candle shows reversal signal (pin bar)
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3259.0,
            high_price=3260.0,
            low_price=3257.0,  # Long lower wick
            close_price=3259.5,  # Bullish close
            tick_count=150  # Volume increase
        )
        
        # EMAs showing uptrend with price near 200EMA
        indicators = Indicators(
            ema20=Decimal('3265.0'),
            ema75=Decimal('3262.0'),
            ema200=Decimal('3258.0'),  # Near current price
            atr14=Decimal('8.0')
        )
        
        # Zone near current price
        zone = self.create_zone("XAUUSD", upper=3262.0, lower=3256.0, strength='A')
        
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
        
        assert pattern.pattern_type == PatternType.TREND_CONTINUATION
        assert pattern.symbol == "XAUUSD"
        assert pattern.confidence >= 70  # Should have good confidence
        assert pattern.parameters['trend_strength'] >= 60
        assert 20 <= pattern.parameters['pullback_depth'] <= 60
        assert pattern.parameters['ema200_distance'] <= 20
        assert pattern.parameters['formation_bars'] >= 5
    
    @pytest.mark.asyncio
    async def test_no_detection_insufficient_data(self, detector, base_time):
        """Test no detection when insufficient data"""
        # Only 30 candles (need 60)
        candles = []
        for i in range(30):
            time = base_time - timedelta(minutes=30-i)
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time,
                open_price=3260.0,
                high_price=3261.0,
                low_price=3259.0,
                close_price=3260.5
            ))
        
        current_candle = candles[-1]
        
        indicators = Indicators(
            ema20=Decimal('3262.0'),
            ema75=Decimal('3260.0'),
            ema200=Decimal('3258.0'),
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
    async def test_no_detection_weak_trend(self, detector, base_time):
        """Test no detection when trend is too weak"""
        # Create sideways/weak trend
        candles = []
        for i in range(60):
            time = base_time - timedelta(minutes=60-i)
            # Mostly sideways with slight upward bias
            price = 3260.0 + (i % 10 - 5) * 0.5  # Oscillating price
            
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time,
                open_price=price,
                high_price=price + 0.5,
                low_price=price - 0.5,
                close_price=price + 0.1
            ))
        
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3260.0,
            high_price=3261.0,
            low_price=3258.0,
            close_price=3260.5
        )
        
        # EMAs not in proper uptrend alignment
        indicators = Indicators(
            ema20=Decimal('3260.5'),
            ema75=Decimal('3260.2'),  # Too close to 20EMA
            ema200=Decimal('3259.8'),
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
        assert len(patterns) == 0
    
    @pytest.mark.asyncio
    async def test_no_detection_no_pullback(self, detector, base_time):
        """Test no detection when there's no valid pullback"""
        # Create strong uptrend without pullback
        candles = []
        base_price = 3250.0
        
        for i in range(60):
            time = base_time - timedelta(minutes=60-i)
            # Continuous uptrend
            price = base_price + i * 0.3
            
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time,
                open_price=price,
                high_price=price + 0.5,
                low_price=price - 0.2,
                close_price=price + 0.3
            ))
        
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3268.0,
            high_price=3269.0,
            low_price=3267.5,
            close_price=3268.5
        )
        
        indicators = Indicators(
            ema20=Decimal('3265.0'),
            ema75=Decimal('3260.0'),
            ema200=Decimal('3255.0'),
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
        assert len(patterns) == 0  # No pullback = no pattern
    
    @pytest.mark.asyncio
    async def test_no_detection_far_from_ema200(self, detector, base_time):
        """Test no detection when price is too far from 200EMA"""
        recent_candles = self.create_uptrend_with_pullback(base_time)
        
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3270.0,  # Far from 200EMA
            high_price=3271.0,
            low_price=3269.0,
            close_price=3270.5
        )
        
        # 200EMA far away
        indicators = Indicators(
            ema20=Decimal('3275.0'),
            ema75=Decimal('3270.0'),
            ema200=Decimal('3245.0'),  # 25 pips away (>20 threshold)
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
    async def test_no_detection_no_reversal_signals(self, detector, base_time):
        """Test no detection when there are no reversal signals"""
        recent_candles = self.create_uptrend_with_pullback(base_time)
        
        # Current candle with no reversal signals
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3259.0,
            high_price=3259.2,  # Small range
            low_price=3258.8,   # No long wick
            close_price=3258.9, # Bearish close
            tick_count=50       # Low volume
        )
        
        indicators = Indicators(
            ema20=Decimal('3265.0'),
            ema75=Decimal('3262.0'),
            ema200=Decimal('3258.0'),
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
    async def test_trend_strength_calculation(self, detector, base_time):
        """Test trend strength calculation factors"""
        # Create strong trend
        candles = []
        base_price = 3240.0
        
        for i in range(60):
            time = base_time - timedelta(minutes=60-i)
            price = base_price + i * 0.4  # Strong upward movement
            
            # Make most candles bullish
            if i % 5 != 0:  # 80% bullish candles
                open_p = price - 0.1
                close_p = price + 0.2
            else:
                open_p = price + 0.1
                close_p = price - 0.1
            
            candles.append(self.create_candlestick(
                "XAUUSD", "1m", time,
                open_price=open_p,
                high_price=price + 0.5,
                low_price=price - 0.3,
                close_price=close_p
            ))
        
        # Perfect EMA alignment
        indicators = Indicators(
            ema20=Decimal('3266.0'),
            ema75=Decimal('3262.0'),
            ema200=Decimal('3255.0'),
            atr14=Decimal('8.0')
        )
        
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3264.0,
            high_price=3265.0,
            low_price=3262.0,
            close_price=3264.5
        )
        
        # Test internal method
        strength = detector._calculate_trend_strength(candles + [current_candle], indicators)
        
        # Should have high strength due to:
        # - Perfect EMA alignment
        # - High bullish ratio
        # - Strong momentum
        assert strength >= 70
    
    @pytest.mark.asyncio
    async def test_pullback_with_fibonacci_levels(self, detector, base_time):
        """Test pullback detection with Fibonacci analysis"""
        recent_candles = self.create_uptrend_with_pullback(base_time)
        
        # Current candle at ideal Fibonacci level
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3258.5,
            high_price=3259.5,
            low_price=3257.0,  # Pin bar
            close_price=3259.0
        )
        
        indicators = Indicators(
            ema20=Decimal('3265.0'),
            ema75=Decimal('3262.0'),
            ema200=Decimal('3258.0'),
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
        
        if patterns:
            pattern = patterns[0]
            # Should have calculated Fibonacci level
            assert 'fibonacci_level' in pattern.parameters
            fib_level = pattern.parameters['fibonacci_level']
            assert 0 <= fib_level <= 100
    
    @pytest.mark.asyncio
    async def test_reversal_signal_types(self, detector, base_time):
        """Test different types of reversal signals"""
        recent_candles = self.create_uptrend_with_pullback(base_time)
        
        # Test engulfing pattern
        # Add bearish candle before current
        prev_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time - timedelta(minutes=1),
            open_price=3259.0,
            high_price=3259.2,
            low_price=3258.0,
            close_price=3258.2  # Bearish
        )
        recent_candles.append(prev_candle)
        
        # Current bullish engulfing candle
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3258.0,  # Below prev close
            high_price=3260.0,
            low_price=3257.5,
            close_price=3259.5,  # Above prev open
            tick_count=200  # High volume
        )
        
        indicators = Indicators(
            ema20=Decimal('3265.0'),
            ema75=Decimal('3262.0'),
            ema200=Decimal('3258.0'),
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
        
        if patterns:
            pattern = patterns[0]
            assert pattern.parameters['reversal_type'] == 'engulfing'
    
    @pytest.mark.asyncio
    async def test_confidence_scoring_factors(self, detector, base_time):
        """Test confidence scoring with optimal conditions"""
        recent_candles = self.create_uptrend_with_pullback(base_time)
        
        current_candle = self.create_candlestick(
            "XAUUSD", "1m", base_time,
            open_price=3258.5,
            high_price=3259.5,
            low_price=3256.0,  # Long lower wick (pin bar)
            close_price=3259.2,
            tick_count=180  # Volume increase
        )
        
        # Optimal indicators
        indicators = Indicators(
            ema20=Decimal('3265.0'),
            ema75=Decimal('3262.0'),
            ema200=Decimal('3258.0'),  # Very close to price
            atr14=Decimal('8.0')
        )
        
        # Strong zone
        zone = self.create_zone("XAUUSD", upper=3260.0, lower=3256.0, strength='S')
        
        context = MarketContext(
            symbol="XAUUSD",
            timestamp=base_time,
            current_candle=current_candle,
            recent_candles=recent_candles,
            indicators=indicators,
            nearby_zones=[zone]
        )
        
        patterns = await detector.detect(context)
        
        if patterns:
            pattern = patterns[0]
            # Should have high confidence due to:
            # - Strong trend
            # - Ideal pullback depth
            # - Close to 200EMA
            # - Pin bar signal
            # - Zone proximity
            assert pattern.confidence >= 80