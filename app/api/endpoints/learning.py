"""Learning data management API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.db.deps import get_db
from app.services.learning_data_service import LearningDataService
from app.schemas.base import MessageResponse


router = APIRouter()


@router.post("/compile", response_model=MessageResponse)
async def compile_learning_data(
    days_back: Optional[int] = 30,
    db: Session = Depends(get_db)
):
    """
    手動で学習データのコンパイルをトリガー
    
    - **days_back**: 何日前までのデータをコンパイルするか（デフォルト: 30日）
    """
    try:
        learning_service = LearningDataService(db)
        
        # Compile data
        compiled_data = await learning_service.compile_learning_data(days_back=days_back)
        
        # Save to file
        filepath = await learning_service.save_learning_data(compiled_data)
        
        # Get summary statistics
        total_patterns = sum(
            stats.get("total", 0) 
            for stats in compiled_data.get("pattern_success_rates", {}).values()
        )
        
        return MessageResponse(
            message=f"Learning data compiled successfully. "
                   f"Analyzed {total_patterns} patterns from the last {days_back} days. "
                   f"Data saved to: {filepath}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compile learning data: {str(e)}")


@router.get("/summary")
async def get_learning_summary(
    db: Session = Depends(get_db)
):
    """
    現在蓄積されている学習データのサマリーを取得
    """
    try:
        learning_service = LearningDataService(db)
        
        # Get pattern success summary
        summary = learning_service.get_pattern_success_summary()
        
        # Get recent learning data files
        recent_files = learning_service.load_recent_learning_data(days=7)
        
        return {
            "summary": summary,
            "recent_compilations": len(recent_files),
            "last_compilation": recent_files[0].get("compilation_date") if recent_files else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get learning summary: {str(e)}")


@router.post("/daily-report", response_model=MessageResponse)
async def generate_daily_report(
    db: Session = Depends(get_db)
):
    """
    日次学習レポートを生成
    """
    try:
        learning_service = LearningDataService(db)
        
        # Get pattern success summary
        summary = learning_service.get_pattern_success_summary()
        
        # Save daily report
        timestamp = datetime.now().strftime("%Y%m%d")
        report_path = learning_service.data_dir / f"daily_report_{timestamp}.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"FX予測システム 日次学習レポート\n")
            f.write(f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            f.write(summary)
            f.write("\n\n" + "=" * 80 + "\n")
            f.write("このレポートは過去30日間の蓄積データから生成されています。\n")
        
        return MessageResponse(
            message=f"Daily report generated successfully. Saved to: {report_path}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate daily report: {str(e)}")