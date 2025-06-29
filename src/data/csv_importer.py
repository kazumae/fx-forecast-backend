"""
CSVデータインポーター
テストデータのCSVファイルをTimescaleDBに取り込む
"""

import csv
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from src.models.candlestick import CandlestickData
from src.models.technical_indicator import TechnicalIndicator
from src.models.price_zone import PriceZone
from src.db.session import get_db

logger = logging.getLogger(__name__)


class CSVImporter:
    """CSVファイルからデータベースへのインポート処理"""
    
    def __init__(self, session: Session):
        self.session = session
        
    def import_candlestick_csv(self, csv_path: str, symbol: str, timeframe: str) -> int:
        """
        ローソク足CSVファイルをインポート
        
        Args:
            csv_path: CSVファイルパス
            symbol: 通貨ペア（例: 'XAUUSD'）
            timeframe: 時間枠（例: '1m', '15m', '1h', '4h', '1d'）
            
        Returns:
            インポートしたレコード数
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")
        
        imported_count = 0
        skipped_count = 0
        
        logger.info(f"CSVインポート開始: {csv_path} -> {symbol} {timeframe}")
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as file:
                csv_reader = csv.DictReader(file)
                
                for row in csv_reader:
                    try:
                        # CSVデータからCandlestickDataインスタンス作成
                        candle = CandlestickData.from_csv_row(
                            symbol=symbol,
                            timeframe=timeframe,
                            date_str=row['date'],
                            open_val=float(row['open']),
                            high_val=float(row['high']),
                            low_val=float(row['low']),
                            close_val=float(row['close'])
                        )
                        
                        self.session.add(candle)
                        # TimescaleDBの複合主キーテーブルは個別にコミット
                        self.session.commit()
                        imported_count += 1
                        
                        # 100件ごとに進捗表示
                        if imported_count % 100 == 0:
                            logger.debug(f"進捗: {imported_count}件インポート完了")
                            
                    except IntegrityError:
                        # 重複データはスキップ
                        self.session.rollback()
                        skipped_count += 1
                        logger.debug(f"重複データをスキップ: {row['date']}")
                        
                    except Exception as e:
                        logger.error(f"行のインポートに失敗: {row}, エラー: {e}")
                        self.session.rollback()
                        continue
                
        except Exception as e:
            logger.error(f"CSVインポートに失敗: {e}")
            self.session.rollback()
            raise
        
        logger.info(f"CSVインポート完了: {imported_count}件インポート, {skipped_count}件スキップ")
        return imported_count
    
    def import_directory(self, data_dir: str, symbol: str = 'XAUUSD') -> Dict[str, int]:
        """
        データディレクトリ全体をインポート
        
        Args:
            data_dir: データディレクトリパス（backend/dataなど）
            symbol: 通貨ペア
            
        Returns:
            時間枠別のインポート件数
        """
        results = {}
        
        # 時間枠とディレクトリのマッピング
        timeframe_mapping = {
            '1minute': '1m',
            '15minute': '15m',
            'hour': '1h',
            'day': '1d'
        }
        
        for dir_name, timeframe in timeframe_mapping.items():
            dir_path = os.path.join(data_dir, dir_name)
            
            if not os.path.exists(dir_path):
                logger.warning(f"ディレクトリが存在しません: {dir_path}")
                continue
                
            total_imported = 0
            csv_files = [f for f in os.listdir(dir_path) if f.endswith('.csv')]
            
            logger.info(f"{timeframe} 時間枠のインポート開始: {len(csv_files)}ファイル")
            
            for csv_file in sorted(csv_files):
                csv_path = os.path.join(dir_path, csv_file)
                try:
                    count = self.import_candlestick_csv(csv_path, symbol, timeframe)
                    total_imported += count
                    logger.info(f"完了: {csv_file} -> {count}件")
                except Exception as e:
                    logger.error(f"ファイルインポート失敗: {csv_file}, エラー: {e}")
            
            results[timeframe] = total_imported
            logger.info(f"{timeframe} 時間枠完了: 合計{total_imported}件")
        
        return results
    
    def generate_technical_indicators(self, symbol: str, timeframe: str, 
                                    start_date: Optional[datetime] = None,
                                    end_date: Optional[datetime] = None) -> int:
        """
        ローソク足データから技術指標を生成
        
        Args:
            symbol: 通貨ペア
            timeframe: 時間枠
            start_date: 開始日時（Noneの場合は全データ）
            end_date: 終了日時（Noneの場合は最新まで）
            
        Returns:
            生成した指標の数
        """
        logger.info(f"技術指標生成開始: {symbol} {timeframe}")
        
        # ローソク足データを時系列順で取得
        query = self.session.query(CandlestickData).filter(
            CandlestickData.symbol == symbol,
            CandlestickData.timeframe == timeframe
        )
        
        if start_date:
            query = query.filter(CandlestickData.open_time >= start_date)
        if end_date:
            query = query.filter(CandlestickData.open_time <= end_date)
            
        candles = query.order_by(CandlestickData.open_time).all()
        
        if len(candles) < 200:  # EMA200のため最低200本必要
            logger.warning(f"ローソク足データが不足: {len(candles)}本 (最低200本必要)")
            return 0
        
        generated_count = 0
        
        # EMA20, EMA75, EMA200を計算
        indicators_config = [
            ('ema_20', 20),
            ('ema_75', 75),
            ('ema_200', 200)
        ]
        
        for indicator_type, period in indicators_config:
            try:
                if indicator_type.startswith('sma'):
                    count = self._generate_sma(candles, symbol, timeframe, period)
                elif indicator_type.startswith('ema'):
                    count = self._generate_ema(candles, symbol, timeframe, period)
                else:
                    continue
                    
                generated_count += count
                logger.info(f"{indicator_type} 生成完了: {count}件")
                
            except Exception as e:
                logger.error(f"{indicator_type} 生成失敗: {e}")
        
        self.session.commit()
        logger.info(f"技術指標生成完了: 合計{generated_count}件")
        return generated_count
    
    def _generate_sma(self, candles: List[CandlestickData], symbol: str, 
                     timeframe: str, period: int) -> int:
        """SMA（単純移動平均）を生成"""
        generated = 0
        
        for i in range(period - 1, len(candles)):
            # period分の終値を取得
            prices = [float(candles[j].close_price) for j in range(i - period + 1, i + 1)]
            sma_value = sum(prices) / period
            
            indicator = TechnicalIndicator.create_sma(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=candles[i].open_time,
                period=period,
                value=sma_value
            )
            
            try:
                self.session.add(indicator)
                generated += 1
            except IntegrityError:
                self.session.rollback()
                continue
        
        return generated
    
    def _generate_ema(self, candles: List[CandlestickData], symbol: str, 
                     timeframe: str, period: int) -> int:
        """EMA（指数移動平均）を生成"""
        generated = 0
        multiplier = 2 / (period + 1)
        
        # 最初のEMAはSMAで初期化
        if len(candles) < period:
            return 0
            
        prices = [float(candles[j].close_price) for j in range(period)]
        ema_value = sum(prices) / period
        
        for i in range(period - 1, len(candles)):
            if i > period - 1:
                # EMA計算: (今日の終値 × 乗数) + (昨日のEMA × (1 - 乗数))
                current_price = float(candles[i].close_price)
                ema_value = (current_price * multiplier) + (ema_value * (1 - multiplier))
            
            indicator = TechnicalIndicator.create_ema(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=candles[i].open_time,
                period=period,
                value=ema_value
            )
            
            try:
                self.session.add(indicator)
                generated += 1
            except IntegrityError:
                self.session.rollback()
                continue
        
        return generated
    
    def generate_sample_price_zones(self, symbol: str = 'XAUUSD') -> int:
        """サンプル価格ゾーンを生成"""
        logger.info(f"サンプル価格ゾーン生成: {symbol}")
        
        # XAUUSDの一般的なサポート・レジスタンスレベル
        zones_data = [
            ('support', 3300.0, '2025-06-01 00:00:00'),
            ('support', 3250.0, '2025-06-01 00:00:00'),
            ('support', 3200.0, '2025-06-01 00:00:00'),
            ('resistance', 3400.0, '2025-06-01 00:00:00'),
            ('resistance', 3450.0, '2025-06-01 00:00:00'),
            ('resistance', 3500.0, '2025-06-01 00:00:00'),
        ]
        
        generated = 0
        
        for zone_type, price_level, timestamp_str in zones_data:
            timestamp = datetime.fromisoformat(timestamp_str)
            
            if zone_type == 'support':
                zone = PriceZone.create_support(symbol, price_level, timestamp)
            else:
                zone = PriceZone.create_resistance(symbol, price_level, timestamp)
            
            try:
                self.session.add(zone)
                generated += 1
            except IntegrityError:
                self.session.rollback()
                continue
        
        self.session.commit()
        logger.info(f"サンプル価格ゾーン生成完了: {generated}件")
        return generated


def import_all_test_data(data_dir: str = './data', symbol: str = 'XAUUSD') -> Dict[str, any]:
    """
    全テストデータをインポートするメイン関数
    
    Args:
        data_dir: データディレクトリパス
        symbol: 通貨ペア
        
    Returns:
        インポート結果のサマリー
    """
    from src.db.session import SessionLocal
    
    session = SessionLocal()
    importer = CSVImporter(session)
    
    try:
        # CSVデータインポート
        csv_results = importer.import_directory(data_dir, symbol)
        
        # 技術指標生成（1分足と15分足で）
        indicators_results = {}
        for timeframe in ['1m', '15m']:
            if timeframe in csv_results and csv_results[timeframe] > 0:
                count = importer.generate_technical_indicators(symbol, timeframe)
                indicators_results[timeframe] = count
        
        # サンプル価格ゾーン生成
        zones_count = importer.generate_sample_price_zones(symbol)
        
        results = {
            'candlestick_data': csv_results,
            'technical_indicators': indicators_results,
            'price_zones': zones_count,
            'total_candles': sum(csv_results.values()),
            'total_indicators': sum(indicators_results.values())
        }
        
        logger.info(f"全データインポート完了: {results}")
        return results
        
    except Exception as e:
        logger.error(f"データインポートに失敗: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    # スタンドアローン実行用
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    
    logging.basicConfig(level=logging.INFO)
    
    data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
    results = import_all_test_data(data_dir)
    print(f"インポート完了: {results}")