"""
Redis クライアント設定とデータ構造管理
リアルタイムデータのキャッシュとAI解析用の高速データ取得
"""

import json
from redis import Redis, ConnectionError
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class TickData:
    """ティックデータ構造"""
    symbol: str
    timestamp: datetime
    bid: Decimal
    ask: Decimal
    spread: Decimal
    source: str = "tradermade"


@dataclass
class CandlestickData:
    """ローソク足データ構造"""
    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    tick_count: int = 0


@dataclass
class TechnicalIndicator:
    """技術指標データ構造"""
    symbol: str
    timeframe: str
    timestamp: datetime
    indicator_type: str
    value: Decimal
    metadata: Optional[Dict] = None


class RedisClient:
    """Redis クライアント - 高速データキャッシュ"""
    
    def __init__(self, host: str = "localhost", port: int = 6379, 
                 password: Optional[str] = None, db: int = 0):
        """Redis接続初期化"""
        self.redis_client = Redis(
            host=host,
            port=port,
            password=password,
            db=db,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        
        # 接続テスト
        try:
            self.redis_client.ping()
            logger.info(f"Redis接続成功: {host}:{port}")
        except ConnectionError as e:
            logger.error(f"Redis接続失敗: {e}")
            raise

    def _serialize_decimal(self, obj: Any) -> Any:
        """Decimal型をJSON対応形式に変換"""
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    def _json_encode(self, data: Any) -> str:
        """データをJSON文字列に変換"""
        return json.dumps(data, default=self._serialize_decimal)

    def _json_decode(self, data: str) -> Any:
        """JSON文字列をデータに変換"""
        return json.loads(data)

    # ===== ティックデータ管理 =====
    
    def set_latest_tick(self, tick_data: TickData) -> None:
        """最新ティックデータを保存"""
        key = f"tick:{tick_data.symbol}:latest"
        data = asdict(tick_data)
        self.redis_client.set(key, self._json_encode(data), ex=300)  # 5分で期限切れ
        logger.debug(f"最新ティックデータ保存: {key}")

    def get_latest_tick(self, symbol: str) -> Optional[TickData]:
        """最新ティックデータを取得"""
        key = f"tick:{symbol}:latest"
        data = self.redis_client.get(key)
        if data:
            parsed = self._json_decode(data)
            return TickData(
                symbol=parsed['symbol'],
                timestamp=datetime.fromisoformat(parsed['timestamp']),
                bid=Decimal(str(parsed['bid'])),
                ask=Decimal(str(parsed['ask'])),
                spread=Decimal(str(parsed['spread'])),
                source=parsed['source']
            )
        return None

    # ===== ローソク足データ管理 =====
    
    def set_latest_candlestick(self, candle_data: CandlestickData) -> None:
        """最新ローソク足データを保存"""
        key = f"candle:{candle_data.symbol}:{candle_data.timeframe}:latest"
        data = asdict(candle_data)
        self.redis_client.set(key, self._json_encode(data), ex=3600)  # 1時間で期限切れ
        logger.debug(f"最新ローソク足保存: {key}")

    def get_latest_candlestick(self, symbol: str, timeframe: str) -> Optional[CandlestickData]:
        """最新ローソク足データを取得"""
        key = f"candle:{symbol}:{timeframe}:latest"
        data = self.redis_client.get(key)
        if data:
            parsed = self._json_decode(data)
            return CandlestickData(
                symbol=parsed['symbol'],
                timeframe=parsed['timeframe'],
                open_time=datetime.fromisoformat(parsed['open_time']),
                close_time=datetime.fromisoformat(parsed['close_time']),
                open_price=Decimal(str(parsed['open_price'])),
                high_price=Decimal(str(parsed['high_price'])),
                low_price=Decimal(str(parsed['low_price'])),
                close_price=Decimal(str(parsed['close_price'])),
                tick_count=parsed['tick_count']
            )
        return None

    def set_candlestick_history(self, symbol: str, timeframe: str, 
                               candles: List[CandlestickData], limit: int = 100) -> None:
        """ローソク足履歴を保存（リスト形式）"""
        key = f"candle:{symbol}:{timeframe}:history"
        
        # 最新のローソク足から指定数だけ保存
        candle_list = []
        for candle in candles[-limit:]:
            candle_list.append(asdict(candle))
        
        self.redis_client.set(key, self._json_encode(candle_list), ex=7200)  # 2時間で期限切れ
        logger.debug(f"ローソク足履歴保存: {key} ({len(candle_list)}件)")

    def get_candlestick_history(self, symbol: str, timeframe: str, 
                               limit: int = 100) -> List[CandlestickData]:
        """ローソク足履歴を取得"""
        key = f"candle:{symbol}:{timeframe}:history"
        data = self.redis_client.get(key)
        if data:
            parsed = self._json_decode(data)
            candles = []
            for item in parsed[-limit:]:
                candles.append(CandlestickData(
                    symbol=item['symbol'],
                    timeframe=item['timeframe'],
                    open_time=datetime.fromisoformat(item['open_time']),
                    close_time=datetime.fromisoformat(item['close_time']),
                    open_price=Decimal(str(item['open_price'])),
                    high_price=Decimal(str(item['high_price'])),
                    low_price=Decimal(str(item['low_price'])),
                    close_price=Decimal(str(item['close_price'])),
                    tick_count=item['tick_count']
                ))
            return candles
        return []

    # ===== 技術指標管理 =====
    
    def set_technical_indicator(self, indicator: TechnicalIndicator) -> None:
        """技術指標データを保存"""
        key = f"indicator:{indicator.symbol}:{indicator.timeframe}:{indicator.indicator_type}"
        data = asdict(indicator)
        self.redis_client.set(key, self._json_encode(data), ex=3600)  # 1時間で期限切れ
        logger.debug(f"技術指標保存: {key}")

    def get_technical_indicator(self, symbol: str, timeframe: str, 
                               indicator_type: str) -> Optional[TechnicalIndicator]:
        """技術指標データを取得"""
        key = f"indicator:{symbol}:{timeframe}:{indicator_type}"
        data = self.redis_client.get(key)
        if data:
            parsed = self._json_decode(data)
            return TechnicalIndicator(
                symbol=parsed['symbol'],
                timeframe=parsed['timeframe'],
                timestamp=datetime.fromisoformat(parsed['timestamp']),
                indicator_type=parsed['indicator_type'],
                value=Decimal(str(parsed['value'])),
                metadata=parsed.get('metadata')
            )
        return None

    def set_indicator_series(self, symbol: str, timeframe: str, 
                           indicator_type: str, values: List[float], 
                           timestamps: List[datetime]) -> None:
        """技術指標の時系列データを保存"""
        key = f"indicator:{symbol}:{timeframe}:{indicator_type}:series"
        
        series_data = {
            'values': values,
            'timestamps': [ts.isoformat() for ts in timestamps],
            'updated_at': datetime.now().isoformat()
        }
        
        self.redis_client.set(key, self._json_encode(series_data), ex=3600)  # 1時間で期限切れ
        logger.debug(f"技術指標時系列保存: {key} ({len(values)}件)")

    def get_indicator_series(self, symbol: str, timeframe: str, 
                           indicator_type: str) -> Dict[str, List]:
        """技術指標の時系列データを取得"""
        key = f"indicator:{symbol}:{timeframe}:{indicator_type}:series"
        data = self.redis_client.get(key)
        if data:
            parsed = self._json_decode(data)
            return {
                'values': parsed['values'],
                'timestamps': [datetime.fromisoformat(ts) for ts in parsed['timestamps']],
                'updated_at': datetime.fromisoformat(parsed['updated_at'])
            }
        return {'values': [], 'timestamps': [], 'updated_at': None}

    # ===== AI解析用データ集約 =====
    
    def get_ai_analysis_data(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        """AI解析用データを一括取得"""
        data = {
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': datetime.now().isoformat(),
            'latest_tick': None,
            'latest_candle': None,
            'candle_history': [],
            'indicators': {}
        }
        
        # 最新ティックデータ
        latest_tick = self.get_latest_tick(symbol)
        if latest_tick:
            data['latest_tick'] = asdict(latest_tick)
        
        # 最新ローソク足
        latest_candle = self.get_latest_candlestick(symbol, timeframe)
        if latest_candle:
            data['latest_candle'] = asdict(latest_candle)
        
        # ローソク足履歴（直近24本）
        candle_history = self.get_candlestick_history(symbol, timeframe, 24)
        data['candle_history'] = [asdict(candle) for candle in candle_history]
        
        # 技術指標データ
        indicator_types = ['sma_20', 'sma_50', 'ema_12', 'ema_26']
        for indicator_type in indicator_types:
            indicator_data = self.get_indicator_series(symbol, timeframe, indicator_type)
            if indicator_data['values']:
                data['indicators'][indicator_type] = indicator_data
        
        logger.info(f"AI解析用データ集約完了: {symbol} {timeframe}")
        return data

    # ===== 通知キュー管理 =====
    
    def push_notification(self, notification_data: Dict[str, Any]) -> None:
        """通知をキューに追加"""
        queue_key = "notification:queue"
        notification_data['queued_at'] = datetime.now().isoformat()
        self.redis_client.lpush(queue_key, self._json_encode(notification_data))
        logger.info("通知キューに追加")

    def pop_notification(self) -> Optional[Dict[str, Any]]:
        """通知をキューから取得"""
        queue_key = "notification:queue"
        data = self.redis_client.rpop(queue_key)
        if data:
            return self._json_decode(data)
        return None

    # ===== ユーティリティ =====
    
    def clear_cache(self, pattern: str = "*") -> int:
        """キャッシュをクリア"""
        keys = self.redis_client.keys(pattern)
        if keys:
            deleted = self.redis_client.delete(*keys)
            logger.info(f"キャッシュクリア: {deleted}件削除")
            return deleted
        return 0

    def get_cache_stats(self) -> Dict[str, Any]:
        """キャッシュ統計情報を取得"""
        info = self.redis_client.info()
        return {
            'used_memory': info.get('used_memory_human', 'N/A'),
            'connected_clients': info.get('connected_clients', 0),
            'total_commands_processed': info.get('total_commands_processed', 0),
            'keyspace_hits': info.get('keyspace_hits', 0),
            'keyspace_misses': info.get('keyspace_misses', 0),
            'hit_rate': round(
                info.get('keyspace_hits', 0) / 
                max(info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0), 1) * 100, 2
            )
        }

    def close(self) -> None:
        """Redis接続を閉じる"""
        self.redis_client.close()
        logger.info("Redis接続を閉じました")
    
    def cache_candlestick(self, symbol: str, timeframe: str, candle_data: Dict[str, Any]) -> None:
        """ローソク足データをキャッシュ（互換性のため）"""
        # Convert dict to CandlestickData dataclass
        candle = CandlestickData(
            symbol=symbol,
            timeframe=timeframe,
            open_time=datetime.fromisoformat(candle_data['open_time']),
            close_time=datetime.fromisoformat(candle_data['close_time']),
            open_price=Decimal(str(candle_data['open'])),
            high_price=Decimal(str(candle_data['high'])),
            low_price=Decimal(str(candle_data['low'])),
            close_price=Decimal(str(candle_data['close'])),
            tick_count=candle_data['tick_count']
        )
        self.set_latest_candlestick(candle)


# Alias for compatibility
RedisManager = RedisClient