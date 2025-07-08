"""Service for extracting and accumulating learning data from forecasts, reviews, and comments"""
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from pathlib import Path

from app.models.forecast import ForecastRequest, ForecastReview, ForecastComment
from app.models.trade_review import TradeReview, TradeReviewComment
from app.services.anthropic_service import AnthropicService
from app.core.config import settings


class LearningDataService:
    """Service for extracting, storing, and managing learning data"""
    
    def __init__(self, db: Session):
        self.db = db
        # Use relative path that works both locally and in Docker
        base_path = os.environ.get("APP_BASE_PATH", "/app")
        self.data_dir = Path(base_path) / "data" / "learning"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.anthropic_service = AnthropicService()
    
    async def extract_pattern_metadata(self, forecast: ForecastRequest) -> Dict[str, Any]:
        """Extract pattern metadata from a forecast using AI"""
        
        # Prepare context for AI extraction
        context = f"""
以下の予測分析から、重要なパターン情報を抽出してください：

予測内容：
{forecast.response}

時間足：{', '.join(forecast.timeframes or [])}
通貨ペア：{forecast.currency_pair}

以下の情報をJSON形式で抽出してください：
1. detected_patterns: 検出されたパターン（かむかむ流ポイント1-9など）
2. trend_direction: トレンド方向（up/down/sideways）
3. entry_type: エントリータイプ（breakout/pullback/reversal）
4. key_levels: 重要な価格レベル（サポート、レジスタンス）
5. ema_positions: EMAの位置関係
6. volatility_condition: ボラティリティ状況（high/medium/low）
7. confidence_factors: 自信度を高める要因
8. risk_factors: リスク要因
9. timeframe_alignment: 時間足の整合性（aligned/mixed/conflicting）
10. entry_timing: エントリータイミング（immediate/wait_for_pullback/wait_for_breakout）
"""
        
        # Use AI to extract structured data
        response = await self.anthropic_service.ask_analysis_question(context)
        
        try:
            # Parse AI response as JSON
            metadata = json.loads(response.get("answer", "{}"))
        except:
            # Fallback to basic extraction if JSON parsing fails
            metadata = self._extract_basic_metadata(forecast)
        
        # Add forecast ID and timestamp
        metadata["forecast_id"] = forecast.id
        metadata["created_at"] = forecast.created_at.isoformat()
        
        return metadata
    
    async def extract_review_learning_data(self, review: ForecastReview) -> Dict[str, Any]:
        """Extract learning data from a review"""
        
        learning_data = {
            "review_id": review.id,
            "forecast_id": review.forecast_id,
            "actual_outcome": review.actual_outcome,
            "accuracy_score": self._calculate_accuracy_score(review),
            "success_factors": [],
            "failure_factors": [],
            "lessons_learned": []
        }
        
        # Extract from review response using AI
        if review.review_response:
            context = f"""
以下のトレードレビューから学習データを抽出してください：

レビュー内容：
{review.review_response}

実際の結果：{review.actual_outcome}
精度メモ：{review.accuracy_notes}

以下の情報をJSON形式で抽出してください：
1. success_factors: 成功要因（リスト形式）
2. failure_factors: 失敗要因（リスト形式）
3. lessons_learned: 学んだ教訓（リスト形式）
4. pattern_effectiveness: パターンの有効性評価
5. timing_accuracy: タイミングの精度
6. risk_management_evaluation: リスク管理の評価
"""
            
            response = await self.anthropic_service.ask_analysis_question(context)
            
            try:
                ai_data = json.loads(response.get("answer", "{}"))
                learning_data.update(ai_data)
            except:
                pass
        
        return learning_data
    
    async def extract_comment_insights(self, comment: ForecastComment) -> Dict[str, Any]:
        """Extract insights from comments and their AI responses"""
        
        insights = {
            "comment_id": comment.id,
            "forecast_id": comment.forecast_id,
            "comment_type": comment.comment_type,
            "is_ai_response": comment.is_ai_response,
            "key_points": [],
            "clarifications": [],
            "additional_insights": []
        }
        
        # Extract insights from Q&A pairs
        if comment.comment_type == "question" and not comment.is_ai_response:
            # Find AI response to this question
            ai_response = self.db.query(ForecastComment).filter(
                and_(
                    ForecastComment.parent_comment_id == comment.id,
                    ForecastComment.is_ai_response == True
                )
            ).first()
            
            if ai_response:
                context = f"""
以下の質問と回答から重要な洞察を抽出してください：

質問：{comment.content}
回答：{ai_response.content}

以下の情報をJSON形式で抽出してください：
1. key_points: 重要なポイント（リスト形式）
2. clarifications: 明確化された事項（リスト形式）
3. additional_insights: 追加の洞察（リスト形式）
4. pattern_refinements: パターン認識の改善点
5. risk_considerations: リスクに関する考慮事項
"""
                
                response = await self.anthropic_service.ask_analysis_question(context)
                
                try:
                    ai_insights = json.loads(response.get("answer", "{}"))
                    insights.update(ai_insights)
                except:
                    pass
        
        return insights
    
    async def compile_learning_data(self, days_back: int = 30) -> Dict[str, Any]:
        """Compile comprehensive learning data from recent activities"""
        
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # Get recent forecasts with reviews
        forecasts_with_reviews = self.db.query(ForecastRequest).join(
            ForecastReview, ForecastRequest.id == ForecastReview.forecast_id
        ).filter(
            ForecastRequest.created_at >= cutoff_date
        ).all()
        
        # Get recent comments
        recent_comments = self.db.query(ForecastComment).filter(
            ForecastComment.created_at >= cutoff_date
        ).all()
        
        # Get trade reviews
        trade_reviews = self.db.query(TradeReview).filter(
            TradeReview.created_at >= cutoff_date
        ).all()
        
        compiled_data = {
            "compilation_date": datetime.now().isoformat(),
            "period": f"last_{days_back}_days",
            "pattern_success_rates": {},
            "successful_patterns": [],
            "failed_patterns": [],
            "common_mistakes": [],
            "best_practices": [],
            "volatility_insights": {},
            "timeframe_insights": {},
            "comment_insights": [],
            "trade_execution_insights": []
        }
        
        # Process forecasts with reviews
        for forecast in forecasts_with_reviews:
            # Extract pattern metadata
            pattern_meta = await self.extract_pattern_metadata(forecast)
            
            # Process associated reviews
            for review in forecast.reviews:
                review_data = await self.extract_review_learning_data(review)
                
                # Aggregate pattern success rates
                patterns = pattern_meta.get("detected_patterns", [])
                outcome = review.actual_outcome
                
                for pattern in patterns:
                    if pattern not in compiled_data["pattern_success_rates"]:
                        compiled_data["pattern_success_rates"][pattern] = {
                            "total": 0,
                            "success": 0,
                            "failure": 0
                        }
                    
                    compiled_data["pattern_success_rates"][pattern]["total"] += 1
                    
                    if outcome in ["long_success", "short_success"]:
                        compiled_data["pattern_success_rates"][pattern]["success"] += 1
                        compiled_data["successful_patterns"].append({
                            "pattern": pattern,
                            "metadata": pattern_meta,
                            "outcome": outcome
                        })
                    else:
                        compiled_data["pattern_success_rates"][pattern]["failure"] += 1
                        compiled_data["failed_patterns"].append({
                            "pattern": pattern,
                            "metadata": pattern_meta,
                            "outcome": outcome,
                            "failure_reasons": review_data.get("failure_factors", [])
                        })
                
                # Collect common mistakes and best practices
                compiled_data["common_mistakes"].extend(review_data.get("failure_factors", []))
                compiled_data["best_practices"].extend(review_data.get("success_factors", []))
        
        # Process comments for insights
        for comment in recent_comments:
            if comment.comment_type == "question" and not comment.is_ai_response:
                insights = await self.extract_comment_insights(comment)
                if insights.get("key_points"):
                    compiled_data["comment_insights"].append(insights)
        
        # Process trade reviews
        for trade_review in trade_reviews:
            execution_insights = {
                "score": trade_review.overall_score,
                "good_points": trade_review.good_points,
                "improvement_points": trade_review.improvement_points,
                "timeframe": trade_review.timeframe,
                "trade_direction": trade_review.trade_direction
            }
            compiled_data["trade_execution_insights"].append(execution_insights)
        
        # Calculate success rates
        for pattern, stats in compiled_data["pattern_success_rates"].items():
            if stats["total"] > 0:
                stats["success_rate"] = stats["success"] / stats["total"]
        
        # Remove duplicates from lists
        compiled_data["common_mistakes"] = list(set(compiled_data["common_mistakes"]))
        compiled_data["best_practices"] = list(set(compiled_data["best_practices"]))
        
        return compiled_data
    
    async def save_learning_data(self, data: Dict[str, Any], filename: Optional[str] = None) -> str:
        """Save learning data to a text file"""
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"learning_data_{timestamp}.txt"
        
        filepath = self.data_dir / filename
        
        # Format data as readable text
        formatted_text = self._format_learning_data(data)
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(formatted_text)
        
        # Also save as JSON for programmatic access
        json_filepath = filepath.with_suffix('.json')
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return str(filepath)
    
    def load_recent_learning_data(self, days: int = 7) -> List[Dict[str, Any]]:
        """Load recent learning data files"""
        
        recent_data = []
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Find JSON files in learning directory
        for json_file in self.data_dir.glob("learning_data_*.json"):
            # Check file modification time
            file_mtime = datetime.fromtimestamp(json_file.stat().st_mtime)
            if file_mtime >= cutoff_date:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    recent_data.append(data)
        
        return recent_data
    
    def get_pattern_success_summary(self) -> str:
        """Get a summary of pattern success rates from accumulated data"""
        
        recent_data = self.load_recent_learning_data(days=30)
        
        if not recent_data:
            return "No recent learning data available"
        
        # Aggregate pattern success rates
        aggregated_patterns = {}
        
        for data in recent_data:
            for pattern, stats in data.get("pattern_success_rates", {}).items():
                if pattern not in aggregated_patterns:
                    aggregated_patterns[pattern] = {
                        "total": 0,
                        "success": 0
                    }
                
                aggregated_patterns[pattern]["total"] += stats.get("total", 0)
                aggregated_patterns[pattern]["success"] += stats.get("success", 0)
        
        # Format summary
        summary_lines = ["【蓄積されたパターン成功率データ】\n"]
        
        for pattern, stats in sorted(aggregated_patterns.items()):
            if stats["total"] > 0:
                success_rate = stats["success"] / stats["total"] * 100
                summary_lines.append(
                    f"- {pattern}: {success_rate:.1f}% "
                    f"(成功{stats['success']}/{stats['total']}回)"
                )
        
        # Add best practices and common mistakes
        all_best_practices = []
        all_common_mistakes = []
        
        for data in recent_data:
            all_best_practices.extend(data.get("best_practices", []))
            all_common_mistakes.extend(data.get("common_mistakes", []))
        
        # Get unique items
        best_practices = list(set(all_best_practices))[:5]
        common_mistakes = list(set(all_common_mistakes))[:5]
        
        if best_practices:
            summary_lines.append("\n【成功要因トップ5】")
            for practice in best_practices:
                summary_lines.append(f"- {practice}")
        
        if common_mistakes:
            summary_lines.append("\n【失敗要因トップ5】")
            for mistake in common_mistakes:
                summary_lines.append(f"- {mistake}")
        
        return "\n".join(summary_lines)
    
    def _extract_basic_metadata(self, forecast: ForecastRequest) -> Dict[str, Any]:
        """Basic metadata extraction without AI"""
        
        metadata = {
            "detected_patterns": [],
            "trend_direction": "unknown",
            "entry_type": "unknown",
            "key_levels": [],
            "confidence_factors": [],
            "risk_factors": []
        }
        
        # Simple pattern detection
        response_lower = forecast.response.lower() if forecast.response else ""
        
        # Detect Kamukamu points
        for i in range(1, 10):
            if f"ポイント{i}" in forecast.response or f"point {i}" in response_lower:
                metadata["detected_patterns"].append(f"ポイント{i}")
        
        # Detect trend
        if "上昇" in forecast.response or "ロング" in forecast.response:
            metadata["trend_direction"] = "up"
        elif "下降" in forecast.response or "ショート" in forecast.response:
            metadata["trend_direction"] = "down"
        
        return metadata
    
    def _calculate_accuracy_score(self, review: ForecastReview) -> float:
        """Calculate accuracy score based on outcome"""
        
        if review.actual_outcome in ["long_success", "short_success"]:
            return 1.0
        elif review.actual_outcome in ["long_failure", "short_failure"]:
            return 0.0
        else:
            return 0.5
    
    def _format_learning_data(self, data: Dict[str, Any]) -> str:
        """Format learning data as readable text"""
        
        lines = [
            "=" * 80,
            "FX予測学習データ",
            f"作成日時: {data.get('compilation_date', 'N/A')}",
            f"期間: {data.get('period', 'N/A')}",
            "=" * 80,
            ""
        ]
        
        # Pattern success rates
        lines.append("【パターン別成功率】")
        for pattern, stats in data.get("pattern_success_rates", {}).items():
            if stats.get("total", 0) > 0:
                success_rate = stats.get("success_rate", 0) * 100
                lines.append(
                    f"  {pattern}: {success_rate:.1f}% "
                    f"(成功{stats.get('success', 0)}/{stats.get('total', 0)}回)"
                )
        lines.append("")
        
        # Best practices
        if data.get("best_practices"):
            lines.append("【成功要因】")
            for practice in data["best_practices"][:10]:
                lines.append(f"  - {practice}")
            lines.append("")
        
        # Common mistakes
        if data.get("common_mistakes"):
            lines.append("【失敗要因】")
            for mistake in data["common_mistakes"][:10]:
                lines.append(f"  - {mistake}")
            lines.append("")
        
        # Trade execution insights
        if data.get("trade_execution_insights"):
            lines.append("【トレード実行の洞察】")
            avg_score = sum(t["score"] for t in data["trade_execution_insights"]) / len(data["trade_execution_insights"])
            lines.append(f"  平均スコア: {avg_score:.1f}/10")
            
            # Common good points
            all_good_points = []
            for trade in data["trade_execution_insights"]:
                all_good_points.extend(trade.get("good_points", []))
            
            if all_good_points:
                lines.append("  よくできた点:")
                for point in list(set(all_good_points))[:5]:
                    lines.append(f"    - {point}")
            lines.append("")
        
        # Comment insights
        if data.get("comment_insights"):
            lines.append("【コメントからの洞察】")
            lines.append(f"  分析されたQ&A数: {len(data['comment_insights'])}")
            
            # Extract key points
            all_key_points = []
            for insight in data["comment_insights"]:
                all_key_points.extend(insight.get("key_points", []))
            
            if all_key_points:
                lines.append("  重要なポイント:")
                for point in list(set(all_key_points))[:10]:
                    lines.append(f"    - {point}")
            lines.append("")
        
        return "\n".join(lines)