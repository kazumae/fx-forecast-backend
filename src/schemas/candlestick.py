"""
ローソク足データスキーマ
"""
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class CandlestickOut(BaseModel):
    """ローソク足データ出力スキーマ"""
    timestamp: datetime = Field(..., description="タイムスタンプ（終値時刻）")
    open: float = Field(..., description="始値")
    high: float = Field(..., description="高値")
    low: float = Field(..., description="安値")
    close: float = Field(..., description="終値")
    volume: float = Field(..., description="出来高（ティック数）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-06-30T12:00:00Z",
                "open": 3287.50,
                "high": 3310.25,
                "low": 3285.00,
                "close": 3307.00,
                "volume": 1234
            }
        }


class CandlestickResponse(BaseModel):
    """ローソク足データレスポンススキーマ"""
    symbol: str = Field(..., description="通貨ペアシンボル")
    timeframe: str = Field(..., description="時間枠")
    count: int = Field(..., description="データ件数")
    data: List[CandlestickOut] = Field(..., description="ローソク足データ配列")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "XAUUSD",
                "timeframe": "1h",
                "count": 2,
                "data": [
                    {
                        "timestamp": "2025-06-30T11:00:00Z",
                        "open": 3285.50,
                        "high": 3290.25,
                        "low": 3284.00,
                        "close": 3287.50,
                        "volume": 987
                    },
                    {
                        "timestamp": "2025-06-30T12:00:00Z",
                        "open": 3287.50,
                        "high": 3310.25,
                        "low": 3285.00,
                        "close": 3307.00,
                        "volume": 1234
                    }
                ]
            }
        }