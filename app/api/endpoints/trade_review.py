from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form
from sqlalchemy.orm import Session
from typing import Optional
import os

from app.schemas.trade_review import (
    TradeReviewCreate,
    TradeReviewResponse,
    TradeReviewDetail,
    TradeReviewListResponse,
    TradeReviewCommentCreate,
    TradeReviewCommentResponse
)
from app.models.trade_review import TradeReview, TradeReviewImage, TradeReviewComment
from app.services import AnthropicService
from app.services.image_storage import ImageStorageService
from app.db.deps import get_db
from app.core.config import settings

router = APIRouter()


@router.post("/analyze", response_model=TradeReviewResponse)
async def analyze_trade(
    db: Session = Depends(get_db),
    chart_image: UploadFile = File(..., description="チャート画像（エントリーポイントがマークされたもの）"),
    currency_pair: str = Form(..., description="通貨ペア（例：USDJPY）"),
    timeframe: str = Form(..., description="時間足（例：5m, 1h）"),
    trade_direction: Optional[str] = Form(None, description="トレード方向（long/short）"),
    additional_context: Optional[str] = Form(None, description="追加のコンテキスト情報")
):
    """
    実行したトレードのチャート画像を分析し、レビューを生成
    
    - **chart_image**: エントリーポイントがマークされたチャート画像
    - **currency_pair**: 通貨ペア
    - **timeframe**: 時間足
    - **trade_direction**: トレード方向（オプション）
    - **additional_context**: 追加情報（オプション）
    """
    
    # ファイルタイプの検証
    allowed_types = ["image/jpeg", "image/png", "image/jpg"]
    if chart_image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {chart_image.content_type}. Only JPEG/PNG allowed"
        )
    
    try:
        # 画像データを読み込む
        image_data = await chart_image.read()
        
        # Anthropicサービスでトレードレビューを実行
        anthropic_service = AnthropicService()
        review_result = await anthropic_service.analyze_trade_execution(
            image_data=image_data,
            currency_pair=currency_pair,
            timeframe=timeframe,
            trade_direction=trade_direction,
            additional_context=additional_context
        )
        
        # データベースに保存
        db_review = TradeReview(
            currency_pair=currency_pair,
            timeframe=timeframe,
            trade_direction=trade_direction,
            overall_score=review_result["overall_score"],
            entry_analysis=review_result["entry_analysis"],
            technical_analysis=review_result.get("technical_analysis"),
            risk_management=review_result.get("risk_management"),
            market_context=review_result.get("market_context"),
            good_points=review_result["good_points"],
            improvement_points=review_result["improvement_points"],
            recommendations=review_result["recommendations"],
            confidence_level=review_result.get("confidence_level"),
            raw_analysis=review_result.get("raw_analysis"),
            additional_context=additional_context
        )
        db.add(db_review)
        db.commit()
        db.refresh(db_review)
        
        # 画像を保存
        image_storage = ImageStorageService()
        filename, file_path, file_size = image_storage.save_image(
            image_data, f"trade_review_{db_review.id}", chart_image.filename
        )
        
        db_image = TradeReviewImage(
            review_id=db_review.id,
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=chart_image.content_type,
            image_type="chart"
        )
        db.add(db_image)
        db.commit()
        
        # レスポンスを準備
        response = TradeReviewResponse(
            id=db_review.id,
            currency_pair=db_review.currency_pair,
            timeframe=db_review.timeframe,
            trade_direction=db_review.trade_direction,
            overall_score=db_review.overall_score,
            entry_analysis=db_review.entry_analysis,
            technical_analysis=db_review.technical_analysis,
            risk_management=db_review.risk_management,
            market_context=db_review.market_context,
            good_points=db_review.good_points,
            improvement_points=db_review.improvement_points,
            recommendations=db_review.recommendations,
            confidence_level=db_review.confidence_level,
            additional_context=db_review.additional_context,
            created_at=db_review.created_at,
            updated_at=db_review.updated_at,
            images=[{
                "id": db_image.id,
                "filename": db_image.filename,
                "image_type": db_image.image_type
            }],
            comments_count=0
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=TradeReviewListResponse)
def get_trade_reviews(
    skip: int = 0,
    limit: int = 20,
    currency_pair: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """トレードレビューの一覧を取得"""
    
    query = db.query(TradeReview)
    
    if currency_pair:
        query = query.filter(TradeReview.currency_pair == currency_pair)
    
    total = query.count()
    
    reviews = query.order_by(TradeReview.created_at.desc()).offset(skip).limit(limit).all()
    
    # レスポンスを準備
    review_responses = []
    for review in reviews:
        comments_count = db.query(TradeReviewComment).filter(
            TradeReviewComment.review_id == review.id
        ).count()
        
        images = [{
            "id": img.id,
            "filename": img.filename,
            "image_type": img.image_type
        } for img in review.images]
        
        review_responses.append(TradeReviewResponse(
            id=review.id,
            currency_pair=review.currency_pair,
            timeframe=review.timeframe,
            trade_direction=review.trade_direction,
            overall_score=review.overall_score,
            entry_analysis=review.entry_analysis,
            technical_analysis=review.technical_analysis,
            risk_management=review.risk_management,
            market_context=review.market_context,
            good_points=review.good_points,
            improvement_points=review.improvement_points,
            recommendations=review.recommendations,
            confidence_level=review.confidence_level,
            additional_context=review.additional_context,
            created_at=review.created_at,
            updated_at=review.updated_at,
            images=images,
            comments_count=comments_count
        ))
    
    return TradeReviewListResponse(
        reviews=review_responses,
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/{review_id}", response_model=TradeReviewDetail)
def get_trade_review(
    review_id: int,
    db: Session = Depends(get_db)
):
    """特定のトレードレビューの詳細を取得"""
    
    review = db.query(TradeReview).filter(TradeReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Trade review not found")
    
    # 画像情報を準備
    images = [{
        "id": img.id,
        "filename": img.filename,
        "image_type": img.image_type,
        "file_size": img.file_size,
        "created_at": img.created_at
    } for img in review.images]
    
    # コメントを取得（トップレベルのみ）
    top_comments = db.query(TradeReviewComment).filter(
        TradeReviewComment.review_id == review_id,
        TradeReviewComment.parent_comment_id == None
    ).order_by(TradeReviewComment.created_at.desc()).all()
    
    # コメントをネストされた形式で準備
    comments = []
    for comment in top_comments:
        comment_dict = _build_comment_tree(comment, db)
        comments.append(comment_dict)
    
    return TradeReviewDetail(
        id=review.id,
        currency_pair=review.currency_pair,
        timeframe=review.timeframe,
        trade_direction=review.trade_direction,
        overall_score=review.overall_score,
        entry_analysis=review.entry_analysis,
        technical_analysis=review.technical_analysis,
        risk_management=review.risk_management,
        market_context=review.market_context,
        good_points=review.good_points,
        improvement_points=review.improvement_points,
        recommendations=review.recommendations,
        confidence_level=review.confidence_level,
        additional_context=review.additional_context,
        raw_analysis=review.raw_analysis,
        created_at=review.created_at,
        updated_at=review.updated_at,
        images=images,
        comments=comments,
        comments_count=len(comments)
    )


def _build_comment_tree(comment: TradeReviewComment, db: Session) -> dict:
    """コメントツリーを構築"""
    # Get replies excluding answers (they'll be nested under questions)
    replies = db.query(TradeReviewComment).filter(
        TradeReviewComment.parent_comment_id == comment.id,
        TradeReviewComment.comment_type != "answer"
    ).order_by(TradeReviewComment.created_at).all()
    
    comment_dict = {
        "id": comment.id,
        "review_id": comment.review_id,
        "parent_comment_id": comment.parent_comment_id,
        "comment_type": comment.comment_type,
        "content": comment.content,
        "author": comment.author,
        "is_ai_response": comment.is_ai_response,
        "extra_metadata": comment.extra_metadata,
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
        "replies": [],
        "answer": None
    }
    
    # If it's a question, find its answer
    if comment.comment_type == "question":
        answer = db.query(TradeReviewComment).filter(
            TradeReviewComment.parent_comment_id == comment.id,
            TradeReviewComment.comment_type == "answer"
        ).first()
        if answer:
            comment_dict["answer"] = _build_comment_tree(answer, db)
    
    for reply in replies:
        comment_dict["replies"].append(_build_comment_tree(reply, db))
    
    return comment_dict


@router.get("/{review_id}/comments", response_model=list[TradeReviewCommentResponse])
def get_review_comments(
    review_id: int,
    db: Session = Depends(get_db)
):
    """トレードレビューのコメントを取得"""
    
    # レビューの存在確認
    review = db.query(TradeReview).filter(TradeReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Trade review not found")
    
    # トップレベルコメントを取得
    comments = db.query(TradeReviewComment).filter(
        TradeReviewComment.review_id == review_id,
        TradeReviewComment.parent_comment_id == None
    ).order_by(TradeReviewComment.created_at.desc()).all()
    
    # レスポンスを構築
    response = []
    for comment in comments:
        comment_response = TradeReviewCommentResponse.from_orm(comment)
        comment_response.replies = _get_comment_replies(comment.id, db, exclude_answers=True)
        
        # If it's a question, find its answer
        if comment.comment_type == "question":
            answer = db.query(TradeReviewComment).filter(
                TradeReviewComment.parent_comment_id == comment.id,
                TradeReviewComment.comment_type == "answer"
            ).first()
            if answer:
                answer_response = TradeReviewCommentResponse.from_orm(answer)
                answer_response.replies = []
                comment_response.answer = answer_response
        
        response.append(comment_response)
    
    return response


def _get_comment_replies(parent_id: int, db: Session, exclude_answers: bool = False) -> list[TradeReviewCommentResponse]:
    """コメントの返信を再帰的に取得"""
    query = db.query(TradeReviewComment).filter(
        TradeReviewComment.parent_comment_id == parent_id
    )
    
    # Exclude answer type if requested (since answers are nested under questions)
    if exclude_answers:
        query = query.filter(TradeReviewComment.comment_type != "answer")
    
    replies = query.order_by(TradeReviewComment.created_at).all()
    
    response = []
    for reply in replies:
        reply_response = TradeReviewCommentResponse.from_orm(reply)
        reply_response.replies = _get_comment_replies(reply.id, db, exclude_answers)
        response.append(reply_response)
    
    return response


@router.post("/comments", response_model=TradeReviewCommentResponse)
async def create_review_comment(
    comment: TradeReviewCommentCreate,
    db: Session = Depends(get_db)
):
    """トレードレビューにコメントを追加（質問の場合は自動的にAIが回答）"""
    
    # レビューの存在確認
    review = db.query(TradeReview).filter(TradeReview.id == comment.review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Trade review not found")
    
    # 親コメントの確認（ある場合）
    if comment.parent_comment_id:
        parent = db.query(TradeReviewComment).filter(
            TradeReviewComment.id == comment.parent_comment_id,
            TradeReviewComment.review_id == comment.review_id
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent comment not found")
    
    # コメントを作成
    db_comment = TradeReviewComment(
        review_id=comment.review_id,
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
            # AnthropicサービスでAI回答を生成
            anthropic_service = AnthropicService()
            
            # コンテキストを準備
            ai_context = f"""以下はトレードレビューの内容です：

通貨ペア: {review.currency_pair}
時間足: {review.timeframe}
トレード方向: {review.trade_direction or "不明"}
総合評価: {review.overall_score}/10点

エントリー分析:
{review.entry_analysis}

良かった点:
{chr(10).join(f"- {point}" for point in review.good_points)}

改善点:
{chr(10).join(f"- {point}" for point in review.improvement_points)}

推奨事項:
{chr(10).join(f"- {rec}" for rec in review.recommendations)}

ユーザーからの質問:
{comment.content}
"""
            
            if comment.extra_metadata and comment.extra_metadata.get('context'):
                ai_context += f"\n追加コンテキスト:\n{comment.extra_metadata['context']}"
            
            # AI回答を取得
            ai_response = await anthropic_service.ask_analysis_question(ai_context)
            
            # AI回答コメントを作成
            answer_comment = TradeReviewComment(
                review_id=comment.review_id,
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
    response = TradeReviewCommentResponse.from_orm(db_comment)
    response.replies = []
    
    # Add answer if it was generated
    if answer_comment:
        answer_response = TradeReviewCommentResponse.from_orm(answer_comment)
        answer_response.replies = []
        response.answer = answer_response
    else:
        response.answer = None
        
    return response




@router.delete("/{review_id}")
def delete_trade_review(
    review_id: int,
    db: Session = Depends(get_db)
):
    """トレードレビューを削除"""
    
    review = db.query(TradeReview).filter(TradeReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Trade review not found")
    
    # 関連する画像ファイルを削除
    for image in review.images:
        if os.path.exists(image.file_path):
            os.remove(image.file_path)
    
    # データベースから削除（関連するコメントと画像も自動的に削除される）
    db.delete(review)
    db.commit()
    
    return {"message": "Trade review deleted successfully"}