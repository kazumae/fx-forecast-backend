"""共通のスキーマベースクラス"""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, model_validator
from app.utils.timezone import ensure_jst


class BaseSchema(BaseModel):
    """日本時間対応のベーススキーマ"""
    
    class Config:
        # JSONエンコード時にタイムゾーン情報を含める
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    @model_validator(mode='after')
    def convert_datetime_to_jst(self) -> 'BaseSchema':
        """モデルの全ての日時フィールドを日本時間に変換"""
        # 日時フィールドの候補
        datetime_fields = ['created_at', 'updated_at', 'timestamp', 'revised_at']
        
        for field_name in datetime_fields:
            if hasattr(self, field_name):
                value = getattr(self, field_name)
                if value is not None and isinstance(value, datetime):
                    setattr(self, field_name, ensure_jst(value))
        
        return self


class MessageResponse(BaseModel):
    """Simple message response schema"""
    message: str