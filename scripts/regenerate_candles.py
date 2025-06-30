#!/usr/bin/env python
"""
ローソク足データを再生成するスクリプト
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from src.db.session import AsyncSessionLocal
from src.stream.candlestick_generator import CandlestickGenerator
from src.stream.indicator_calculator import IndicatorCalculator
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def regenerate_candlesticks():
    """forex_ratesデータから過去3時間分のローソク足を再生成"""
    try:
        # 24時間前から現在まで
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(hours=24)
        
        logger.info(f"Regenerating candlesticks from {start_date} to {end_date}")
        
        # CandlestickGeneratorを初期化
        candlestick_gen = CandlestickGenerator(AsyncSessionLocal)
        
        # 履歴データからローソク足を生成
        await candlestick_gen.generate_from_historical_data("XAUUSD", start_date, end_date)
        
        logger.info("Candlestick regeneration completed")
        
        # テクニカル指標も更新
        logger.info("Updating technical indicators...")
        indicator_calc = IndicatorCalculator(AsyncSessionLocal)
        
        for timeframe in ['1m', '5m', '15m', '1h']:
            await indicator_calc.calculate_indicators("XAUUSD", timeframe)
            logger.info(f"Updated indicators for {timeframe}")
        
        logger.info("All done!")
        
    except Exception as e:
        logger.error(f"Error regenerating candlesticks: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(regenerate_candlesticks())