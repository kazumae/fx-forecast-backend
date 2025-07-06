"""API endpoints for pattern analysis"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from app.db.deps import get_db
from app.services.pattern_analysis_service import PatternAnalysisService
from app.services.enhanced_pattern_service import EnhancedPatternService
from app.schemas.trade_metadata import HistoricalPatternSummary, SimilarPatternMatch

router = APIRouter()


@router.get("/analysis/{currency_pair}", response_model=HistoricalPatternSummary)
async def get_pattern_analysis(
    currency_pair: str,
    days_back: int = Query(30, ge=7, le=90, description="分析する日数"),
    db: Session = Depends(get_db)
):
    """
    特定の通貨ペアの過去パターン分析を取得
    
    - **currency_pair**: 分析する通貨ペア (例: XAUUSD, USDJPY)
    - **days_back**: 遡る日数 (7-90日)
    """
    try:
        pattern_service = PatternAnalysisService(db)
        summary = pattern_service.analyze_patterns_for_currency_pair(
            currency_pair=currency_pair.upper(),
            days_back=days_back
        )
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/similar")
async def find_similar_patterns(
    current_conditions: Dict[str, Any],
    limit: int = Query(5, ge=1, le=10, description="返す類似パターンの最大数"),
    db: Session = Depends(get_db)
):
    """
    現在の市場状況に基づいて類似の過去パターンを検索
    
    - **current_conditions**: 現在の市場状況を含む辞書
      - currency_pair: str (例: "XAUUSD")
      - timeframe: str (例: "5m")
      - pattern_type: str (オプション、例: "point_1")
    - **limit**: 返す類似パターンの最大数
    """
    try:
        pattern_service = PatternAnalysisService(db)
        matches = pattern_service.find_similar_patterns(
            current_conditions=current_conditions,
            limit=limit
        )
        return {"matches": matches, "total_found": len(matches)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/context/{currency_pair}")
async def get_pattern_context(
    currency_pair: str,
    timeframes: str = Query(..., description="カンマ区切りの時間足リスト"),
    db: Session = Depends(get_db)
):
    """
    AI予測のための包括的なパターンコンテキストを取得
    
    - **currency_pair**: 通貨ペア (例: XAUUSD)
    - **timeframes**: カンマ区切りの時間足 (例: "1m,5m,15m")
    """
    try:
        timeframes_list = [tf.strip() for tf in timeframes.split(",")]
        enhanced_service = EnhancedPatternService(db)
        
        context = enhanced_service.get_comprehensive_pattern_context(
            currency_pair=currency_pair.upper(),
            timeframes=timeframes_list
        )
        
        return {
            "currency_pair": currency_pair.upper(),
            "timeframes": timeframes_list,
            "context": context,
            "context_length": len(context)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_pattern_statistics(
    db: Session = Depends(get_db)
):
    """
    すべての通貨ペアにわたるパターン統計を取得
    """
    try:
        pattern_service = PatternAnalysisService(db)
        
        # Get statistics for major pairs
        pairs = ["XAUUSD", "USDJPY", "EURUSD", "GBPUSD"]
        statistics = {}
        
        for pair in pairs:
            try:
                summary = pattern_service.analyze_patterns_for_currency_pair(pair, days_back=30)
                statistics[pair] = {
                    "total_patterns": summary.total_patterns_analyzed,
                    "confidence_score": summary.confidence_score,
                    "top_patterns": [
                        {
                            "type": ps.pattern_type.value,
                            "success_rate": ps.success_rate,
                            "occurrences": ps.total_occurrences
                        }
                        for ps in summary.pattern_stats[:3]
                        if ps.total_occurrences > 0
                    ]
                }
            except:
                statistics[pair] = {"error": "No data available"}
        
        return statistics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))