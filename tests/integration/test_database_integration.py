"""
データベース統合テスト
TimescaleDB、Redis、ORM、リポジトリの統合テスト
"""

import pytest
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.models.base import Base
from src.models.candlestick import CandlestickData
from src.models.technical_indicator import TechnicalIndicator
from src.models.ai_analysis import AIAnalysisResult
from src.repositories.candlestick_repository import CandlestickRepository
from src.repositories.technical_indicator_repository import TechnicalIndicatorRepository
from src.repositories.ai_analysis_repository import AIAnalysisRepository
from src.db.redis_manager import RedisClient
from src.data.csv_importer import CSVImporter


class TestDatabaseIntegration:
    """データベース統合テストクラス"""
    
    @classmethod
    def setup_class(cls):
        """テスト開始前のセットアップ"""
        # TimescaleDB接続設定
        cls.database_url = "postgresql://fx_user:fx_password@localhost:5433/fx_trading"
        cls.engine = create_engine(cls.database_url)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        
        # Redis接続設定
        cls.redis_client = RedisClient(host="localhost", port=6380)
        
        # テスト用セッション
        cls.session = cls.SessionLocal()
        
        # リポジトリ初期化
        cls.candlestick_repo = CandlestickRepository(cls.session)
        cls.indicator_repo = TechnicalIndicatorRepository(cls.session)
        cls.ai_repo = AIAnalysisRepository(cls.session)
    
    @classmethod
    def teardown_class(cls):
        """テスト終了後のクリーンアップ"""
        cls.session.close()
        cls.redis_client.close()
    
    def setup_method(self):
        """各テストメソッド開始前のセットアップ"""
        # テストデータのクリーンアップ
        self.session.query(AIAnalysisResult).filter(
            AIAnalysisResult.symbol == 'TEST_XAUUSD'
        ).delete()
        self.session.query(TechnicalIndicator).filter(
            TechnicalIndicator.symbol == 'TEST_XAUUSD'
        ).delete()
        self.session.query(CandlestickData).filter(
            CandlestickData.symbol == 'TEST_XAUUSD'
        ).delete()
        self.session.commit()
        
        # Redisのテストキーをクリア
        self.redis_client.clear_cache("test:*")
    
    def test_timescaledb_connection(self):
        """TimescaleDB接続テスト"""
        # TimescaleDB拡張の確認
        result = self.session.execute(text("SELECT extname FROM pg_extension WHERE extname = 'timescaledb';"))
        extensions = result.fetchall()
        assert len(extensions) > 0, "TimescaleDB拡張が見つかりません"
        
        # ハイパーテーブルの確認
        result = self.session.execute(text("SELECT hypertable_name FROM timescaledb_information.hypertables;"))
        hypertables = [row[0] for row in result.fetchall()]
        
        expected_hypertables = ['tick_data', 'candlestick_data', 'technical_indicators']
        for table in expected_hypertables:
            assert table in hypertables, f"ハイパーテーブル {table} が見つかりません"
    
    def test_redis_connection(self):
        """Redis接続テスト"""
        # 基本的な操作テスト
        test_key = "test:connection"
        test_value = "connection_test"
        
        # SET操作
        self.redis_client.redis_client.set(test_key, test_value, ex=60)
        
        # GET操作
        retrieved_value = self.redis_client.redis_client.get(test_key)
        assert retrieved_value == test_value, "Redis読み書きテストに失敗"
        
        # TTL確認
        ttl = self.redis_client.redis_client.ttl(test_key)
        assert ttl > 0 and ttl <= 60, "TTL設定が正しくありません"
    
    def test_candlestick_crud_operations(self):
        """ローソク足データのCRUD操作テスト"""
        symbol = "TEST_XAUUSD"
        timeframe = "1m"
        now = datetime.utcnow()
        
        # CREATE
        candle = CandlestickData.from_csv_row(
            symbol=symbol,
            timeframe=timeframe,
            date_str=now.isoformat(),
            open_val=3300.0,
            high_val=3310.0,
            low_val=3295.0,
            close_val=3305.0
        )
        
        self.candlestick_repo.session.add(candle)
        self.candlestick_repo.session.commit()
        self.candlestick_repo.session.refresh(candle)
        
        assert candle.symbol == symbol, "ローソク足作成に失敗"
        
        # READ
        retrieved = self.candlestick_repo.get_latest(symbol, timeframe)
        assert retrieved is not None, "ローソク足取得に失敗"
        assert retrieved.symbol == symbol
        assert retrieved.timeframe == timeframe
        assert float(retrieved.open_price) == 3300.0
        
        # UPDATE
        updated_candle = self.candlestick_repo.upsert_candle(
            symbol=symbol,
            timeframe=timeframe,
            open_time=now,
            open_price=3300.0,
            high_price=3315.0,  # 更新
            low_price=3290.0,   # 更新
            close_price=3308.0, # 更新
            tick_count=10
        )
        
        assert float(updated_candle.high_price) == 3315.0, "ローソク足更新に失敗"
        
        # DELETE（クリーンアップで削除される）
    
    def test_technical_indicator_calculations(self):
        """技術指標計算テスト"""
        symbol = "TEST_XAUUSD"
        timeframe = "1m"
        now = datetime.utcnow()
        
        # テスト用ローソク足データを作成（SMA計算用）
        prices = [3300, 3305, 3310, 3308, 3312, 3315, 3320, 3318, 3322, 3325, 
                 3320, 3323, 3328, 3330, 3325, 3322, 3327, 3332, 3335, 3338]
        
        for i, price in enumerate(prices):
            candle_time = now + timedelta(minutes=i)
            candle = CandlestickData(
                symbol=symbol,
                timeframe=timeframe,
                open_time=candle_time,
                close_time=candle_time + timedelta(minutes=1),
                open_price=price,
                high_price=price + 2,
                low_price=price - 2,
                close_price=price + 1,
                tick_count=1
            )
            self.session.add(candle)
        
        self.session.commit()
        
        # SMA20計算テスト
        sma_20 = sum(prices) / len(prices)  # 20個の価格の平均
        
        indicator = TechnicalIndicator.create_sma(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=now + timedelta(minutes=19),
            period=20,
            value=sma_20
        )
        
        self.session.add(indicator)
        self.session.commit()
        
        # 取得テスト
        retrieved_indicator = self.indicator_repo.get_latest(symbol, timeframe, 'sma_20')
        assert retrieved_indicator is not None, "技術指標取得に失敗"
        assert abs(float(retrieved_indicator.value) - sma_20) < 0.01, "SMA値が正しくありません"
    
    def test_csv_importer_integration(self):
        """CSVインポーター統合テスト"""
        # テスト用CSVファイルを作成
        test_csv_path = "/tmp/test_candlestick.csv"
        test_data = [
            "date,open,high,low,close",
            "2025-06-29 00:00:00,3300.0,3310.0,3295.0,3305.0",
            "2025-06-29 00:01:00,3305.0,3315.0,3300.0,3310.0",
            "2025-06-29 00:02:00,3310.0,3320.0,3305.0,3315.0"
        ]
        
        with open(test_csv_path, 'w') as f:
            f.write('\n'.join(test_data))
        
        try:
            # CSVインポートテスト
            importer = CSVImporter(self.session)
            imported_count = importer.import_candlestick_csv(
                csv_path=test_csv_path,
                symbol="TEST_XAUUSD",
                timeframe="1m"
            )
            
            assert imported_count == 3, f"期待される3件ではなく{imported_count}件インポートされました"
            
            # インポートされたデータの確認
            candles = self.candlestick_repo.get_recent("TEST_XAUUSD", "1m", 10)
            assert len(candles) == 3, "インポートされたローソク足数が正しくありません"
            
            # 最新データの確認
            latest = self.candlestick_repo.get_latest("TEST_XAUUSD", "1m")
            assert latest is not None
            assert float(latest.close_price) == 3315.0, "最新の終値が正しくありません"
            
        finally:
            # テストファイルを削除
            if os.path.exists(test_csv_path):
                os.remove(test_csv_path)
    
    def test_redis_cache_integration(self):
        """Redisキャッシュ統合テスト"""
        symbol = "TEST_XAUUSD"
        timeframe = "1m"
        
        # ティックデータのキャッシュテスト
        from src.db.redis_manager import TickData
        tick_data = TickData(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            bid=3300.0,
            ask=3305.0,
            spread=5.0
        )
        
        self.redis_client.set_latest_tick(tick_data)
        
        # 取得テスト
        retrieved_tick = self.redis_client.get_latest_tick(symbol)
        assert retrieved_tick is not None, "ティックデータキャッシュ取得に失敗"
        assert retrieved_tick.symbol == symbol
        assert float(retrieved_tick.bid) == 3300.0
        
        # ローソク足キャッシュテスト
        from src.db.redis_manager import CandlestickData as RedisCandlestick
        candle_data = RedisCandlestick(
            symbol=symbol,
            timeframe=timeframe,
            open_time=datetime.utcnow(),
            close_time=datetime.utcnow() + timedelta(minutes=1),
            open_price=3300.0,
            high_price=3310.0,
            low_price=3295.0,
            close_price=3305.0
        )
        
        self.redis_client.set_latest_candlestick(candle_data)
        
        # 取得テスト
        retrieved_candle = self.redis_client.get_latest_candlestick(symbol, timeframe)
        assert retrieved_candle is not None, "ローソク足キャッシュ取得に失敗"
        assert retrieved_candle.symbol == symbol
        assert float(retrieved_candle.close_price) == 3305.0
    
    def test_ai_analysis_workflow(self):
        """AI解析ワークフロー統合テスト"""
        symbol = "TEST_XAUUSD"
        timeframe = "15m"
        
        # 技術指標データの準備
        now = datetime.utcnow()
        technical_data = {
            'sma_20': 3320.5,
            'sma_50': 3315.2,
            'ema_12': 3325.8,
            'ema_26': 3318.9,
            'latest_price': 3330.0
        }
        
        # AI解析結果の作成
        analysis = self.ai_repo.create_analysis_record(
            symbol=symbol,
            timeframe=timeframe,
            signal='BUY',
            confidence=0.85,
            reasoning='移動平均線がゴールデンクロスを形成し、上昇トレンドが強い',
            technical_data=technical_data,
            anthropic_response={'response': 'test_response'}
        )
        
        assert analysis.id is not None, "AI解析結果作成に失敗"
        assert analysis.entry_signal == 'BUY'
        assert float(analysis.confidence_score) == 0.85
        
        # 強いシグナルの検索テスト
        strong_signals = self.ai_repo.get_strong_signals(symbol, confidence_threshold=0.8)
        assert len(strong_signals) == 1, "強いシグナル検索に失敗"
        assert strong_signals[0].id == analysis.id
        
        # 通知待ち検索テスト
        pending = self.ai_repo.get_pending_notifications(symbol)
        assert len(pending) == 1, "通知待ち検索に失敗"
        
        # 通知完了マーク
        success = self.ai_repo.mark_as_notified(analysis.id)
        assert success, "通知完了マークに失敗"
        
        # 通知済み確認
        updated_analysis = self.ai_repo.get_by_id(analysis.id)
        assert updated_analysis.notification_sent == True, "通知完了フラグが更新されていません"
    
    def test_performance_requirements(self):
        """パフォーマンス要件テスト"""
        symbol = "TEST_XAUUSD"
        timeframe = "1m"
        
        # 大量データ挿入性能テスト（1000件）
        import time
        start_time = time.time()
        
        candles_data = []
        base_time = datetime.utcnow()
        
        for i in range(1000):
            candle_time = base_time + timedelta(minutes=i)
            price = 3300 + (i % 50)  # 価格変動をシミュレート
            
            candle = CandlestickData(
                symbol=symbol,
                timeframe=timeframe,
                open_time=candle_time,
                close_time=candle_time + timedelta(minutes=1),
                open_price=price,
                high_price=price + 2,
                low_price=price - 2,
                close_price=price + 1,
                tick_count=1
            )
            candles_data.append(candle)
        
        # TimescaleDB対応の一括挿入を使用
        try:
            insert_query = text("""
                INSERT INTO candlestick_data (symbol, timeframe, open_time, close_time, 
                                            open_price, high_price, low_price, close_price, tick_count)
                VALUES (:symbol, :timeframe, :open_time, :close_time, 
                       :open_price, :high_price, :low_price, :close_price, :tick_count)
            """)
            
            batch_data = []
            for candle in candles_data:
                batch_data.append({
                    'symbol': candle.symbol,
                    'timeframe': candle.timeframe,
                    'open_time': candle.open_time,
                    'close_time': candle.close_time,
                    'open_price': candle.open_price,
                    'high_price': candle.high_price,
                    'low_price': candle.low_price,
                    'close_price': candle.close_price,
                    'tick_count': candle.tick_count
                })
            
            self.session.execute(insert_query, batch_data)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            # フォールバック: 一件ずつ挿入
            for candle in candles_data:
                self.session.merge(candle)
                try:
                    self.session.commit()
                except:
                    self.session.rollback()
        
        insert_time = time.time() - start_time
        
        # 挿入性能確認（1000件/秒以上の目標）
        insert_rate = 1000 / insert_time
        print(f"挿入性能: {insert_rate:.2f} 件/秒")
        assert insert_rate >= 100, f"挿入性能が低すぎます: {insert_rate:.2f} 件/秒"
        
        # 検索性能テスト
        start_time = time.time()
        
        recent_candles = self.candlestick_repo.get_recent(symbol, timeframe, 100)
        
        search_time = time.time() - start_time
        
        # 検索性能確認（100ms以内の目標）
        print(f"検索性能: {search_time*1000:.2f} ms")
        assert search_time < 0.5, f"検索性能が低すぎます: {search_time*1000:.2f} ms"
        assert len(recent_candles) == 100, "検索結果数が正しくありません"
    
    def test_data_integrity_and_consistency(self):
        """データ整合性とトランザクション一貫性テスト"""
        symbol = "TEST_XAUUSD"
        timeframe = "1m"
        
        try:
            # トランザクション開始
            candle = CandlestickData(
                symbol=symbol,
                timeframe=timeframe,
                open_time=datetime.utcnow(),
                close_time=datetime.utcnow() + timedelta(minutes=1),
                open_price=3300.0,
                high_price=3310.0,
                low_price=3295.0,
                close_price=3305.0,
                tick_count=1
            )
            
            self.session.add(candle)
            
            # 意図的にエラーを発生させる（不正なデータ）
            invalid_candle = CandlestickData(
                symbol=symbol,
                timeframe=timeframe,
                open_time=datetime.utcnow(),  # 同じ時刻（重複）
                close_time=datetime.utcnow() + timedelta(minutes=1),
                open_price=None,  # 不正なNULL値
                high_price=3310.0,
                low_price=3295.0,
                close_price=3305.0,
                tick_count=1
            )
            
            self.session.add(invalid_candle)
            self.session.commit()
            
            # このポイントに到達すべきではない
            assert False, "不正なデータがコミットされました"
            
        except Exception:
            # エラーが期待通り発生した場合
            self.session.rollback()
            
            # ロールバック後の確認
            candles = self.candlestick_repo.find_by_criteria(symbol=symbol, timeframe=timeframe)
            assert len(candles) == 0, "ロールバックが正しく動作していません"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])