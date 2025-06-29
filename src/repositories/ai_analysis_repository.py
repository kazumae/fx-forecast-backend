"""
AI解析結果リポジトリ
Anthropic APIによる解析結果とシグナルの管理
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func

from src.models.ai_analysis import AIAnalysisResult
from .base import BaseRepository


class AIAnalysisRepository(BaseRepository[AIAnalysisResult]):
    """AI解析結果専用リポジトリ"""
    
    def __init__(self, session: Session):
        super().__init__(AIAnalysisResult, session)
    
    def get_latest_analysis(self, symbol: str, timeframe: str) -> Optional[AIAnalysisResult]:
        """最新の解析結果を取得"""
        return self.session.query(AIAnalysisResult).filter(
            and_(
                AIAnalysisResult.symbol == symbol,
                AIAnalysisResult.timeframe == timeframe
            )
        ).order_by(desc(AIAnalysisResult.analysis_timestamp)).first()
    
    def get_recent_analyses(self, symbol: str, timeframe: str,
                          count: int = 10) -> List[AIAnalysisResult]:
        """直近の解析結果を取得"""
        return self.session.query(AIAnalysisResult).filter(
            and_(
                AIAnalysisResult.symbol == symbol,
                AIAnalysisResult.timeframe == timeframe
            )
        ).order_by(desc(AIAnalysisResult.analysis_timestamp)).limit(count).all()
    
    def get_by_signal_type(self, symbol: str, signal: str,
                          days_back: int = 7) -> List[AIAnalysisResult]:
        """シグナル種別で解析結果を取得"""
        cutoff_time = datetime.utcnow() - timedelta(days=days_back)
        
        return self.session.query(AIAnalysisResult).filter(
            and_(
                AIAnalysisResult.symbol == symbol,
                AIAnalysisResult.entry_signal == signal,
                AIAnalysisResult.analysis_timestamp >= cutoff_time
            )
        ).order_by(desc(AIAnalysisResult.analysis_timestamp)).all()
    
    def get_strong_signals(self, symbol: str, confidence_threshold: float = 0.8,
                          days_back: int = 7) -> List[AIAnalysisResult]:
        """強いシグナル（高信頼度）の解析結果を取得"""
        cutoff_time = datetime.utcnow() - timedelta(days=days_back)
        
        return self.session.query(AIAnalysisResult).filter(
            and_(
                AIAnalysisResult.symbol == symbol,
                AIAnalysisResult.confidence_score >= confidence_threshold,
                AIAnalysisResult.entry_signal.in_(['BUY', 'SELL']),
                AIAnalysisResult.analysis_timestamp >= cutoff_time
            )
        ).order_by(desc(AIAnalysisResult.analysis_timestamp)).all()
    
    def get_pending_notifications(self, symbol: str = None) -> List[AIAnalysisResult]:
        """通知待ちの解析結果を取得"""
        query = self.session.query(AIAnalysisResult).filter(
            and_(
                AIAnalysisResult.notification_sent == False,
                AIAnalysisResult.entry_signal.in_(['BUY', 'SELL']),
                AIAnalysisResult.confidence_score >= 0.7
            )
        )
        
        if symbol:
            query = query.filter(AIAnalysisResult.symbol == symbol)
        
        return query.order_by(desc(AIAnalysisResult.analysis_timestamp)).all()
    
    def mark_as_notified(self, analysis_id: int) -> bool:
        """通知完了としてマーク"""
        analysis = self.get_by_id(analysis_id)
        if analysis:
            analysis.notification_sent = True
            self.session.commit()
            return True
        return False
    
    def get_performance_stats(self, symbol: str, days_back: int = 30) -> Dict[str, Any]:
        """解析パフォーマンス統計を取得"""
        cutoff_time = datetime.utcnow() - timedelta(days=days_back)
        
        # 基本統計
        total_analyses = self.session.query(func.count(AIAnalysisResult.id)).filter(
            and_(
                AIAnalysisResult.symbol == symbol,
                AIAnalysisResult.analysis_timestamp >= cutoff_time
            )
        ).scalar()
        
        # シグナル別集計
        signal_stats = self.session.query(
            AIAnalysisResult.entry_signal,
            func.count().label('count'),
            func.avg(AIAnalysisResult.confidence_score).label('avg_confidence')
        ).filter(
            and_(
                AIAnalysisResult.symbol == symbol,
                AIAnalysisResult.analysis_timestamp >= cutoff_time
            )
        ).group_by(AIAnalysisResult.entry_signal).all()
        
        # 信頼度分布
        high_confidence = self.session.query(func.count(AIAnalysisResult.id)).filter(
            and_(
                AIAnalysisResult.symbol == symbol,
                AIAnalysisResult.analysis_timestamp >= cutoff_time,
                AIAnalysisResult.confidence_score >= 0.8
            )
        ).scalar()
        
        medium_confidence = self.session.query(func.count(AIAnalysisResult.id)).filter(
            and_(
                AIAnalysisResult.symbol == symbol,
                AIAnalysisResult.analysis_timestamp >= cutoff_time,
                AIAnalysisResult.confidence_score >= 0.6,
                AIAnalysisResult.confidence_score < 0.8
            )
        ).scalar()
        
        low_confidence = self.session.query(func.count(AIAnalysisResult.id)).filter(
            and_(
                AIAnalysisResult.symbol == symbol,
                AIAnalysisResult.analysis_timestamp >= cutoff_time,
                AIAnalysisResult.confidence_score < 0.6
            )
        ).scalar()
        
        return {
            'total_analyses': total_analyses,
            'signal_distribution': {
                row.entry_signal: {
                    'count': row.count,
                    'avg_confidence': float(row.avg_confidence) if row.avg_confidence else 0.0
                }
                for row in signal_stats
            },
            'confidence_distribution': {
                'high': high_confidence,
                'medium': medium_confidence,
                'low': low_confidence
            },
            'period_days': days_back
        }
    
    def get_signal_frequency(self, symbol: str, timeframe: str,
                           days_back: int = 30) -> Dict[str, Any]:
        """シグナル頻度分析"""
        cutoff_time = datetime.utcnow() - timedelta(days=days_back)
        
        # 日別シグナル数
        daily_signals = self.session.query(
            func.date(AIAnalysisResult.analysis_timestamp).label('date'),
            func.count().label('count')
        ).filter(
            and_(
                AIAnalysisResult.symbol == symbol,
                AIAnalysisResult.timeframe == timeframe,
                AIAnalysisResult.analysis_timestamp >= cutoff_time,
                AIAnalysisResult.entry_signal.in_(['BUY', 'SELL'])
            )
        ).group_by(func.date(AIAnalysisResult.analysis_timestamp)).all()
        
        # 時間別シグナル分布
        hourly_signals = self.session.query(
            func.extract('hour', AIAnalysisResult.analysis_timestamp).label('hour'),
            func.count().label('count')
        ).filter(
            and_(
                AIAnalysisResult.symbol == symbol,
                AIAnalysisResult.timeframe == timeframe,
                AIAnalysisResult.analysis_timestamp >= cutoff_time,
                AIAnalysisResult.entry_signal.in_(['BUY', 'SELL'])
            )
        ).group_by(func.extract('hour', AIAnalysisResult.analysis_timestamp)).all()
        
        return {
            'daily_distribution': [
                {'date': row.date.isoformat(), 'count': row.count}
                for row in daily_signals
            ],
            'hourly_distribution': [
                {'hour': int(row.hour), 'count': row.count}
                for row in hourly_signals
            ]
        }
    
    def create_analysis_record(self, symbol: str, timeframe: str, signal: str,
                             confidence: float, reasoning: str,
                             technical_data: Dict[str, Any],
                             anthropic_response: Dict[str, Any]) -> AIAnalysisResult:
        """新しい解析結果レコードを作成"""
        analysis = AIAnalysisResult.create_analysis(
            symbol=symbol,
            timeframe=timeframe,
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            technical_data=technical_data,
            anthropic_response=anthropic_response
        )
        
        self.session.add(analysis)
        self.session.commit()
        self.session.refresh(analysis)
        
        return analysis
    
    def get_recent_decisions(self, symbol: str, timeframe: str,
                           hours_back: int = 6) -> List[Dict[str, Any]]:
        """直近の解析判定結果を簡潔な形式で取得"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        analyses = self.session.query(AIAnalysisResult).filter(
            and_(
                AIAnalysisResult.symbol == symbol,
                AIAnalysisResult.timeframe == timeframe,
                AIAnalysisResult.analysis_timestamp >= cutoff_time
            )
        ).order_by(desc(AIAnalysisResult.analysis_timestamp)).all()
        
        return [
            {
                'timestamp': analysis.analysis_timestamp.isoformat(),
                'signal': analysis.entry_signal,
                'confidence': float(analysis.confidence_score) if analysis.confidence_score else 0.0,
                'reasoning_summary': analysis.reasoning[:100] + '...' if len(analysis.reasoning or '') > 100 else analysis.reasoning
            }
            for analysis in analyses
        ]
    
    def delete_old_analyses(self, symbol: str, days_to_keep: int = 180) -> int:
        """古い解析結果を削除（通知済みのもののみ）"""
        cutoff_time = datetime.utcnow() - timedelta(days=days_to_keep)
        
        deleted_count = self.session.query(AIAnalysisResult).filter(
            and_(
                AIAnalysisResult.symbol == symbol,
                AIAnalysisResult.analysis_timestamp < cutoff_time,
                AIAnalysisResult.notification_sent == True
            )
        ).delete()
        
        self.session.commit()
        return deleted_count