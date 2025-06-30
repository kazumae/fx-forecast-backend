"""
履歴データからローソク足と技術指標を生成するバッチスクリプト
"""

import asyncio
import logging
from datetime import datetime, timezone
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.stream.data_processor_db import DataProcessorDB

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def generate_historical_data(symbol: str = "XAUUSD"):
    """履歴データからローソク足と技術指標を生成"""
    logger.info(f"Starting historical data generation for {symbol}")
    
    # DataProcessorDBインスタンスを作成
    processor = DataProcessorDB()
    
    try:
        # 現在時刻から遡って処理
        end_date = datetime.now(timezone.utc)
        start_date = datetime(2025, 6, 30, 0, 0, 0, tzinfo=timezone.utc)  # forex_ratesの最初のデータから
        
        logger.info(f"Processing period: {start_date} to {end_date}")
        
        # Step 1: 履歴データからローソク足を生成
        logger.info("Step 1: Generating candlesticks from historical forex_rates...")
        await processor.generate_historical_candlesticks(symbol, start_date, end_date)
        logger.info("Candlestick generation completed")
        
        # Step 2: 各時間枠の技術指標を計算
        logger.info("Step 2: Calculating technical indicators...")
        timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        
        for timeframe in timeframes:
            logger.info(f"Calculating indicators for {timeframe} timeframe...")
            await processor.calculate_historical_indicators(symbol, timeframe, start_date, end_date)
            logger.info(f"Completed {timeframe} indicators")
        
        logger.info("All processing completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during processing: {e}")
        raise
    finally:
        processor.close()


async def check_data_status():
    """データ状態を確認"""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy import select, func
    from src.core.config import settings
    from src.models.forex import ForexRate
    from src.models.candlestick import CandlestickData
    from src.models.technical_indicator import TechnicalIndicator
    
    engine = create_async_engine(settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://'))
    
    async with AsyncSession(engine) as session:
        # forex_ratesのカウント
        forex_count = await session.execute(select(func.count()).select_from(ForexRate))
        forex_count = forex_count.scalar()
        
        # candlestick_dataのカウント
        candle_count = await session.execute(select(func.count()).select_from(CandlestickData))
        candle_count = candle_count.scalar()
        
        # technical_indicatorsのカウント
        indicator_count = await session.execute(select(func.count()).select_from(TechnicalIndicator))
        indicator_count = indicator_count.scalar()
        
        logger.info(f"Data status:")
        logger.info(f"  forex_rates: {forex_count} records")
        logger.info(f"  candlestick_data: {candle_count} records")
        logger.info(f"  technical_indicators: {indicator_count} records")
        
    await engine.dispose()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate historical candlesticks and indicators")
    parser.add_argument("--symbol", default="XAUUSD", help="Symbol to process (default: XAUUSD)")
    parser.add_argument("--check-only", action="store_true", help="Only check data status")
    
    args = parser.parse_args()
    
    if args.check_only:
        asyncio.run(check_data_status())
    else:
        asyncio.run(generate_historical_data(args.symbol))