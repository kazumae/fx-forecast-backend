"""
データコレクターの単体テスト
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.analysis.data_collector import AnalysisDataCollector
from src.models.forex import ForexRate
from src.models.candlestick import CandlestickData
from src.models.technical_indicator import TechnicalIndicator
from src.models.entry_signal import EntrySignal


@pytest.fixture
def mock_db_session():
    """モックDBセッション"""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def collector(mock_db_session):
    """データコレクターのフィクスチャ"""
    return AnalysisDataCollector(mock_db_session)


class TestAnalysisDataCollector:
    """AnalysisDataCollectorのテスト"""
    
    @pytest.mark.asyncio
    async def test_collect_market_data_success(self, collector, mock_db_session):
        """市場データ収集の正常系テスト"""
        # モックデータ準備
        current_rate = ForexRate(
            currency_pair="XAUUSD",
            bid=3250.50,
            ask=3251.00,
            timestamp=datetime.now(timezone.utc)
        )
        
        ago_rate = ForexRate(
            currency_pair="XAUUSD",
            bid=3240.00,
            ask=3240.50,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=24)
        )
        
        # モックの設定
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = current_rate
        mock_db_session.execute.return_value = mock_result
        
        # 統計データのモック
        stats_mock = MagicMock()
        stats_mock.one.return_value = MagicMock(
            high_bid=3260.00,
            low_bid=3230.00,
            avg_bid=3245.00,
            stddev_bid=15.00,
            tick_count=1000
        )
        
        # execute呼び出しごとに異なる結果を返す
        mock_db_session.execute.side_effect = [
            mock_result,  # current_price_query
            stats_mock,   # stats_query
            MagicMock(scalar_one_or_none=MagicMock(return_value=ago_rate))  # ago_price_query
        ]
        
        # テスト実行
        result = await collector.collect_market_data("XAUUSD")
        
        # 検証
        assert result["current_price"] == 3250.75  # (bid + ask) / 2
        assert result["bid"] == 3250.50
        assert result["ask"] == 3251.00
        assert result["spread"] == 0.50
        assert result["24h_high"] == 3260.00
        assert result["24h_low"] == 3230.00
        assert result["tick_count"] == 1000
        assert "volatility" in result
        assert "24h_change" in result
    
    @pytest.mark.asyncio
    async def test_collect_market_data_no_data(self, collector, mock_db_session):
        """データがない場合のテスト"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        result = await collector.collect_market_data("XAUUSD")
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_collect_candlestick_data_success(self, collector, mock_db_session):
        """ローソク足データ収集の正常系テスト"""
        # モックデータ
        candle = CandlestickData(
            symbol="XAUUSD",
            timeframe="1m",
            open_time=datetime.now(timezone.utc),
            close_time=datetime.now(timezone.utc),
            open_price=3250.00,
            high_price=3252.00,
            low_price=3249.00,
            close_price=3251.00,
            tick_count=100
        )
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [candle]
        mock_db_session.execute.return_value = mock_result
        
        result = await collector.collect_candlestick_data("XAUUSD")
        
        assert "1m" in result
        assert len(result["1m"]) == 1
        assert result["1m"][0]["open"] == 3250.00
        assert result["1m"][0]["close"] == 3251.00
        assert result["1m"][0]["volume"] == 100
    
    @pytest.mark.asyncio
    async def test_collect_technical_indicators_success(self, collector, mock_db_session):
        """技術指標データ収集の正常系テスト"""
        # モックデータ
        indicator = TechnicalIndicator(
            symbol="XAUUSD",
            timeframe="1h",
            timestamp=datetime.now(timezone.utc),
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
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [indicator]
        mock_db_session.execute.return_value = mock_result
        
        result = await collector.collect_technical_indicators("XAUUSD")
        
        assert "1h" in result
        assert result["1h"]["rsi"] == 65.5
        assert result["1h"]["ema_5"] == 3250.00
    
    @pytest.mark.asyncio
    async def test_collect_signal_history_success(self, collector, mock_db_session):
        """シグナル履歴収集の正常系テスト"""
        # モックデータ
        signal = EntrySignal(
            id=1,
            symbol="XAUUSD",
            signal_type="BUY",
            pattern_type="v_shape_reversal",
            timeframe="15m",
            entry_price=3250.00,
            stop_loss=3240.00,
            take_profit=3270.00,
            confidence_score=0.85,
            status="active",
            created_at=datetime.now(timezone.utc),
            signal_metadata={}
        )
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [signal]
        mock_db_session.execute.return_value = mock_result
        
        result = await collector.collect_signal_history("XAUUSD")
        
        assert len(result) == 1
        assert result[0]["signal_type"] == "BUY"
        assert result[0]["entry_price"] == 3250.00
        assert result[0]["confidence_score"] == 0.85
    
    @pytest.mark.asyncio
    async def test_collect_all_data_success(self, collector, mock_db_session):
        """全データ収集の正常系テスト"""
        # 各メソッドをモック
        with patch.object(collector, 'collect_market_data', return_value={"current_price": 3250.00}):
            with patch.object(collector, 'collect_candlestick_data', return_value={"1m": []}):
                with patch.object(collector, 'collect_technical_indicators', return_value={"1h": {}}):
                    with patch.object(collector, 'collect_signal_history', return_value=[]):
                        
                        result = await collector.collect_all_data("XAUUSD")
                        
                        assert result["symbol"] == "XAUUSD"
                        assert "timestamp" in result
                        assert result["market_data"]["current_price"] == 3250.00
                        assert "candlesticks" in result
                        assert "indicators" in result
                        assert "signals" in result
    
    @pytest.mark.asyncio
    async def test_collect_all_data_partial_failure(self, collector, mock_db_session):
        """一部のデータ収集が失敗した場合のテスト"""
        # market_dataは成功、他は失敗
        with patch.object(collector, 'collect_market_data', return_value={"current_price": 3250.00}):
            with patch.object(collector, 'collect_candlestick_data', side_effect=Exception("DB Error")):
                with patch.object(collector, 'collect_technical_indicators', return_value={"1h": {}}):
                    with patch.object(collector, 'collect_signal_history', return_value=[]):
                        
                        result = await collector.collect_all_data("XAUUSD")
                        
                        # market_dataは正常
                        assert result["market_data"]["current_price"] == 3250.00
                        # candlesticksは空
                        assert result["candlesticks"] == {}
                        # indicatorsは正常
                        assert "1h" in result["indicators"]
    
    @pytest.mark.asyncio
    async def test_calculate_volatility_success(self, collector, mock_db_session):
        """ボラティリティ計算の正常系テスト"""
        stats_mock = MagicMock()
        stats_mock.one.return_value = MagicMock(
            price_stddev=15.0,
            price_avg=3250.0
        )
        mock_db_session.execute.return_value = stats_mock
        
        result = await collector.calculate_volatility("XAUUSD")
        
        assert result == pytest.approx(15.0 / 3250.0, rel=1e-6)
    
    @pytest.mark.asyncio
    async def test_calculate_volatility_no_data(self, collector, mock_db_session):
        """データがない場合のボラティリティ計算"""
        stats_mock = MagicMock()
        stats_mock.one.return_value = MagicMock(
            price_stddev=None,
            price_avg=None
        )
        mock_db_session.execute.return_value = stats_mock
        
        result = await collector.calculate_volatility("XAUUSD")
        assert result == 0.0