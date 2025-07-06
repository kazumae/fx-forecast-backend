"""Service for managing review metadata"""
import json
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.forecast import ForecastReview
from app.services import AnthropicService
from app.core.metadata_prompts import get_metadata_extraction_prompt


class MetadataService:
    def __init__(self):
        self.anthropic_service = AnthropicService()
    
    async def extract_metadata_from_review(self, review_content: str) -> Dict:
        """Extract structured metadata from review content using AI"""
        prompt = get_metadata_extraction_prompt(review_content)
        
        # Call Anthropic API for metadata extraction
        response = self.anthropic_service.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            temperature=0.1,  # Low temperature for consistent JSON output
            system="You are a metadata extraction specialist. Always respond with valid JSON only, no additional text.",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        # Parse JSON response
        try:
            metadata_text = response.content[0].text
            # Clean up the response to ensure valid JSON
            if "```json" in metadata_text:
                metadata_text = metadata_text.split("```json")[1].split("```")[0]
            elif "```" in metadata_text:
                metadata_text = metadata_text.split("```")[1].split("```")[0]
            
            metadata = json.loads(metadata_text.strip())
            return metadata
        except json.JSONDecodeError:
            # Fallback to basic metadata if parsing fails
            return {
                "pattern": {"result": "unknown"},
                "statistics": {"total_score": 0},
                "key_takeaway": "Metadata extraction failed"
            }
    
    def get_recent_metadata(self, db: Session, limit: int = 10) -> List[Dict]:
        """Get recent review metadata for context"""
        reviews = db.query(ForecastReview)\
                   .filter(ForecastReview.review_metadata.isnot(None))\
                   .order_by(desc(ForecastReview.created_at))\
                   .limit(limit)\
                   .all()
        
        return [review.review_metadata for review in reviews if review.review_metadata]
    
    def aggregate_metadata_summary(self, metadata_list: List[Dict]) -> Dict:
        """Aggregate multiple metadata into a summary"""
        if not metadata_list:
            return {}
        
        # Calculate statistics
        total_reviews = len(metadata_list)
        successful_reviews = sum(1 for m in metadata_list if m.get("pattern", {}).get("result") == "success")
        
        # Collect common patterns
        success_factors = []
        failure_factors = []
        caution_zones = set()
        
        for metadata in metadata_list:
            lessons = metadata.get("lessons", {})
            success_factors.extend(lessons.get("success_factors", []))
            failure_factors.extend(lessons.get("failure_factors", []))
            caution_zones.update(lessons.get("caution_zones", []))
        
        # Count pattern frequencies
        pattern_counts = {}
        for metadata in metadata_list:
            pattern = metadata.get("pattern", {}).get("kamukamu_point", "unknown")
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        
        return {
            "total_reviews": total_reviews,
            "success_rate": (successful_reviews / total_reviews * 100) if total_reviews > 0 else 0,
            "common_success_factors": list(set(success_factors))[:5],  # Top 5 unique factors
            "common_failure_factors": list(set(failure_factors))[:5],
            "caution_zones": list(caution_zones),
            "pattern_usage": pattern_counts,
            "average_score": sum(m.get("statistics", {}).get("total_score", 0) for m in metadata_list) / total_reviews if total_reviews > 0 else 0
        }
    
    def format_metadata_for_prompt(self, metadata_summary: Dict) -> str:
        """Format metadata summary for inclusion in analysis prompts"""
        if not metadata_summary:
            return ""
        
        formatted = "\n【過去の分析実績からの学習】\n"
        formatted += f"※直近{metadata_summary.get('total_reviews', 0)}件の検証結果より\n\n"
        
        if metadata_summary.get('success_rate', 0) > 0:
            formatted += f"成功率: {metadata_summary['success_rate']:.1f}%\n"
        
        if metadata_summary.get('common_success_factors'):
            formatted += "\n成功パターン:\n"
            for factor in metadata_summary['common_success_factors']:
                formatted += f"- {factor}\n"
        
        if metadata_summary.get('common_failure_factors'):
            formatted += "\n失敗パターン:\n"
            for factor in metadata_summary['common_failure_factors']:
                formatted += f"- {factor}\n"
        
        if metadata_summary.get('caution_zones'):
            formatted += f"\n要注意価格帯: {', '.join(metadata_summary['caution_zones'])}\n"
        
        if metadata_summary.get('pattern_usage'):
            formatted += "\n使用頻度の高いパターン:\n"
            for pattern, count in sorted(metadata_summary['pattern_usage'].items(), key=lambda x: x[1], reverse=True)[:3]:
                formatted += f"- {pattern}: {count}回\n"
        
        return formatted