"""予測履歴のAPIエンドポイント"""
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from pathlib import Path
import math

from app.db.deps import get_db
from app.models.forecast import ForecastRequest, ForecastImage
from app.schemas.forecast import ForecastHistoryResponse, ForecastHistoryItem, ForecastImageResponse


router = APIRouter()


@router.get("/", response_model=ForecastHistoryResponse)
async def get_forecast_history(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="ページ番号"),
    per_page: int = Query(10, ge=1, le=100, description="1ページあたりの項目数"),
    currency_pair: str = Query(None, description="通貨ペアでフィルタ")
):
    """
    画像付き予測履歴をページネーションで取得
    """
    # Build query
    query = db.query(ForecastRequest).options(joinedload(ForecastRequest.images))
    
    if currency_pair:
        query = query.filter(ForecastRequest.currency_pair == currency_pair)
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    total_pages = math.ceil(total / per_page)
    offset = (page - 1) * per_page
    
    # Get paginated results
    items = query.order_by(desc(ForecastRequest.created_at))\
                 .offset(offset)\
                 .limit(per_page)\
                 .all()
    
    # Add URLs to images
    base_url = str(request.base_url).rstrip('/')
    history_items = []
    for item in items:
        item_dict = ForecastHistoryItem.model_validate(item).model_dump()
        for i, img in enumerate(item_dict['images']):
            img['url'] = f"{base_url}/api/v1/history/image/{img['id']}"
        history_items.append(item_dict)
    
    return ForecastHistoryResponse(
        items=history_items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/{forecast_id}", response_model=ForecastHistoryItem)
async def get_forecast_detail(
    forecast_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    URL付き画像を含む予測の詳細情報を取得
    """
    forecast = db.query(ForecastRequest)\
                 .options(joinedload(ForecastRequest.images))\
                 .filter(ForecastRequest.id == forecast_id)\
                 .first()
    
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast not found")
    
    # Add URLs to images
    base_url = str(request.base_url).rstrip('/')
    forecast_dict = ForecastHistoryItem.model_validate(forecast).model_dump()
    for img in forecast_dict['images']:
        img['url'] = f"{base_url}/api/v1/history/image/{img['id']}"
    
    return forecast_dict


@router.get("/image/{image_id}")
async def get_forecast_image(
    image_id: int,
    db: Session = Depends(get_db)
):
    """
    予測画像ファイルを配信
    """
    image = db.query(ForecastImage).filter(ForecastImage.id == image_id).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Get full path
    image_path = Path("/app") / image.file_path
    
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found on disk")
    
    return FileResponse(
        path=str(image_path),
        media_type=image.mime_type or "image/jpeg",
        filename=image.filename
    )


@router.delete("/{forecast_id}")
async def delete_forecast(
    forecast_id: int,
    db: Session = Depends(get_db)
):
    """
    予測と関連する画像を削除
    """
    forecast = db.query(ForecastRequest)\
                 .options(joinedload(ForecastRequest.images))\
                 .filter(ForecastRequest.id == forecast_id)\
                 .first()
    
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast not found")
    
    # Delete image files from disk
    from app.services.image_storage import ImageStorageService
    storage = ImageStorageService()
    storage.delete_forecast_images(
        forecast_id, 
        [img.file_path for img in forecast.images]
    )
    
    # Delete from database (cascade will delete images)
    db.delete(forecast)
    db.commit()
    
    return {"message": "Forecast deleted successfully"}