"""Enhanced pattern analysis service that integrates historical patterns with AI predictions"""
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from datetime import datetime

from app.services.pattern_analysis_service import PatternAnalysisService
from app.services.metadata_service import MetadataService
from app.schemas.trade_metadata import HistoricalPatternSummary, SimilarPatternMatch


class EnhancedPatternService:
    """Service that combines pattern analysis with metadata for enhanced predictions"""
    
    def __init__(self, db: Session):
        self.db = db
        self.pattern_service = PatternAnalysisService(db)
        self.metadata_service = MetadataService()
    
    def get_comprehensive_pattern_context(
        self, 
        currency_pair: str,
        timeframes: List[str],
        current_market_conditions: Dict[str, Any] = None
    ) -> str:
        """Get comprehensive pattern context for AI prompts"""
        
        # Get historical pattern analysis
        pattern_summary = self.pattern_service.analyze_patterns_for_currency_pair(
            currency_pair, days_back=30
        )
        
        # Get metadata summary from recent reviews
        recent_metadata = self.metadata_service.get_recent_metadata(self.db, limit=10)
        metadata_summary = self.metadata_service.aggregate_metadata_summary(recent_metadata)
        
        # Find similar historical patterns if current conditions provided
        similar_patterns = []
        if current_market_conditions:
            similar_patterns = self.pattern_service.find_similar_patterns(
                current_market_conditions, limit=3
            )
        
        # Format everything for the prompt
        return self._format_enhanced_context(
            pattern_summary, metadata_summary, similar_patterns, timeframes
        )
    
    def _format_enhanced_context(
        self,
        pattern_summary: HistoricalPatternSummary,
        metadata_summary: Dict,
        similar_patterns: List[SimilarPatternMatch],
        timeframes: List[str]
    ) -> str:
        """Format all pattern data for inclusion in AI prompts"""
        
        context = "\n\n【高度なパターン分析コンテキスト】\n"
        context += "="*50 + "\n\n"
        
        # 1. Pattern Success Rates
        context += "📊 パターン別成功率（過去30日）:\n"
        for pattern_stat in pattern_summary.pattern_stats:
            if pattern_stat.total_occurrences >= 3:  # Only show patterns with enough data
                context += f"• {pattern_stat.pattern_type.value}: "
                context += f"成功率 {pattern_stat.success_rate:.1%} "
                context += f"（{pattern_stat.success_count}/{pattern_stat.total_occurrences}回）\n"
        
        # 2. Timeframe Performance
        context += "\n⏰ 時間足別パフォーマンス:\n"
        relevant_timeframes = [tf for tf in pattern_summary.timeframe_stats if tf.timeframe in timeframes]
        for tf_stat in relevant_timeframes:
            if tf_stat.total_trades > 0:
                context += f"• {tf_stat.timeframe}: "
                context += f"成功率 {tf_stat.success_rate:.1%} "
                context += f"（{tf_stat.total_trades}回の取引）\n"
        
        # 3. Recent Performance Insights
        if metadata_summary:
            context += f"\n📈 直近の実績（{metadata_summary.get('total_reviews', 0)}件の検証）:\n"
            context += f"• 全体成功率: {metadata_summary.get('success_rate', 0):.1f}%\n"
            context += f"• 平均スコア: {metadata_summary.get('average_score', 0):.1f}/10\n"
        
        # 4. Success Factors
        if pattern_summary.successful_pattern_characteristics:
            context += "\n✅ 成功パターンの特徴:\n"
            chars = pattern_summary.successful_pattern_characteristics
            if chars.get('high_success_patterns'):
                context += f"• 高成功率パターン: {', '.join(chars['high_success_patterns'])}\n"
            if chars.get('average_success_rate'):
                context += f"• 平均成功率: {chars['average_success_rate']:.1%}\n"
        
        # 5. Common Success/Failure Factors from metadata
        if metadata_summary.get('common_success_factors'):
            context += "\n🎯 成功要因TOP3:\n"
            for factor in metadata_summary['common_success_factors'][:3]:
                context += f"• {factor}\n"
        
        if metadata_summary.get('common_failure_factors'):
            context += "\n⚠️ 失敗要因TOP3:\n"
            for factor in metadata_summary['common_failure_factors'][:3]:
                context += f"• {factor}\n"
        
        # 6. Similar Historical Patterns
        if similar_patterns:
            context += "\n📝 類似の過去パターン:\n"
            for i, match in enumerate(similar_patterns[:3], 1):
                context += f"\n{i}. 類似度 {match.similarity_score:.1%}:\n"
                context += f"   • パターン: {match.pattern_type.value}\n"
                context += f"   • 結果: {match.outcome.value}\n"
                if match.key_similarities:
                    context += f"   • 共通点: {', '.join(match.key_similarities[:2])}\n"
                if match.trade_result.get('accuracy_notes'):
                    context += f"   • 注意点: {match.trade_result['accuracy_notes']}\n"
        
        # 7. Recommendations
        if pattern_summary.recommendations:
            context += "\n💡 推奨事項:\n"
            for rec in pattern_summary.recommendations[:3]:
                context += f"• {rec}\n"
        
        # 8. Caution Zones
        if metadata_summary.get('caution_zones'):
            context += f"\n⚡ 要注意価格帯: {', '.join(metadata_summary['caution_zones'])}\n"
        
        # 9. Confidence Level
        context += f"\n📊 データ信頼度: {pattern_summary.confidence_score:.0%}\n"
        context += f"（分析期間: {pattern_summary.analysis_period}）\n"
        
        context += "\n" + "="*50 + "\n"
        context += "※このコンテキストを参考に、より精度の高い分析を行ってください。\n"
        context += "※ただし、現在の市場状況を最優先に判断してください。\n"
        
        return context
    
    def extract_current_conditions_from_request(
        self,
        currency_pair: str,
        timeframes: List[str],
        analysis_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract current market conditions from analysis request"""
        
        conditions = {
            'currency_pair': currency_pair,
            'timeframe': timeframes[0] if timeframes else None,
            'pattern_type': None,
            'timestamp': datetime.now()
        }
        
        # If we have analysis text, try to extract pattern type
        if analysis_text:
            pattern_type = self.pattern_service.extract_pattern_from_text(analysis_text)
            if pattern_type:
                conditions['pattern_type'] = pattern_type
        
        return conditions
    
    def update_pattern_statistics_after_trade(
        self,
        forecast_id: int,
        trade_outcome: str,
        score: float
    ):
        """Update pattern statistics after a trade is reviewed"""
        # This would be called after a trade review to update the statistics
        # Implementation would update the pattern success rates based on outcomes
        pass