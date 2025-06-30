"""
ローソク足データ取得エンドポイント
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.api import deps
from src.models import CandlestickData
from src.schemas.candlestick import CandlestickResponse, CandlestickOut

router = APIRouter()


@router.get("/", response_model=CandlestickResponse)
def get_candlesticks(
    symbol: str = Query("XAUUSD", description="通貨ペアシンボル"),
    timeframe: str = Query("1h", regex="^(1m|15m|1h)$", description="時間枠: 1m, 15m, 1h"),
    limit: int = Query(100, ge=1, le=500, description="取得するローソク足の数"),
    db: Session = Depends(deps.get_db)
):
    """
    ローソク足データを取得
    
    - **symbol**: 通貨ペアシンボル（デフォルト: XAUUSD）
    - **timeframe**: 時間枠 - 1m（1分）、15m（15分）、1h（1時間）
    - **limit**: 取得するローソク足の数（最大500）
    """
    # データ取得
    candles = db.query(CandlestickData).filter(
        CandlestickData.symbol == symbol,
        CandlestickData.timeframe == timeframe
    ).order_by(desc(CandlestickData.close_time)).limit(limit).all()
    
    if not candles:
        raise HTTPException(
            status_code=404,
            detail=f"No candlestick data found for {symbol} {timeframe}"
        )
    
    # 古い順に並べ替え（チャート表示用）
    candles_sorted = list(reversed(candles))
    
    # レスポンス作成
    return CandlestickResponse(
        symbol=symbol,
        timeframe=timeframe,
        count=len(candles_sorted),
        data=[
            CandlestickOut(
                timestamp=candle.close_time,
                open=float(candle.open_price),
                high=float(candle.high_price),
                low=float(candle.low_price),
                close=float(candle.close_price),
                volume=float(candle.tick_count) if candle.tick_count else 0
            )
            for candle in candles_sorted
        ]
    )


@router.get("/latest", response_model=CandlestickOut)
def get_latest_candlestick(
    symbol: str = Query("XAUUSD", description="通貨ペアシンボル"),
    timeframe: str = Query("1h", regex="^(1m|15m|1h)$", description="時間枠: 1m, 15m, 1h"),
    db: Session = Depends(deps.get_db)
):
    """
    最新のローソク足データを1つだけ取得
    
    - **symbol**: 通貨ペアシンボル（デフォルト: XAUUSD）
    - **timeframe**: 時間枠 - 1m（1分）、15m（15分）、1h（1時間）
    """
    # 最新データ取得
    candle = db.query(CandlestickData).filter(
        CandlestickData.symbol == symbol,
        CandlestickData.timeframe == timeframe
    ).order_by(desc(CandlestickData.close_time)).first()
    
    if not candle:
        raise HTTPException(
            status_code=404,
            detail=f"No candlestick data found for {symbol} {timeframe}"
        )
    
    return CandlestickOut(
        timestamp=candle.close_time,
        open=float(candle.open_price),
        high=float(candle.high_price),
        low=float(candle.low_price),
        close=float(candle.close_price),
        volume=float(candle.tick_count) if candle.tick_count else 0
    )