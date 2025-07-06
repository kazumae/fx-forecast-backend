"""Schemas for analysis updates based on comments"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from app.schemas.base import BaseSchema


class AnalysisUpdateRequest(BaseModel):
    """Request to update analysis based on comment insights"""
    comment_id: int = Field(..., description="更新をトリガーしたコメントのID")
    update_reason: str = Field(..., description="分析を更新する理由")
    revised_sections: Dict[str, str] = Field(
        ..., 
        description="更新するセクションのマップ（例：'entry_point'、'risk_assessment'）"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "comment_id": 123,
                "update_reason": "上位足の分析を考慮してエントリーポイントを修正",
                "revised_sections": {
                    "entry_point": "4時間足の上昇トレンドを考慮し、押し目買いのポイントに変更",
                    "direction": "ロングエントリーに修正"
                }
            }
        }


class AnalysisUpdateResponse(BaseSchema):
    """Response after updating analysis"""
    forecast_id: int
    original_analysis: str
    revised_analysis: str
    update_metadata: Dict[str, Any]
    updated_at: datetime
    
    
class RevisionHistoryItem(BaseSchema):
    """Item in revision history"""
    revision_number: int
    revised_at: datetime
    revised_by: str
    comment_id: Optional[int]
    update_reason: str
    changes_summary: Dict[str, str]