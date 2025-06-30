#!/usr/bin/env python
"""
過去データCSVをインポートするスクリプト
"""
import asyncio
import sys
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict
import logging

# プロジェクトのルートディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from src.db.session import AsyncSessionLocal
from src.models.forex import ForexRate
from src.stream.candlestick_generator import CandlestickGenerator
from src.stream.indicator_calculator import IndicatorCalculator
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def parse_csv_file(file_path: str) -> List[Dict]:
    """CSVファイルをパースしてデータを取得"""
    data = []
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # タイムスタンプをUTCに変換
            timestamp = datetime.strptime(row['date'], '%Y-%m-%d %H:%M:%S')
            timestamp = timestamp.replace(tzinfo=timezone.utc)
            
            # OHLCデータから bid/ask を推定（スプレッド0.3を想定）
            close_price = float(row['close'])
            spread = 0.3
            bid = close_price - (spread / 2)
            ask = close_price + (spread / 2)
            
            data.append({
                'currency_pair': 'XAUUSD',
                'timestamp': timestamp,
                'bid': bid,
                'ask': ask,
                'rate': close_price,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': close_price
            })
    
    return data


def import_to_forex_rates(data: List[Dict]):
    """forex_ratesテーブルにデータをインポート"""
    db = SessionLocal()
    try:
        imported_count = 0
        skipped_count = 0
        
        for item in data:
            # 既存データをチェック
            existing = db.query(ForexRate).filter(
                ForexRate.currency_pair == item['currency_pair'],
                ForexRate.timestamp == item['timestamp']
            ).first()
            
            if existing:
                skipped_count += 1
                continue
            
            # 新規データを追加
            forex_rate = ForexRate(
                currency_pair=item['currency_pair'],
                timestamp=item['timestamp'],
                bid=item['bid'],
                ask=item['ask'],
                rate=item['rate'],
                created_at=datetime.now(timezone.utc)
            )
            db.add(forex_rate)
            imported_count += 1
            
            # バッチコミット（100件ごと）
            if imported_count % 100 == 0:
                db.commit()
                logger.info(f"Imported {imported_count} records...")
        
        # 最終コミット
        db.commit()
        logger.info(f"Import completed: {imported_count} new records, {skipped_count} skipped")
        
    except Exception as e:
        logger.error(f"Error importing data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


async def generate_candlesticks_and_indicators(symbol: str, start_date: datetime, end_date: datetime):
    """インポートしたデータからローソク足とテクニカル指標を生成"""
    try:
        logger.info(f"Generating candlesticks for {symbol} from {start_date} to {end_date}")
        
        # CandlestickGeneratorを初期化
        candlestick_gen = CandlestickGenerator(AsyncSessionLocal)
        
        # 履歴データからローソク足を生成
        await candlestick_gen.generate_from_historical_data(symbol, start_date, end_date)
        
        logger.info("Candlestick generation completed")
        
        # テクニカル指標も更新
        logger.info("Calculating technical indicators...")
        indicator_calc = IndicatorCalculator(AsyncSessionLocal)
        
        for timeframe in ['1m', '5m', '15m', '1h', '4h', '1d']:
            await indicator_calc.batch_calculate_historical(symbol, timeframe, start_date, end_date)
            logger.info(f"Calculated indicators for {timeframe}")
        
        logger.info("All processing completed!")
        
    except Exception as e:
        logger.error(f"Error in processing: {e}")
        raise


def main():
    """メイン処理"""
    # データディレクトリ（Dockerコンテナ内のパス）
    data_dir = Path("/docs/data")
    
    # インポートするファイルを選択（優先順位順）
    import_files = [
        # 1分足データ（最も詳細）
        data_dir / "1minute" / "XAUUSD Forex Data Jun 26 2025.csv",
        data_dir / "1minute" / "XAUUSD Forex Data Jun 23 2025.csv",
        data_dir / "1minute" / "XAUUSD Forex Data Jun 18 2025.csv",
        data_dir / "1minute" / "XAUUSD Forex Data Jun 16 2025.csv",
        data_dir / "1minute" / "XAUUSD Forex Data Jun 11 2025.csv",
        data_dir / "1minute" / "XAUUSD Forex Data Jun 4 2025.csv",
        data_dir / "1minute" / "XAUUSD Forex Data Jun 2 2025.csv",
    ]
    
    all_data = []
    
    # 各ファイルを読み込み
    for file_path in import_files:
        if file_path.exists():
            logger.info(f"Reading {file_path.name}...")
            data = parse_csv_file(str(file_path))
            all_data.extend(data)
            logger.info(f"Read {len(data)} records from {file_path.name}")
        else:
            logger.warning(f"File not found: {file_path}")
    
    if not all_data:
        logger.error("No data to import!")
        return
    
    # データをソート（タイムスタンプ順）
    all_data.sort(key=lambda x: x['timestamp'])
    
    logger.info(f"Total records to import: {len(all_data)}")
    logger.info(f"Date range: {all_data[0]['timestamp']} to {all_data[-1]['timestamp']}")
    
    # forex_ratesにインポート
    logger.info("Importing to forex_rates table...")
    import_to_forex_rates(all_data)
    
    # ローソク足とテクニカル指標を生成
    if all_data:
        start_date = all_data[0]['timestamp']
        end_date = all_data[-1]['timestamp']
        asyncio.run(generate_candlesticks_and_indicators('XAUUSD', start_date, end_date))


if __name__ == "__main__":
    main()