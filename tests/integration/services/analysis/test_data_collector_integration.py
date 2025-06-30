"""
データコレクターの結合テスト
"""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.services.analysis.data_collector import AnalysisDataCollector
from src.models.forex import ForexRate
from src.models.candlestick import CandlestickData
from src.models.technical_indicator import TechnicalIndicator
from src.models.entry_signal import EntrySignal
from src.models.base import Base


@pytest.fixture
async def test_db():
    """テスト用データベース"""
    # SQLiteメモリDBを使用
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        
    await engine.dispose()


@pytest.fixture
async def setup_test_data(test_db):
    """テストデータのセットアップ"""
    now = datetime.now(timezone.utc)
    
    # ForexRateデータ
    for i in range(100):
        rate = ForexRate(
            currency_pair="XAUUSD",
            bid=3250.00 + (i % 10) - 5,
            ask=3250.50 + (i % 10) - 5,
            timestamp=now - timedelta(minutes=i)
        )
        test_db.add(rate)
    
    # CandlestickData
    for tf in ["1m", "5m", "15m", "1h", "4h"]:
        for i in range(10):
            candle = CandlestickData(
                symbol="XAUUSD",
                timeframe=tf,
                open_time=now - timedelta(minutes=i),
                close_time=now - timedelta(minutes=i-1),
                open_price=3250.00,
                high_price=3252.00,
                low_price=3248.00,
                close_price=3251.00,
                tick_count=100
            )
            test_db.add(candle)
    
    # TechnicalIndicator
    for tf in ["1h", "4h"]:
        indicator = TechnicalIndicator(
            symbol="XAUUSD",
            timeframe=tf,
            timestamp=now,
            ema_5=3250.00,
            ema_10=3248.00,
            ema_15=3247.00,
            ema_20=3246.00,
            ema_50=3245.00,
            ema_100=3244.00,
            ema_200=3243.00,
            rsi_14=65.5,
            macd=2.5,
            macd_signal=2.0,
            macd_histogram=0.5,
            bb_upper=3260.00,
            bb_middle=3250.00,
            bb_lower=3240.00,
            atr_14=10.0,
            stoch_k=75.0,
            stoch_d=70.0
        )
        test_db.add(indicator)
    
    # EntrySignal
    signal = EntrySignal(
        symbol="XAUUSD",
        signal_type="BUY",
        pattern_type="v_shape_reversal",
        timeframe="15m",
        entry_price=3250.00,
        stop_loss=3240.00,
        take_profit=3270.00,
        confidence_score=0.85,
        status="active",
        created_at=now - timedelta(hours=1),
        signal_metadata={"reason": "Strong reversal pattern"}
    )
    test_db.add(signal)
    
    await test_db.commit()


class TestAnalysisDataCollectorIntegration:
    """データコレクターの結合テスト"""
    
    @pytest.mark.asyncio
    async def test_collect_market_data_with_real_db(self, test_db, setup_test_data):
        """実際のDBを使用した市場データ収集テスト"""
        collector = AnalysisDataCollector(test_db)
        
        result = await collector.collect_market_data("XAUUSD")
        
        assert "current_price" in result
        assert result["current_price"] > 0
        assert "24h_high" in result
        assert "24h_low" in result
        assert "volatility" in result
        assert result["tick_count"] > 0
    
    @pytest.mark.asyncio
    async def test_collect_candlestick_data_with_real_db(self, test_db, setup_test_data):
        """実際のDBを使用したローソク足データ収集テスト"""
        collector = AnalysisDataCollector(test_db)
        
        result = await collector.collect_candlestick_data("XAUUSD")
        
        assert "1m" in result
        assert "5m" in result
        assert "1h" in result
        assert len(result["1m"]) > 0
        assert result["1m"][0]["open"] == 3250.00
        assert result["1m"][0]["volume"] == 100
    
    @pytest.mark.asyncio
    async def test_collect_technical_indicators_with_real_db(self, test_db, setup_test_data):
        """実際のDBを使用した技術指標収集テスト"""
        collector = AnalysisDataCollector(test_db)
        
        result = await collector.collect_technical_indicators("XAUUSD")
        
        assert "1h" in result
        assert result["1h"]["rsi"] == 65.5
        assert result["1h"]["ema_5"] == 3250.00
    
    @pytest.mark.asyncio
    async def test_collect_signal_history_with_real_db(self, test_db, setup_test_data):
        """実際のDBを使用したシグナル履歴収集テスト"""
        collector = AnalysisDataCollector(test_db)
        
        result = await collector.collect_signal_history("XAUUSD")
        
        assert len(result) == 1
        assert result[0]["signal_type"] == "BUY"
        assert result[0]["pattern_type"] == "v_shape_reversal"
        assert result[0]["metadata"]["reason"] == "Strong reversal pattern"
    
    @pytest.mark.asyncio
    async def test_collect_all_data_integration(self, test_db, setup_test_data):
        """全データ収集の統合テスト"""
        collector = AnalysisDataCollector(test_db)
        
        result = await collector.collect_all_data("XAUUSD")
        
        # 全セクションが存在することを確認
        assert result["symbol"] == "XAUUSD"
        assert "timestamp" in result
        assert "market_data" in result
        assert "candlesticks" in result
        assert "indicators" in result
        assert "signals" in result
        
        # 各セクションにデータが入っていることを確認
        assert result["market_data"]["current_price"] > 0
        assert len(result["candlesticks"]["1m"]) > 0
        assert "1h" in result["indicators"]
        assert len(result["signals"]) == 1
    
    @pytest.mark.asyncio
    async def test_collect_data_no_data_scenario(self, test_db):
        """データがない場合の動作確認"""
        collector = AnalysisDataCollector(test_db)
        
        result = await collector.collect_all_data("EURUSD")  # 存在しない通貨ペア
        
        assert result["symbol"] == "EURUSD"
        assert result["market_data"] == {}
        assert result["candlesticks"] == {}
        assert result["indicators"] == {}
        assert result["signals"] == []
    
    @pytest.mark.asyncio
    async def test_performance_collect_all_data(self, test_db, setup_test_data):
        """パフォーマンステスト - 60秒以内に完了すること"""
        import time
        
        collector = AnalysisDataCollector(test_db)
        
        start_time = time.time()
        result = await collector.collect_all_data("XAUUSD")
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        assert execution_time < 60  # 60秒以内
        assert result["market_data"]["current_price"] > 0  # データが取得できている