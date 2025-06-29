"""pytest設定とグローバルフィクスチャ"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any


@pytest.fixture
def sample_candlesticks():
    """サンプルローソク足データ"""
    from src.domain.models.market_data import Candlestick
    
    base_time = datetime(2024, 6, 29, 10, 0, 0, tzinfo=timezone.utc)
    candles = []
    
    # 単純な上昇トレンド
    prices = [
        (3270.0, 3272.0, 3273.0, 3269.0),
        (3272.0, 3274.0, 3275.0, 3271.0),
        (3274.0, 3276.0, 3277.0, 3273.0),
        (3276.0, 3278.0, 3279.0, 3275.0),
        (3278.0, 3280.0, 3281.0, 3277.0),
    ]
    
    for i, (open_p, close_p, high_p, low_p) in enumerate(prices):
        candle = Candlestick(
            symbol="XAUUSD",
            timeframe="1m",
            timestamp=base_time.replace(minute=i),
            open=Decimal(str(open_p)),
            close=Decimal(str(close_p)),
            high=Decimal(str(high_p)),
            low=Decimal(str(low_p)),
            volume=1000 + i * 100
        )
        candles.append(candle)
    
    return candles


@pytest.fixture
def sample_zones():
    """サンプルゾーンデータ"""
    from src.domain.models.zone import Zone, ZoneType, ZoneStatus
    
    zones = [
        Zone(
            id="zone_001",
            symbol="XAUUSD",
            upper_bound=Decimal("3285.00"),
            lower_bound=Decimal("3283.00"),
            zone_type=ZoneType.RESISTANCE,
            strength=0.85,
            touch_count=4,
            status=ZoneStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            last_touched=datetime.now(timezone.utc)
        ),
        Zone(
            id="zone_002",
            symbol="XAUUSD",
            upper_bound=Decimal("3270.00"),
            lower_bound=Decimal("3268.00"),
            zone_type=ZoneType.SUPPORT,
            strength=0.90,
            touch_count=5,
            status=ZoneStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            last_touched=datetime.now(timezone.utc)
        )
    ]
    
    return zones


@pytest.fixture
def sample_market_context():
    """サンプル市場コンテキスト"""
    return {
        "trend": "bullish",
        "strength": 0.75,
        "volatility": "normal",
        "session": "london",
        "major_levels": [
            Decimal("3280.00"),
            Decimal("3275.00"),
            Decimal("3270.00")
        ]
    }


@pytest.fixture
def mock_config():
    """モック設定"""
    return {
        "min_confidence": 70.0,
        "max_risk_pips": 50.0,
        "min_rr_ratio": 1.5,
        "enable_zone_validation": True,
        "enable_trend_filter": True
    }


@pytest.fixture(autouse=True)
def reset_singletons():
    """シングルトンのリセット（テスト間の独立性確保）"""
    # 必要に応じてシングルトンオブジェクトをリセット
    yield
    # クリーンアップ処理


# カバレッジ設定
def pytest_configure(config):
    """pytest設定"""
    config.option.verbose = 1


# テストマーカー
def pytest_collection_modifyitems(config, items):
    """テストマーカーの自動付与"""
    for item in items:
        # ファイルパスに基づいてマーカーを付与
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)