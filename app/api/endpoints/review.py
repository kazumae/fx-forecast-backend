"""予測レビュー/フィードバックのAPIエンドポイント"""
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Request
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict, Tuple
from datetime import datetime

from app.db.deps import get_db
from app.models.forecast import ForecastRequest, ForecastReview, ForecastReviewImage, ForecastReviewComment
from app.schemas.review import ReviewResponse, ReviewRequest, ForecastWithReviewsResponse
from app.schemas.forecast import ReviewCommentCreate, ReviewCommentUpdate, ReviewCommentResponse
from app.services import AnthropicService
from app.services.image_storage import ImageStorageService
from app.services.metadata_service import MetadataService
from app.services.learning_data_service import LearningDataService
from app.core.review_prompts import get_review_prompt
from app.api.endpoints.analysis import process_timeframe_files


router = APIRouter()


@router.post("/{forecast_id}/review", response_model=ReviewResponse)
async def create_forecast_review(
    forecast_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actual_outcome: Optional[str] = Form(None, description="実際の結果：long_success、short_success、neutral"),
    accuracy_notes: Optional[str] = Form(None, description="精度に関する追加メモ"),
    timeframe_1m: UploadFile | None = File(None, description="1分足チャート（振り返り用）"),
    timeframe_5m: UploadFile | None = File(None, description="5分足チャート（振り返り用）"),
    timeframe_15m: UploadFile | None = File(None, description="15分足チャート（振り返り用）"),
    timeframe_1h: UploadFile | None = File(None, description="1時間足チャート（振り返り用）"),
    timeframe_4h: UploadFile | None = File(None, description="4時間足チャート（振り返り用）"),
    timeframe_d1: UploadFile | None = File(None, description="日足チャート（振り返り用）")
):
    """
    元の予測と新しいチャート画像を比較して予測のレビューを作成
    
    - **forecast_id**: レビュー対象の元の予測のID
    - **actual_outcome**: オプションの結果分類
    - **accuracy_notes**: 精度に関するオプションのメモ
    - **timeframe_***: 実際の価格変動を示す新しいチャート画像
    """
    
    # Get original forecast
    forecast = db.query(ForecastRequest)\
                 .options(joinedload(ForecastRequest.images))\
                 .filter(ForecastRequest.id == forecast_id)\
                 .first()
    
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast not found")
    
    # Collect uploaded files
    timeframe_files = {
        "1分足": timeframe_1m if timeframe_1m and timeframe_1m.filename else None,
        "5分足": timeframe_5m if timeframe_5m and timeframe_5m.filename else None,
        "15分足": timeframe_15m if timeframe_15m and timeframe_15m.filename else None,
        "1時間足": timeframe_1h if timeframe_1h and timeframe_1h.filename else None,
        "4時間足": timeframe_4h if timeframe_4h and timeframe_4h.filename else None,
        "日足": timeframe_d1 if timeframe_d1 and timeframe_d1.filename else None
    }
    
    # Process files
    images_with_timeframes, timeframe_info = await process_timeframe_files(timeframe_files)
    
    # Validate
    if len(images_with_timeframes) == 0:
        raise HTTPException(status_code=400, detail="At least 1 review image is required")
    if len(images_with_timeframes) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 review images allowed")
    
    try:
        # Initialize services
        anthropic_service = AnthropicService()
        image_storage = ImageStorageService()
        metadata_service = MetadataService()
        
        # Create review prompt with forecast creation time
        forecast_datetime = forecast.created_at.strftime("%Y年%m月%d日 %H:%M:%S")
        enhanced_response = f"【予測作成日時】{forecast_datetime}\n\n{forecast.response}"
        review_prompt = get_review_prompt(enhanced_response)
        
        # Analyze with review prompt using the review-specific method
        review_analysis = await anthropic_service.analyze_review(
            images_with_timeframes, review_prompt
        )
        
        # Extract metadata from the review
        review_metadata = await metadata_service.extract_metadata_from_review(review_analysis)
        
        # Create review record
        review = ForecastReview(
            forecast_id=forecast_id,
            review_timeframes=[tf for tf, _ in images_with_timeframes],
            review_prompt=f"Review analysis for forecast #{forecast_id}: {timeframe_info}",
            review_response=review_analysis,
            actual_outcome=actual_outcome,
            accuracy_notes=accuracy_notes,
            review_metadata=review_metadata
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        
        # Save review images
        for timeframe, image_data in images_with_timeframes:
            # Get original filename
            original_filename = "review_chart.jpg"
            for tf_label, file in timeframe_files.items():
                if tf_label == timeframe and file:
                    original_filename = file.filename
                    break
            
            # Save image
            filename, file_path, file_size = image_storage.save_image(
                image_data, f"review_{timeframe.replace('足', '')}", original_filename
            )
            
            # Get mime type
            mime_type = "image/jpeg"
            if original_filename.lower().endswith('.png'):
                mime_type = "image/png"
            
            # Save review image record
            review_image = ForecastReviewImage(
                review_id=review.id,
                timeframe=timeframe.replace("足", ""),
                filename=filename,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type
            )
            db.add(review_image)
        
        db.commit()
        db.refresh(review)
        
        # Extract learning data from the review in background (non-blocking)
        # Comment out for now to avoid delays - can be re-enabled with async task queue
        # try:
        #     learning_service = LearningDataService(db)
        #     learning_data = await learning_service.extract_review_learning_data(review)
        #     if not forecast.extra_metadata:
        #         forecast.extra_metadata = {}
        #     if "review_learning_data" not in forecast.extra_metadata:
        #         forecast.extra_metadata["review_learning_data"] = []
        #     forecast.extra_metadata["review_learning_data"].append(learning_data)
        #     compiled_data = await learning_service.compile_learning_data(days_back=7)
        #     await learning_service.save_learning_data(
        #         compiled_data, 
        #         filename=f"review_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        #     )
        #     db.commit()
        # except Exception as e:
        #     print(f"Failed to extract learning data from review: {e}")
        
        # Add URLs to response
        base_url = str(request.base_url).rstrip('/')
        review_dict = ReviewResponse.model_validate(review).model_dump()
        for img in review_dict['review_images']:
            img['url'] = f"{base_url}/api/v1/review/image/{img['id']}"
        
        return review_dict
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{forecast_id}", response_model=ForecastWithReviewsResponse)
async def get_forecast_with_reviews(
    forecast_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    予測とそのすべてのレビューを取得
    """
    forecast = db.query(ForecastRequest)\
                 .options(
                     joinedload(ForecastRequest.images),
                     joinedload(ForecastRequest.reviews).joinedload(ForecastReview.review_images)
                 )\
                 .filter(ForecastRequest.id == forecast_id)\
                 .first()
    
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast not found")
    
    # Add URLs
    base_url = str(request.base_url).rstrip('/')
    forecast_dict = ForecastWithReviewsResponse.model_validate(forecast).model_dump()
    
    # Add URLs to original images
    for img in forecast_dict['images']:
        img['url'] = f"{base_url}/api/v1/history/image/{img['id']}"
    
    # Add URLs to review images
    for review in forecast_dict['reviews']:
        for img in review['review_images']:
            img['url'] = f"{base_url}/api/v1/review/image/{img['id']}"
    
    return forecast_dict


@router.get("/image/{image_id}")
async def get_review_image(
    image_id: int,
    db: Session = Depends(get_db)
):
    """
    レビュー画像ファイルを配信
    """
    from fastapi.responses import FileResponse
    from pathlib import Path
    
    image = db.query(ForecastReviewImage).filter(ForecastReviewImage.id == image_id).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Review image not found")
    
    # Get full path
    image_path = Path("/app") / image.file_path
    
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Review image file not found on disk")
    
    return FileResponse(
        path=str(image_path),
        media_type=image.mime_type or "image/jpeg",
        filename=image.filename
    )


# Review Comment Endpoints
@router.get("/review/{review_id}/comments", response_model=List[ReviewCommentResponse])
async def get_review_comments(
    review_id: int,
    db: Session = Depends(get_db)
):
    """
    レビューのコメント一覧を取得（トップレベルのコメントのみ、返信は各コメントに含まれる）
    """
    # Check if review exists
    review = db.query(ForecastReview).filter(ForecastReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    # Get top-level comments (parent_comment_id is None)
    comments = db.query(ForecastReviewComment)\
                 .filter(
                     ForecastReviewComment.review_id == review_id,
                     ForecastReviewComment.parent_comment_id.is_(None)
                 )\
                 .order_by(ForecastReviewComment.created_at.desc())\
                 .all()
    
    return comments


@router.post("/review/{review_id}/comments", response_model=ReviewCommentResponse)
async def create_review_comment(
    review_id: int,
    comment: ReviewCommentCreate,
    db: Session = Depends(get_db)
):
    """
    レビューに新しいコメントを追加
    
    - **comment_type**: "question", "answer", "note"のいずれか
    - **content**: コメントの内容
    - **parent_comment_id**: 返信の場合は親コメントのID
    """
    # Check if review exists with its forecast
    review = db.query(ForecastReview)\
               .options(joinedload(ForecastReview.forecast))\
               .filter(ForecastReview.id == review_id)\
               .first()
               
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    # Validate parent comment if provided
    if comment.parent_comment_id:
        parent = db.query(ForecastReviewComment)\
                   .filter(
                       ForecastReviewComment.id == comment.parent_comment_id,
                       ForecastReviewComment.review_id == review_id
                   )\
                   .first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent comment not found")
    
    # Create comment
    db_comment = ForecastReviewComment(
        review_id=review_id,
        parent_comment_id=comment.parent_comment_id,
        comment_type=comment.comment_type,
        content=comment.content,
        author="User",
        is_ai_response=False
    )
    
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    
    # If it's a question type, generate AI answer
    if comment.comment_type == "question" and not comment.parent_comment_id:
        try:
            # Initialize Anthropic service
            anthropic_service = AnthropicService()
            
            # Prepare context
            context = f"""
レビュー内容：
{review.review_response}

元の予測：
{review.forecast.response}

ユーザーからの質問：
{comment.content}

この質問に対して、レビューと元の予測の内容を踏まえて具体的かつ建設的な回答を提供してください。
トレーディングの改善に役立つアドバイスを含めてください。
"""
            
            # Get AI response
            ai_response = await anthropic_service.generate_comment_response(context)
            
            # Create AI answer
            ai_comment = ForecastReviewComment(
                review_id=review_id,
                parent_comment_id=db_comment.id,
                comment_type="answer",
                content=ai_response,
                author="AI",
                is_ai_response=True,
                extra_metadata={"confidence": "high", "context": "review_question"}
            )
            
            db.add(ai_comment)
            db.commit()
            db.refresh(db_comment)
            
        except Exception as e:
            print(f"Error generating AI response: {e}")
            # Continue without AI response if it fails
    
    return db_comment


@router.put("/review/comments/{comment_id}", response_model=ReviewCommentResponse)
async def update_review_comment(
    comment_id: int,
    comment_update: ReviewCommentUpdate,
    db: Session = Depends(get_db)
):
    """
    レビューコメントを更新
    """
    # Get comment
    comment = db.query(ForecastReviewComment)\
                .filter(ForecastReviewComment.id == comment_id)\
                .first()
    
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Only allow updating user comments, not AI responses
    if comment.is_ai_response:
        raise HTTPException(status_code=403, detail="Cannot update AI-generated comments")
    
    # Update content if provided
    if comment_update.content is not None:
        comment.content = comment_update.content
        comment.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(comment)
    
    return comment


@router.delete("/review/comments/{comment_id}")
async def delete_review_comment(
    comment_id: int,
    db: Session = Depends(get_db)
):
    """
    レビューコメントを削除（関連する返信も削除される）
    """
    # Get comment
    comment = db.query(ForecastReviewComment)\
                .filter(ForecastReviewComment.id == comment_id)\
                .first()
    
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Only allow deleting user comments, not AI responses (unless deleting parent)
    if comment.is_ai_response and not comment.parent_comment_id:
        raise HTTPException(status_code=403, detail="Cannot delete AI-generated comments directly")
    
    # Delete comment (cascades to replies)
    db.delete(comment)
    db.commit()
    
    return {"message": "Comment deleted successfully"}