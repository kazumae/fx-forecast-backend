from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from app.schemas.base import BaseSchema


class CommentType(str, Enum):
    QUESTION = "question"
    ANSWER = "answer"
    NOTE = "note"


class CommentBase(BaseModel):
    content: str = Field(..., min_length=1, description="コメント内容")
    comment_type: CommentType = Field(..., description="コメントの種類")
    parent_comment_id: Optional[int] = Field(None, description="返信の親コメントID")
    extra_metadata: Optional[Dict[str, Any]] = Field(None, description="追加メタデータ")


class CommentCreate(CommentBase):
    forecast_id: int = Field(..., description="コメントする予測のID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "forecast_id": 100,
                "content": "このトレンドラインのブレイクについて詳しく教えてください。",
                "comment_type": "question",
                "parent_comment_id": None,
                "extra_metadata": {"priority": "high"}
            }
        }


class CommentUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, description="更新されたコメント内容")
    metadata: Optional[Dict[str, Any]] = Field(None, description="更新されたメタデータ")


class CommentInDB(CommentBase, BaseSchema):
    id: int
    forecast_id: int
    author: str
    is_ai_response: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config(BaseSchema.Config):
        from_attributes = True


class CommentResponse(CommentInDB):
    replies: List['CommentResponse'] = []
    # 質問タイプの場合、紐づく回答を含める
    answer: Optional['CommentResponse'] = None
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "examples": [
                {
                    "id": 6,
                    "forecast_id": 26,
                    "content": "4時間足を見ると下値を切り上げているように見えるので、大きく見るなら上昇目線では？",
                    "comment_type": "question",
                    "parent_comment_id": None,
                    "extra_metadata": None,
                    "author": "User",
                    "is_ai_response": False,
                    "created_at": "2025-01-02T17:18:18+09:00",
                    "updated_at": None,
                    "replies": [],
                    "answer": {
                        "id": 7,
                        "forecast_id": 26,
                        "content": "回答：\nこの分析は主に短期（1時間足以下）の時間軸に基づいており、4時間足の上昇傾向については言及されていません。\n\n詳細説明：\n- この分析では1時間足をベースに「短期下降トレンド」と判断しています\n- 分析の有効期限が4時間以内と設定されており、より長期の視点は考慮対象外となっています\n- 15分足での執行を推奨しており、短期的な値動きに焦点を当てています",
                        "comment_type": "answer",
                        "parent_comment_id": 6,
                        "extra_metadata": {
                            "confidence": 0.8,
                            "reasoning": "Based on the provided analysis context"
                        },
                        "author": "AI Assistant",
                        "is_ai_response": True,
                        "created_at": "2025-01-02T17:18:25+09:00",
                        "updated_at": None,
                        "replies": [],
                        "answer": None
                    }
                },
                {
                    "id": 1,
                    "forecast_id": 26,
                    "content": "1分足では上昇をするように見えますが、ロングは狙い目ではないのでしょうか？",
                    "comment_type": "question",
                    "parent_comment_id": None,
                    "extra_metadata": None,
                    "author": "User",
                    "is_ai_response": False,
                    "created_at": "2025-01-02T17:16:43+09:00",
                    "updated_at": None,
                    "replies": [
                        {
                            "id": 49,
                            "forecast_id": 26,
                            "content": "✅ 分析が更新されました（リビジョン 1）\n\n理由: テスト更新\n\n変更内容:\n• test: テストセクション",
                            "comment_type": "note",
                            "parent_comment_id": 1,
                            "extra_metadata": {
                                "system_action": "analysis_updated",
                                "revision_number": 1
                            },
                            "author": "System",
                            "is_ai_response": False,
                            "created_at": "2025-01-03T10:30:15+09:00",
                            "updated_at": None,
                            "replies": [],
                            "answer": None
                        }
                    ],
                    "answer": None
                }
            ]
        }


class AIQuestionRequest(BaseModel):
    forecast_id: int = Field(..., description="質問する予測のID")
    question: str = Field(..., min_length=1, description="分析に関する質問")
    context: Optional[str] = Field(None, description="質問の追加コンテキスト")
    
    class Config:
        json_schema_extra = {
            "example": {
                "forecast_id": 100,
                "question": "現在のMACDの状態から、エントリータイミングをどう判断すればよいでしょうか？",
                "context": "特に日足と4時間足のダイバージェンスについて詳しく知りたいです。"
            }
        }


class AIQuestionResponse(BaseModel):
    question: CommentResponse = Field(..., description="質問コメントと紐づく回答")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="回答に対するAIの確信度")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": {
                    "id": 6,
                    "forecast_id": 26,
                    "content": "4時間足を見ると下値を切り上げているように見えるので、大きく見るなら上昇目線では？",
                    "comment_type": "question",
                    "parent_comment_id": None,
                    "extra_metadata": None,
                    "author": "User",
                    "is_ai_response": False,
                    "created_at": "2025-01-02T17:18:18+09:00",
                    "updated_at": None,
                    "replies": [],
                    "answer": {
                        "id": 7,
                        "forecast_id": 26,
                        "content": "回答：\nこの分析は主に短期（1時間足以下）の時間軸に基づいており、4時間足の上昇傾向については言及されていません。\n\n詳細説明：\n- この分析では1時間足をベースに「短期下降トレンド」と判断しています\n- 分析の有効期限が4時間以内と設定されており、より長期の視点は考慮対象外となっています\n- 15分足での執行を推奨しており、短期的な値動きに焦点を当てています",
                        "comment_type": "answer",
                        "parent_comment_id": 6,
                        "extra_metadata": {
                            "confidence": 0.8,
                            "reasoning": "Based on the provided analysis context"
                        },
                        "author": "AI Assistant",
                        "is_ai_response": True,
                        "created_at": "2025-01-02T17:18:25+09:00",
                        "updated_at": None,
                        "replies": [],
                        "answer": None
                    }
                },
                "confidence": 0.75
            }
        }


# Update forward references
CommentResponse.model_rebuild()