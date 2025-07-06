"""Service for analyzing historical trade patterns and extracting insights"""
import re
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.forecast import ForecastRequest, ForecastReview
from app.models.trade_review import TradeReview
from app.schemas.trade_metadata import (
    PatternType, TradeOutcome, PatternStats, TimeframeStats,
    CurrencyPairStats, MarketConditionStats, HistoricalPatternSummary,
    SimilarPatternMatch, TradePatternMetadata
)


class PatternAnalysisService:
    """Service for analyzing trading patterns and extracting metadata"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def extract_pattern_from_text(self, text: str) -> Optional[PatternType]:
        """Extract pattern type from analysis text"""
        pattern_mapping = {
            r'ポイント1|point.?1': PatternType.POINT_1,
            r'ポイント2|point.?2': PatternType.POINT_2,
            r'ポイント3-1|point.?3.?1': PatternType.POINT_3_1,
            r'ポイント3-2|point.?3.?2': PatternType.POINT_3_2,
            r'ポイント4|point.?4': PatternType.POINT_4,
            r'ポイント5|point.?5': PatternType.POINT_5,
            r'ポイント6|point.?6': PatternType.POINT_6,
            r'ポイント7|point.?7': PatternType.POINT_7,
            r'ポイント8|point.?8': PatternType.POINT_8,
            r'ポイント9|point.?9': PatternType.POINT_9,
        }
        
        text_lower = text.lower()
        for pattern, pattern_type in pattern_mapping.items():
            if re.search(pattern, text_lower):
                return pattern_type
        return None
    
    def extract_trade_outcome(self, review_text: str, actual_outcome: Optional[str]) -> TradeOutcome:
        """Extract trade outcome from review"""
        if actual_outcome:
            outcome_map = {
                'long_success': TradeOutcome.LONG_SUCCESS,
                'long_failure': TradeOutcome.LONG_FAILURE,
                'short_success': TradeOutcome.SHORT_SUCCESS,
                'short_failure': TradeOutcome.SHORT_FAILURE,
                'neutral': TradeOutcome.NEUTRAL
            }
            return outcome_map.get(actual_outcome, TradeOutcome.UNKNOWN)
        
        # Try to extract from text if not explicitly set
        text_lower = review_text.lower()
        if '成功' in text_lower or 'success' in text_lower:
            if 'ロング' in text_lower or 'long' in text_lower:
                return TradeOutcome.LONG_SUCCESS
            elif 'ショート' in text_lower or 'short' in text_lower:
                return TradeOutcome.SHORT_SUCCESS
        elif '失敗' in text_lower or 'fail' in text_lower:
            if 'ロング' in text_lower or 'long' in text_lower:
                return TradeOutcome.LONG_FAILURE
            elif 'ショート' in text_lower or 'short' in text_lower:
                return TradeOutcome.SHORT_FAILURE
        
        return TradeOutcome.UNKNOWN
    
    def analyze_patterns_for_currency_pair(
        self, 
        currency_pair: str, 
        days_back: int = 30
    ) -> HistoricalPatternSummary:
        """Analyze historical patterns for a specific currency pair"""
        
        # Get historical data
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # Get forecasts with reviews
        forecasts = self.db.query(ForecastRequest).filter(
            and_(
                ForecastRequest.currency_pair == currency_pair,
                ForecastRequest.created_at >= cutoff_date
            )
        ).all()
        
        # Get trade reviews
        trade_reviews = self.db.query(TradeReview).filter(
            and_(
                TradeReview.currency_pair == currency_pair,
                TradeReview.created_at >= cutoff_date
            )
        ).all()
        
        # Initialize statistics collectors
        pattern_stats_dict: Dict[PatternType, PatternStats] = {}
        timeframe_stats_dict: Dict[str, TimeframeStats] = {}
        market_conditions: Dict[str, MarketConditionStats] = {}
        
        # Process forecasts with reviews
        for forecast in forecasts:
            # Extract patterns from forecast
            patterns = self._extract_patterns_from_forecast(forecast)
            
            for pattern_data in patterns:
                pattern_type = pattern_data['pattern_type']
                
                # Initialize pattern stats if needed
                if pattern_type not in pattern_stats_dict:
                    pattern_stats_dict[pattern_type] = PatternStats(
                        pattern_type=pattern_type,
                        common_timeframes=[],
                        typical_market_conditions=[]
                    )
                
                stats = pattern_stats_dict[pattern_type]
                stats.total_occurrences += 1
                
                # Check reviews for outcomes
                for review in forecast.reviews:
                    outcome = self.extract_trade_outcome(
                        review.review_response, 
                        review.actual_outcome
                    )
                    
                    if outcome in [TradeOutcome.LONG_SUCCESS, TradeOutcome.SHORT_SUCCESS]:
                        stats.success_count += 1
                    elif outcome in [TradeOutcome.LONG_FAILURE, TradeOutcome.SHORT_FAILURE]:
                        stats.failure_count += 1
                
                # Update timeframe stats
                if pattern_data.get('timeframe'):
                    tf = pattern_data['timeframe']
                    if tf not in timeframe_stats_dict:
                        timeframe_stats_dict[tf] = TimeframeStats(timeframe=tf)
                    
                    tf_stats = timeframe_stats_dict[tf]
                    tf_stats.total_trades += 1
        
        # Process trade reviews for additional insights
        for review in trade_reviews:
            if review.overall_score:
                # Extract patterns from trade review
                pattern_type = self.extract_pattern_from_text(review.entry_analysis or '')
                if pattern_type and pattern_type in pattern_stats_dict:
                    pattern_stats_dict[pattern_type].average_score = (
                        pattern_stats_dict[pattern_type].average_score + review.overall_score
                    ) / 2
        
        # Calculate success rates
        for stats in pattern_stats_dict.values():
            if stats.total_occurrences > 0:
                stats.success_rate = stats.success_count / (
                    stats.success_count + stats.failure_count
                ) if (stats.success_count + stats.failure_count) > 0 else 0.0
        
        for stats in timeframe_stats_dict.values():
            if stats.total_trades > 0:
                stats.success_rate = stats.success_count / stats.total_trades
        
        # Build summary
        summary = HistoricalPatternSummary(
            currency_pair=currency_pair,
            analysis_period=f"last_{days_back}_days",
            total_patterns_analyzed=len(forecasts) + len(trade_reviews),
            pattern_stats=list(pattern_stats_dict.values()),
            timeframe_stats=list(timeframe_stats_dict.values()),
            market_condition_stats=list(market_conditions.values()),
            successful_pattern_characteristics=self._extract_success_characteristics(
                pattern_stats_dict
            ),
            failure_pattern_characteristics=self._extract_failure_characteristics(
                pattern_stats_dict
            ),
            recommendations=self._generate_recommendations(
                pattern_stats_dict, timeframe_stats_dict
            ),
            confidence_score=self._calculate_confidence_score(
                len(forecasts) + len(trade_reviews)
            ),
            generated_at=datetime.now()
        )
        
        return summary
    
    def find_similar_patterns(
        self,
        current_conditions: Dict[str, Any],
        limit: int = 5
    ) -> List[SimilarPatternMatch]:
        """Find similar historical patterns to current market conditions"""
        
        currency_pair = current_conditions.get('currency_pair')
        timeframe = current_conditions.get('timeframe')
        pattern_type = current_conditions.get('pattern_type')
        
        # Query similar forecasts
        query = self.db.query(ForecastRequest)
        
        if currency_pair:
            query = query.filter(ForecastRequest.currency_pair == currency_pair)
        
        if timeframe and isinstance(timeframe, str):
            query = query.filter(ForecastRequest.timeframes.contains([timeframe]))
        
        similar_forecasts = query.order_by(
            ForecastRequest.created_at.desc()
        ).limit(limit * 2).all()
        
        # Score and rank similarities
        matches = []
        for forecast in similar_forecasts:
            similarity_score = self._calculate_similarity_score(
                current_conditions, forecast
            )
            
            if similarity_score > 0.5:  # Threshold for similarity
                # Get outcome if available
                outcome = TradeOutcome.UNKNOWN
                if forecast.reviews:
                    latest_review = forecast.reviews[0]
                    outcome = self.extract_trade_outcome(
                        latest_review.review_response,
                        latest_review.actual_outcome
                    )
                
                match = SimilarPatternMatch(
                    pattern_id=forecast.id,
                    similarity_score=similarity_score,
                    pattern_type=pattern_type or PatternType.POINT_9,
                    currency_pair=forecast.currency_pair,
                    timeframe=timeframe or 'multiple',
                    outcome=outcome,
                    entry_conditions=self._extract_entry_conditions(forecast),
                    trade_result=self._extract_trade_result(forecast),
                    key_differences=self._find_differences(current_conditions, forecast),
                    key_similarities=self._find_similarities(current_conditions, forecast),
                    occurred_at=forecast.created_at
                )
                matches.append(match)
        
        # Sort by similarity score and return top matches
        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        return matches[:limit]
    
    def _extract_patterns_from_forecast(self, forecast: ForecastRequest) -> List[Dict]:
        """Extract pattern information from forecast text"""
        patterns = []
        
        if forecast.response:
            # Look for pattern mentions in the response
            pattern_type = self.extract_pattern_from_text(forecast.response)
            if pattern_type:
                patterns.append({
                    'pattern_type': pattern_type,
                    'timeframe': forecast.timeframes[0] if forecast.timeframes else None,
                    'text': forecast.response
                })
        
        return patterns
    
    def _extract_success_characteristics(
        self, pattern_stats: Dict[PatternType, PatternStats]
    ) -> Dict[str, Any]:
        """Extract characteristics of successful patterns"""
        successful_patterns = [
            stats for stats in pattern_stats.values() 
            if stats.success_rate > 0.6 and stats.total_occurrences > 3
        ]
        
        return {
            'high_success_patterns': [p.pattern_type.value for p in successful_patterns],
            'average_success_rate': sum(p.success_rate for p in successful_patterns) / len(successful_patterns) if successful_patterns else 0,
            'min_occurrences_for_reliability': 3
        }
    
    def _extract_failure_characteristics(
        self, pattern_stats: Dict[PatternType, PatternStats]
    ) -> Dict[str, Any]:
        """Extract characteristics of failure patterns"""
        failure_patterns = [
            stats for stats in pattern_stats.values() 
            if stats.success_rate < 0.4 and stats.total_occurrences > 3
        ]
        
        return {
            'high_failure_patterns': [p.pattern_type.value for p in failure_patterns],
            'average_failure_rate': 1 - (sum(p.success_rate for p in failure_patterns) / len(failure_patterns)) if failure_patterns else 0,
            'common_issues': ['Insufficient confirmation', 'Poor timing', 'Against major trend']
        }
    
    def _generate_recommendations(
        self, 
        pattern_stats: Dict[PatternType, PatternStats],
        timeframe_stats: Dict[str, TimeframeStats]
    ) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []
        
        # Pattern-based recommendations
        best_pattern = max(
            pattern_stats.values(), 
            key=lambda x: x.success_rate * x.total_occurrences,
            default=None
        )
        if best_pattern and best_pattern.success_rate > 0.6:
            recommendations.append(
                f"{best_pattern.pattern_type.value}パターンの成功率が{best_pattern.success_rate:.1%}と高い"
            )
        
        # Timeframe recommendations
        best_timeframe = max(
            timeframe_stats.values(),
            key=lambda x: x.success_rate * x.total_trades,
            default=None
        )
        if best_timeframe and best_timeframe.success_rate > 0.6:
            recommendations.append(
                f"{best_timeframe.timeframe}での取引成功率が高い"
            )
        
        return recommendations
    
    def _calculate_confidence_score(self, sample_size: int) -> float:
        """Calculate confidence score based on data availability"""
        if sample_size >= 100:
            return 0.95
        elif sample_size >= 50:
            return 0.85
        elif sample_size >= 20:
            return 0.70
        elif sample_size >= 10:
            return 0.50
        else:
            return 0.30
    
    def _calculate_similarity_score(
        self, 
        current: Dict[str, Any], 
        historical: ForecastRequest
    ) -> float:
        """Calculate similarity score between current and historical conditions"""
        score = 0.0
        weights = {
            'currency_pair': 0.3,
            'timeframe': 0.2,
            'pattern_type': 0.3,
            'time_proximity': 0.2
        }
        
        # Currency pair match
        if current.get('currency_pair') == historical.currency_pair:
            score += weights['currency_pair']
        
        # Timeframe match
        if current.get('timeframe') in (historical.timeframes or []):
            score += weights['timeframe']
        
        # Pattern type match
        if current.get('pattern_type'):
            historical_pattern = self.extract_pattern_from_text(historical.response or '')
            if current.get('pattern_type') == historical_pattern:
                score += weights['pattern_type']
        
        # Time proximity (more recent = higher score)
        days_ago = (datetime.now() - historical.created_at).days
        if days_ago < 7:
            score += weights['time_proximity']
        elif days_ago < 30:
            score += weights['time_proximity'] * 0.5
        elif days_ago < 90:
            score += weights['time_proximity'] * 0.2
        
        return score
    
    def _extract_entry_conditions(self, forecast: ForecastRequest) -> Dict[str, Any]:
        """Extract entry conditions from forecast"""
        # This would parse the forecast response for entry conditions
        # Simplified version for now
        return {
            'currency_pair': forecast.currency_pair,
            'timeframes': forecast.timeframes,
            'analysis_time': forecast.created_at.isoformat()
        }
    
    def _extract_trade_result(self, forecast: ForecastRequest) -> Dict[str, Any]:
        """Extract trade results from forecast reviews"""
        if not forecast.reviews:
            return {'status': 'no_review'}
        
        latest_review = forecast.reviews[0]
        return {
            'outcome': latest_review.actual_outcome,
            'review_date': latest_review.created_at.isoformat(),
            'accuracy_notes': latest_review.accuracy_notes
        }
    
    def _find_differences(
        self, 
        current: Dict[str, Any], 
        historical: ForecastRequest
    ) -> List[str]:
        """Find key differences between current and historical conditions"""
        differences = []
        
        if current.get('currency_pair') != historical.currency_pair:
            differences.append(f"通貨ペア: {current.get('currency_pair')} vs {historical.currency_pair}")
        
        current_tf = current.get('timeframe')
        hist_tfs = historical.timeframes or []
        if current_tf and current_tf not in hist_tfs:
            differences.append(f"時間足: {current_tf} vs {', '.join(hist_tfs)}")
        
        return differences
    
    def _find_similarities(
        self, 
        current: Dict[str, Any], 
        historical: ForecastRequest
    ) -> List[str]:
        """Find key similarities between current and historical conditions"""
        similarities = []
        
        if current.get('currency_pair') == historical.currency_pair:
            similarities.append(f"同じ通貨ペア: {historical.currency_pair}")
        
        current_tf = current.get('timeframe')
        if current_tf and current_tf in (historical.timeframes or []):
            similarities.append(f"同じ時間足: {current_tf}")
        
        return similarities