from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.schemas.comment import (
    CommentCreate, CommentResponse, CommentUpdate
)
from app.schemas.analysis_update import (
    AnalysisUpdateRequest, AnalysisUpdateResponse, RevisionHistoryItem
)
from app.models.forecast import ForecastRequest, ForecastComment, ForecastImage
from app.db.deps import get_db
from app.services import AnthropicService
from app.services.analysis_update_service import AnalysisUpdateService
from app.services.learning_data_service import LearningDataService
from app.core.config import settings

router = APIRouter()


@router.get("/forecasts/{forecast_id}/comments", response_model=List[CommentResponse])
def get_forecast_comments(
    forecast_id: int,
    db: Session = Depends(get_db)
):
    """特定の予測のすべてのコメントを取得"""
    # Check if forecast exists
    forecast = db.query(ForecastRequest).filter(ForecastRequest.id == forecast_id).first()
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast not found")
    
    # Get only question and note type comments (answers are nested under questions)
    comments = db.query(ForecastComment).filter(
        ForecastComment.forecast_id == forecast_id,
        ForecastComment.parent_comment_id == None,
        ForecastComment.comment_type.in_(["question", "note"])
    ).order_by(ForecastComment.created_at.desc()).all()
    
    # Build response with nested structure
    response = []
    for comment in comments:
        comment_dict = CommentResponse.from_orm(comment).dict()
        
        # If it's a question, find its answer
        if comment.comment_type == "question":
            answer = db.query(ForecastComment).filter(
                ForecastComment.parent_comment_id == comment.id,
                ForecastComment.comment_type == "answer"
            ).first()
            if answer:
                comment_dict['answer'] = CommentResponse.from_orm(answer).dict()
        
        # Get other replies (excluding answers)
        comment_dict['replies'] = _get_comment_replies(comment.id, db, exclude_answers=True)
        response.append(CommentResponse(**comment_dict))
    
    return response


def _get_comment_replies(parent_id: int, db: Session, exclude_answers: bool = False) -> List[CommentResponse]:
    """Recursively get all replies for a comment"""
    query = db.query(ForecastComment).filter(
        ForecastComment.parent_comment_id == parent_id
    )
    
    # Exclude answer type if requested (since answers are nested under questions)
    if exclude_answers:
        query = query.filter(ForecastComment.comment_type != "answer")
    
    replies = query.order_by(ForecastComment.created_at).all()
    
    response = []
    for reply in replies:
        reply_dict = CommentResponse.from_orm(reply).dict()
        reply_dict['replies'] = _get_comment_replies(reply.id, db, exclude_answers)
        response.append(CommentResponse(**reply_dict))
    
    return response


@router.post("/comments", response_model=CommentResponse)
async def create_comment(
    comment: CommentCreate,
    db: Session = Depends(get_db)
):
    """予測に新しいコメントを作成（質問の場合は自動的にAIが回答）"""
    # Check if forecast exists
    forecast = db.query(ForecastRequest).filter(ForecastRequest.id == comment.forecast_id).first()
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast not found")
    
    # Check if parent comment exists (if provided)
    if comment.parent_comment_id:
        parent = db.query(ForecastComment).filter(
            ForecastComment.id == comment.parent_comment_id,
            ForecastComment.forecast_id == comment.forecast_id
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent comment not found")
    
    # Create comment
    db_comment = ForecastComment(
        forecast_id=comment.forecast_id,
        parent_comment_id=comment.parent_comment_id,
        comment_type=comment.comment_type,
        content=comment.content,
        extra_metadata=comment.extra_metadata,
        author="User",
        is_ai_response=False
    )
    
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    
    # If it's a question, automatically generate AI answer
    answer_comment = None
    if comment.comment_type == "question" and not comment.parent_comment_id:
        try:
            # Initialize Anthropic service
            anthropic_service = AnthropicService()
            
            # Get forecast images
            images_data = []
            if forecast.images:
                for image in forecast.images:
                    try:
                        # Read image file
                        image_path = f"/app/{image.file_path}"
                        with open(image_path, 'rb') as f:
                            image_data = f.read()
                            images_data.append((image.timeframe, image_data))
                    except Exception as e:
                        print(f"Failed to read image {image.file_path}: {e}")
            
            # Prepare context for AI
            ai_context = f"""以下は過去の分析結果です：

通貨ペア: {forecast.currency_pair}
使用時間足: {', '.join(forecast.timeframes) if forecast.timeframes else '不明'}

分析内容：
{forecast.response}

ユーザーからの質問：
{comment.content}
"""
            
            if comment.extra_metadata and comment.extra_metadata.get('context'):
                ai_context += f"\n追加コンテキスト：\n{comment.extra_metadata['context']}"
            
            # Get AI response with images
            ai_response = await anthropic_service.ask_analysis_question(ai_context, images_data)
            
            # Create AI answer comment
            answer_comment = ForecastComment(
                forecast_id=comment.forecast_id,
                parent_comment_id=db_comment.id,
                comment_type="answer",
                content=ai_response['answer'],
                author="AI Assistant",
                is_ai_response=True,
                extra_metadata={
                    "confidence": ai_response.get('confidence'),
                    "reasoning": ai_response.get('reasoning')
                }
            )
            db.add(answer_comment)
            db.commit()
            db.refresh(answer_comment)
            
        except Exception as e:
            print(f"Failed to generate AI answer: {e}")
            # Continue without AI answer if it fails
    
    # Build response
    response_dict = CommentResponse.from_orm(db_comment).dict()
    response_dict['replies'] = []
    
    # Add answer if it was generated
    if answer_comment:
        response_dict['answer'] = CommentResponse.from_orm(answer_comment).dict()
    else:
        response_dict['answer'] = None
        
    return CommentResponse(**response_dict)


@router.put("/comments/{comment_id}", response_model=CommentResponse)
def update_comment(
    comment_id: int,
    comment_update: CommentUpdate,
    db: Session = Depends(get_db)
):
    """既存のコメントを更新"""
    # Get comment
    comment = db.query(ForecastComment).filter(ForecastComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Only allow updating user comments, not AI responses
    if comment.is_ai_response:
        raise HTTPException(status_code=403, detail="Cannot update AI responses")
    
    # Update fields
    if comment_update.content is not None:
        comment.content = comment_update.content
    if comment_update.extra_metadata is not None:
        comment.extra_metadata = comment_update.extra_metadata
    
    db.commit()
    db.refresh(comment)
    
    # Build response
    response_dict = CommentResponse.from_orm(comment).dict()
    
    # If it's a question, find its answer
    if comment.comment_type == "question":
        answer = db.query(ForecastComment).filter(
            ForecastComment.parent_comment_id == comment.id,
            ForecastComment.comment_type == "answer"
        ).first()
        if answer:
            response_dict['answer'] = CommentResponse.from_orm(answer).dict()
    
    response_dict['replies'] = _get_comment_replies(comment.id, db, exclude_answers=True)
    return CommentResponse(**response_dict)


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db)
):
    """コメントとそのすべての返信を削除"""
    # Get comment
    comment = db.query(ForecastComment).filter(ForecastComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Only allow deleting user comments, not AI responses
    if comment.is_ai_response:
        raise HTTPException(status_code=403, detail="Cannot delete AI responses")
    
    # Delete comment (cascades to replies)
    db.delete(comment)
    db.commit()
    
    return {"message": "Comment deleted successfully"}




@router.post("/update-analysis", response_model=AnalysisUpdateResponse)
async def update_analysis_from_comment(
    request: AnalysisUpdateRequest,
    db: Session = Depends(get_db)
):
    """コメントの洞察に基づいて予測分析を更新"""
    try:
        update_service = AnalysisUpdateService(db)
        result = await update_service.update_analysis_from_comment(request)
        
        # Extract learning data from the comment Q&A after analysis update
        # Comment out for now to avoid delays - can be re-enabled with async task queue
        # try:
        #     learning_service = LearningDataService(db)
        #     comment = db.query(ForecastComment).filter(
        #         ForecastComment.id == request.comment_id
        #     ).first()
        #     if comment and comment.comment_type == "question":
        #         insights = await learning_service.extract_comment_insights(comment)
        #         forecast = db.query(ForecastRequest).filter(
        #             ForecastRequest.id == comment.forecast_id
        #         ).first()
        #         if forecast:
        #             if not forecast.extra_metadata:
        #                 forecast.extra_metadata = {}
        #             if "comment_insights" not in forecast.extra_metadata:
        #                 forecast.extra_metadata["comment_insights"] = []
        #             forecast.extra_metadata["comment_insights"].append(insights)
        #             compiled_data = await learning_service.compile_learning_data(days_back=7)
        #             await learning_service.save_learning_data(
        #                 compiled_data, 
        #                 filename=f"realtime_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        #             )
        #             db.commit()
        # except Exception as e:
        #     print(f"Failed to extract learning data from comment: {e}")
        
        return AnalysisUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update analysis: {str(e)}")


@router.get("/suggest-revision/{comment_id}")
async def suggest_revision_from_comment(
    comment_id: int,
    db: Session = Depends(get_db)
):
    """コメントを分析し、分析の修正が必要かどうかを提案"""
    try:
        update_service = AnalysisUpdateService(db)
        suggestion = await update_service.suggest_revisions_from_comment(comment_id)
        
        return suggestion
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze comment: {str(e)}")


@router.get("/forecasts/{forecast_id}/revision-history", response_model=List[RevisionHistoryItem])
def get_forecast_revision_history(
    forecast_id: int,
    db: Session = Depends(get_db)
):
    """予測の改訂履歴を取得"""
    try:
        update_service = AnalysisUpdateService(db)
        history = update_service.get_analysis_revision_history(forecast_id)
        
        return history
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get revision history: {str(e)}")