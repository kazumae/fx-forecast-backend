from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Tuple, Union
import os

from app.schemas.analysis import AnalysisResponse
from app.services import AnthropicService, SlackService
from app.services.image_storage import ImageStorageService
from app.services.metadata_service import MetadataService
from app.services.enhanced_pattern_service import EnhancedPatternService
from app.models.forecast import ForecastRequest, ForecastImage
from app.db.deps import get_db
from app.core.config import settings


router = APIRouter()


def load_logic_files() -> str:
    """Load all logic files from docs/logic directory"""
    logic_dir = "/Users/kazu/Develop/kazumae/fx/fx-forecast-03/docs/logic"
    logic_content = ""
    
    logic_files = [
        "01-entrypoint.md",
        "02-zone.md", 
        "03-other.md"
    ]
    
    for filename in logic_files:
        file_path = os.path.join(logic_dir, filename)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                logic_content += f"\n\n## {filename}\n\n{f.read()}"
    
    return logic_content


async def process_timeframe_files(
    timeframe_files: Dict[str, Optional[UploadFile]]
) -> Tuple[List[Tuple[str, bytes]], str]:
    """Process timeframe files and return image data with labels"""
    images_with_timeframes = []
    timeframe_info = []
    
    for timeframe, file in timeframe_files.items():
        if file:
            content = await file.read()
            images_with_timeframes.append((timeframe, content))
            timeframe_info.append(timeframe)
    
    return images_with_timeframes, ", ".join(timeframe_info)


@router.post("/analyze/v2", response_model=AnalysisResponse)
async def analyze_charts_v2(
    db: Session = Depends(get_db),
    timeframe_1m: UploadFile | None = File(None, description="1分足チャート"),
    timeframe_5m: UploadFile | None = File(None, description="5分足チャート"),
    timeframe_15m: UploadFile | None = File(None, description="15分足チャート"),
    timeframe_1h: UploadFile | None = File(None, description="1時間足チャート"),
    timeframe_4h: UploadFile | None = File(None, description="4時間足チャート"),
    timeframe_d1: UploadFile | None = File(None, description="日足チャート")
):
    """
    AIを使用したマルチタイムフレーム分析でFXチャート画像を分析 (V2)
    
    - **timeframe_1m**: 1分足チャート (任意)
    - **timeframe_5m**: 5分足チャート (任意)
    - **timeframe_15m**: 15分足チャート (任意)
    - **timeframe_1h**: 1時間足チャート (任意)
    - **timeframe_4h**: 4時間足チャート (任意)
    - **timeframe_d1**: 日足チャート (任意)
    
    注意: 最低1枚の画像が必要、最大4枚まで
    """
    
    # Collect all uploaded files
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
    
    # Validate number of files
    if len(images_with_timeframes) == 0:
        raise HTTPException(status_code=400, detail="At least 1 image is required")
    if len(images_with_timeframes) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 images allowed")
    
    # Validate file types
    allowed_types = ["image/jpeg", "image/png", "image/jpg"]
    for timeframe, file in timeframe_files.items():
        if file and hasattr(file, 'content_type') and file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type for {timeframe}: {file.content_type}. Only JPEG/PNG allowed"
            )
    
    try:
        # Load logic files
        logic_content = load_logic_files()
        
        # Initialize services
        anthropic_service = AnthropicService()
        slack_service = SlackService()
        image_storage = ImageStorageService()
        enhanced_pattern_service = EnhancedPatternService(db)
        
        # Get timeframes list for pattern analysis
        timeframes_list = [tf for tf, _ in images_with_timeframes]
        
        # Get comprehensive pattern context
        pattern_context = enhanced_pattern_service.get_comprehensive_pattern_context(
            currency_pair="XAUUSD",
            timeframes=timeframes_list
        )
        
        # Analyze charts with Anthropic including pattern context
        analysis_result = await anthropic_service.analyze_charts_with_timeframes(
            images_with_timeframes, 
            logic_content,
            pattern_context=pattern_context
        )
        
        # Save to database
        db_request = ForecastRequest(
            currency_pair="XAUUSD",  # Default to Gold
            prompt=f"Multi-timeframe analysis: {timeframe_info}",
            response=analysis_result,
            timeframes=[tf for tf, _ in images_with_timeframes]
        )
        db.add(db_request)
        db.commit()
        db.refresh(db_request)
        
        # Save images to disk and database
        for timeframe, image_data in images_with_timeframes:
            # Get original filename from the upload
            original_filename = "chart.jpg"
            for tf_label, file in timeframe_files.items():
                if tf_label == timeframe and file:
                    original_filename = file.filename
                    break
            
            # Save image to disk
            filename, file_path, file_size = image_storage.save_image(
                image_data, timeframe.replace("足", ""), original_filename
            )
            
            # Get mime type
            mime_type = "image/jpeg"
            if original_filename.lower().endswith('.png'):
                mime_type = "image/png"
            
            # Save image record to database
            db_image = ForecastImage(
                forecast_id=db_request.id,
                timeframe=timeframe.replace("足", ""),
                filename=filename,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type
            )
            db.add(db_image)
        
        db.commit()
        
        # Send to Slack
        slack_notified = await slack_service.send_notification(
            analysis_result, 
            len(images_with_timeframes)
        )
        
        return AnalysisResponse(
            analysis=analysis_result,
            images_count=len(images_with_timeframes),
            slack_notified=slack_notified,
            request_id=db_request.id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_charts(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """
    AIを使用してFXチャート画像を分析（レガシーエンドポイント）
    
    - **files**: 1-4枚のチャート画像（必須）
    """
    
    # Validate number of files
    if not files or len(files) < 1:
        raise HTTPException(status_code=400, detail="At least 1 image is required")
    if len(files) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 images allowed")
    
    # Validate file types
    allowed_types = ["image/jpeg", "image/png", "image/jpg"]
    for file in files:
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type: {file.content_type}. Only JPEG/PNG allowed"
            )
    
    try:
        # Read all image data
        images_data = []
        for file in files:
            content = await file.read()
            images_data.append(content)
        
        # Load logic files
        logic_content = load_logic_files()
        
        # Initialize services
        anthropic_service = AnthropicService()
        slack_service = SlackService()
        
        # Analyze charts with Anthropic
        analysis_result = await anthropic_service.analyze_charts(images_data, logic_content)
        
        # Save to database
        db_request = ForecastRequest(
            currency_pair="XAUUSD",  # Default to Gold
            prompt=f"Chart analysis with {len(files)} images",
            response=analysis_result
        )
        db.add(db_request)
        db.commit()
        db.refresh(db_request)
        
        # Send to Slack
        slack_notified = await slack_service.send_notification(
            analysis_result, 
            len(files)
        )
        
        return AnalysisResponse(
            analysis=analysis_result,
            images_count=len(files),
            slack_notified=slack_notified,
            request_id=db_request.id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))