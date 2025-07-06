"""Service for updating analysis based on comment insights"""
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.forecast import ForecastRequest, ForecastComment
from app.services import AnthropicService
from app.schemas.analysis_update import AnalysisUpdateRequest, RevisionHistoryItem


class AnalysisUpdateService:
    """Service to handle analysis updates based on comment insights"""
    
    def __init__(self, db: Session):
        self.db = db
        self.anthropic_service = AnthropicService()
    
    async def update_analysis_from_comment(
        self, 
        request: AnalysisUpdateRequest
    ) -> Dict[str, Any]:
        """Update forecast analysis based on comment insights"""
        
        # Get the comment that triggered the update
        comment = self.db.query(ForecastComment).filter(
            ForecastComment.id == request.comment_id
        ).first()
        
        if not comment:
            raise ValueError(f"Comment {request.comment_id} not found")
        
        # Get the forecast
        forecast = self.db.query(ForecastRequest).filter(
            ForecastRequest.id == comment.forecast_id
        ).first()
        
        if not forecast:
            raise ValueError(f"Forecast {comment.forecast_id} not found")
        
        # Save original analysis
        original_analysis = forecast.response
        
        # Get revision history
        revision_history = self._get_revision_history(forecast)
        revision_number = len(revision_history) + 1
        
        # Generate revised analysis
        revised_analysis = await self._generate_revised_analysis(
            original_analysis=original_analysis,
            comment_content=comment.content,
            update_reason=request.update_reason,
            revised_sections=request.revised_sections,
            forecast=forecast
        )
        
        # Update the forecast
        forecast.response = revised_analysis
        
        # Update metadata to track revisions
        metadata = forecast.extra_metadata or {}
        if 'revision_history' not in metadata:
            metadata['revision_history'] = []
        
        metadata['revision_history'].append({
            'revision_number': revision_number,
            'revised_at': datetime.now().isoformat(),
            'revised_by': 'User via comment',
            'comment_id': request.comment_id,
            'update_reason': request.update_reason,
            'changes_summary': request.revised_sections
        })
        
        metadata['last_revised_at'] = datetime.now().isoformat()
        metadata['total_revisions'] = revision_number
        
        forecast.extra_metadata = metadata
        
        # Add a note comment about the update
        update_note = ForecastComment(
            forecast_id=forecast.id,
            parent_comment_id=comment.id,
            comment_type='note',
            content=f"✅ 分析が更新されました（リビジョン {revision_number}）\n\n"
                   f"理由: {request.update_reason}\n\n"
                   f"変更内容:\n" + 
                   '\n'.join([f"• {k}: {v}" for k, v in request.revised_sections.items()]),
            author='System',
            is_ai_response=False,
            extra_metadata={
                'system_action': 'analysis_updated',
                'revision_number': revision_number
            }
        )
        
        self.db.add(update_note)
        self.db.commit()
        self.db.refresh(forecast)
        
        return {
            'forecast_id': forecast.id,
            'original_analysis': original_analysis,
            'revised_analysis': revised_analysis,
            'update_metadata': {
                'revision_number': revision_number,
                'comment_id': request.comment_id,
                'update_reason': request.update_reason,
                'revised_sections': request.revised_sections
            },
            'updated_at': datetime.now()
        }
    
    async def _generate_revised_analysis(
        self,
        original_analysis: str,
        comment_content: str,
        update_reason: str,
        revised_sections: Dict[str, str],
        forecast: ForecastRequest
    ) -> str:
        """Generate revised analysis using AI"""
        
        # Create prompt for AI to revise the analysis
        revision_prompt = f"""
以下の分析を、コメントでの指摘に基づいて修正してください。

【元の分析】
{original_analysis}

【修正理由】
{update_reason}

【コメント内容】
{comment_content}

【修正すべき箇所】
"""
        
        for section, revision in revised_sections.items():
            revision_prompt += f"\n{section}: {revision}"
        
        revision_prompt += """

【重要な指示】
1. 元の分析の構造とフォーマットを維持してください
2. 指定された箇所のみを修正し、他の部分は変更しないでください
3. 修正内容が分析全体と整合性が取れるようにしてください
4. 修正箇所は【修正】マークを付けて明確に示してください

修正後の完全な分析を出力してください。
"""
        
        # Call AI to generate revised analysis
        response = self.anthropic_service.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            temperature=0.3,
            system="あなたはFX分析の専門家です。既存の分析を、新しい洞察に基づいて適切に修正してください。",
            messages=[
                {
                    "role": "user",
                    "content": revision_prompt
                }
            ]
        )
        
        return response.content[0].text
    
    def _get_revision_history(self, forecast: ForecastRequest) -> List[RevisionHistoryItem]:
        """Get revision history from forecast metadata"""
        metadata = forecast.extra_metadata or {}
        history_data = metadata.get('revision_history', [])
        
        history = []
        for item in history_data:
            history.append(RevisionHistoryItem(
                revision_number=item['revision_number'],
                revised_at=datetime.fromisoformat(item['revised_at']),
                revised_by=item['revised_by'],
                comment_id=item.get('comment_id'),
                update_reason=item['update_reason'],
                changes_summary=item['changes_summary']
            ))
        
        return history
    
    def get_analysis_revision_history(self, forecast_id: int) -> List[RevisionHistoryItem]:
        """Get complete revision history for a forecast"""
        forecast = self.db.query(ForecastRequest).filter(
            ForecastRequest.id == forecast_id
        ).first()
        
        if not forecast:
            raise ValueError(f"Forecast {forecast_id} not found")
        
        return self._get_revision_history(forecast)
    
    async def suggest_revisions_from_comment(
        self,
        comment_id: int
    ) -> Dict[str, Any]:
        """Analyze a comment and suggest potential revisions"""
        
        # Get comment
        comment = self.db.query(ForecastComment).filter(
            ForecastComment.id == comment_id
        ).first()
        
        if not comment:
            raise ValueError(f"Comment {comment_id} not found")
        
        # Get forecast
        forecast = self.db.query(ForecastRequest).filter(
            ForecastRequest.id == comment.forecast_id
        ).first()
        
        if not forecast:
            raise ValueError(f"Forecast {comment.forecast_id} not found")
        
        # Use AI to analyze if the comment suggests revisions
        analysis_prompt = f"""
以下のコメントを分析し、元の分析に対する修正が必要かどうか判断してください。

【元の分析】
{forecast.response[:1000]}...

【コメント】
{comment.content}

以下の形式でJSONレスポンスを返してください：
{{
    "needs_revision": true/false,
    "confidence": 0.0-1.0,
    "suggested_reason": "修正理由の説明",
    "suggested_sections": {{
        "セクション名": "修正内容の提案"
    }},
    "explanation": "なぜ修正が必要/不要かの詳細説明"
}}
"""
        
        response = self.anthropic_service.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            temperature=0.2,
            system="分析の修正が必要かどうかを判断する専門家として回答してください。JSONのみを返してください。",
            messages=[
                {
                    "role": "user",
                    "content": analysis_prompt
                }
            ]
        )
        
        try:
            suggestion = json.loads(response.content[0].text)
            suggestion['comment_id'] = comment_id
            suggestion['forecast_id'] = forecast.id
            return suggestion
        except json.JSONDecodeError:
            return {
                "needs_revision": False,
                "confidence": 0.0,
                "explanation": "コメントの分析に失敗しました",
                "comment_id": comment_id,
                "forecast_id": forecast.id
            }