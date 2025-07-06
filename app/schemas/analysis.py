from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from app.schemas.base import BaseSchema
from app.utils.timezone import get_jst_now


class AnalysisRequest(BaseModel):
    # Handled via Form and File upload
    pass


class EntryPoint(BaseModel):
    point_type: str = Field(..., description="ポイント番号")
    direction: str = Field(..., description="ロング/ショート")
    entry_price: float = Field(..., description="エントリー価格")
    stop_loss: float = Field(..., description="損切り価格")
    take_profit_1: float = Field(..., description="利確目標1")
    take_profit_2: Optional[float] = Field(None, description="利確目標2")
    risk_reward_ratio: float = Field(..., description="リスクリワード比")
    timeframe: str = Field(..., description="時間足")
    reasoning: List[str] = Field(..., description="エントリー根拠")
    timing: str = Field(..., description="エントリータイミング")


class ParsedAnalysis(BaseModel):
    current_price: float = Field(..., description="現在価格")
    trend: str = Field(..., description="トレンド方向")
    timeframe: str = Field(..., description="分析時間足")
    entry_points: List[EntryPoint] = Field(..., description="検出されたエントリーポイント")
    market_overview: str = Field(..., description="相場概況")


class AnalysisResponse(BaseSchema):
    analysis: str = Field(..., description="AI分析結果（全文）")
    parsed_analysis: Optional[ParsedAnalysis] = Field(None, description="解析済み分析データ")
    timestamp: datetime = Field(default_factory=get_jst_now)
    images_count: int = Field(..., description="分析された画像数")
    slack_notified: bool = Field(default=False, description="Slack通知が送信されたかどうか")
    request_id: Optional[int] = Field(None, description="データベースレコードID")