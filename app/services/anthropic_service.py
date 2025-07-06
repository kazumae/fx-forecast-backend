import base64
from typing import List, Tuple, Optional, Dict, Any
from anthropic import Anthropic
from app.core.config import settings
from app.core.prompts import get_full_prompt
from app.core.trade_review_prompts import get_trade_review_prompts


class AnthropicService:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    
    async def analyze_charts_with_timeframes(
        self, 
        images_with_timeframes: List[Tuple[str, bytes]], 
        logic_content: str,
        pattern_context: Optional[str] = None
    ) -> str:
        """Analyze chart images with timeframe labels using Anthropic API"""
        
        # Prepare image messages with timeframe labels
        content = []
        
        # Add introduction
        timeframes_list = [tf for tf, _ in images_with_timeframes]
        content.append({
            "type": "text",
            "text": f"以下のマルチタイムフレームチャートを分析してください。提供された時間足は【{', '.join(timeframes_list)}】です。エントリー時間足は必ずこれらの中から選択してください。"
        })
        
        for timeframe, image_data in images_with_timeframes:
            # Add timeframe label
            content.append({
                "type": "text",
                "text": f"\n【{timeframe}チャート】"
            })
            
            # Convert image to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64_image
                }
            })
        
        # Add analysis request
        content.append({
            "type": "text",
            "text": "\n提供された全ての時間足を総合的に分析し、最適なエントリーポイントと、そのエントリーを実行すべき時間足（1分足でのエントリーか、5分足でのエントリーか等）を明確に指定してください。\n\n重要：かむかむ流の各ポイントの方向性を正確に理解し、適用してください。特にポイント3は「上昇→下降」でショート方向のエントリーポイントです。"
        })
        
        # Get full system prompt with logic
        system_prompt = get_full_prompt(logic_content)
        
        # Add pattern context if provided
        if pattern_context:
            system_prompt += f"\n\n{pattern_context}"
        
        # Call Anthropic API
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            temperature=0.3,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ]
        )
        
        return response.content[0].text
    
    async def analyze_review(
        self, images_with_timeframes: List[Tuple[str, bytes]], review_prompt: str
    ) -> str:
        """Analyze charts for review purposes (not prediction)"""
        
        # Prepare image messages with timeframe labels
        content = []
        
        # Add introduction
        timeframes_list = [tf for tf, _ in images_with_timeframes]
        content.append({
            "type": "text",
            "text": f"以下は検証用のチャート画像です。時間足：【{', '.join(timeframes_list)}】"
        })
        
        for timeframe, image_data in images_with_timeframes:
            # Add timeframe label
            content.append({
                "type": "text",
                "text": f"\n【{timeframe}チャート】"
            })
            
            # Convert image to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64_image
                }
            })
        
        # Call Anthropic API with review-specific system prompt
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            temperature=0.3,
            system=review_prompt,  # Use the review prompt directly
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ]
        )
        
        return response.content[0].text
    
    async def analyze_charts(self, images: List[bytes], logic_content: str) -> str:
        """Analyze chart images using Anthropic API (legacy method)"""
        
        # Prepare image messages
        content = []
        
        for i, image_data in enumerate(images):
            # Convert image to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",  # Assuming JPEG, adjust if needed
                    "data": base64_image
                }
            })
            
            if i == 0:
                content.append({
                    "type": "text",
                    "text": "以下のチャート画像を分析してください。"
                })
        
        # Get full system prompt with logic
        system_prompt = get_full_prompt(logic_content)
        
        # Call Anthropic API
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            temperature=0.3,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ]
        )
        
        return response.content[0].text
    
    async def ask_analysis_question(self, context: str, images_data: List[Tuple[str, bytes]] = None) -> dict:
        """Ask AI a question about a specific analysis"""
        
        # System prompt for Q&A
        system_prompt = """あなたはFX分析の専門家アシスタントです。
提供された分析結果とチャート画像を総合的に参照して、ユーザーの質問に答えてください。

【重要なルール】
1. 分析内容とチャート画像の両方を参照して回答してください
2. 特に複数時間足のチャートがある場合は、全ての時間足を確認し、総合的な視点で回答してください
3. 上位足（4時間足、日足など）は大きなトレンドを把握するために重要なので、必ず確認してください
4. チャートから読み取れる情報（トレンド、サポート/レジスタンス、パターンなど）も含めて回答してください
5. 新たな予測は控えめにし、既存の分析の解説と補足に焦点を当ててください
6. 技術的な根拠を明確に示してください

【回答形式】
- 質問に対する直接的な答えを最初に提示
- チャートから読み取れる根拠を具体的に説明
- 複数時間足の観点がある場合は、それぞれの時間足での見解を示す
- 技術的な用語は分かりやすく説明"""
        
        # Prepare content
        content = []
        
        # Add images if provided
        if images_data:
            content.append({
                "type": "text",
                "text": "以下のチャート画像も参照してください："
            })
            
            for timeframe, image_data in images_data:
                content.append({
                    "type": "text",
                    "text": f"\n【{timeframe}チャート】"
                })
                
                base64_image = base64.b64encode(image_data).decode('utf-8')
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64_image
                    }
                })
        
        # Add the question context
        content.append({
            "type": "text",
            "text": f"\n\n{context}"
        })
        
        # Call Anthropic API
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            temperature=0.5,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ]
        )
        
        answer = response.content[0].text
        
        # Simple confidence estimation based on answer characteristics
        confidence = 0.8  # Default confidence
        if "分析には含まれていません" in answer or "不明" in answer:
            confidence = 0.3
        elif "おそらく" in answer or "可能性" in answer:
            confidence = 0.6
        
        return {
            "answer": answer,
            "confidence": confidence,
            "reasoning": "Based on the provided analysis context"
        }
    
    async def analyze_trade_execution(
        self, image_data: bytes, currency_pair: str, timeframe: str, 
        trade_direction: str = None, additional_context: str = None
    ) -> dict:
        """Analyze actual trade execution with entry points marked"""
        
        # Get trade review prompts
        system_prompt, user_prompt = get_trade_review_prompts()
        
        # Prepare content
        content = []
        
        # Add context
        context_text = f"通貨ペア: {currency_pair}\n時間足: {timeframe}"
        if trade_direction:
            context_text += f"\nトレード方向: {trade_direction}"
        if additional_context:
            context_text += f"\n追加情報: {additional_context}"
        
        content.append({
            "type": "text",
            "text": context_text
        })
        
        # Add image
        base64_image = base64.b64encode(image_data).decode('utf-8')
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64_image
            }
        })
        
        # Add analysis request
        content.append({
            "type": "text",
            "text": user_prompt
        })
        
        # Call Anthropic API
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            temperature=0.4,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ]
        )
        
        # Parse the response
        analysis_text = response.content[0].text
        
        # Extract structured data from the response
        # This is a simplified parser - in production, you might want more robust parsing
        lines = analysis_text.split('\n')
        
        overall_score = 7.0  # Default
        good_points = []
        improvement_points = []
        recommendations = []
        
        current_section = None
        entry_analysis = ""
        technical_analysis = ""
        risk_management = ""
        market_context = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Detect sections
            if "総合評価スコア" in line or "総合スコア" in line:
                # Try to extract score
                import re
                score_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:点|/)', line)
                if score_match:
                    overall_score = float(score_match.group(1))
            elif "エントリーポイント分析" in line:
                current_section = "entry"
            elif "良かった点" in line or "良い点" in line:
                current_section = "good"
            elif "改善すべき点" in line or "改善点" in line:
                current_section = "improvement"
            elif "テクニカル分析" in line:
                current_section = "technical"
            elif "リスク管理" in line:
                current_section = "risk"
            elif "市場環境" in line:
                current_section = "market"
            elif "今後への提言" in line or "提言" in line:
                current_section = "recommendations"
            else:
                # Add content to appropriate section
                if line.startswith('- ') or line.startswith('・'):
                    clean_line = line[2:].strip()
                    if current_section == "good" and clean_line:
                        good_points.append(clean_line)
                    elif current_section == "improvement" and clean_line:
                        improvement_points.append(clean_line)
                    elif current_section == "recommendations" and clean_line:
                        recommendations.append(clean_line)
                elif current_section == "entry":
                    entry_analysis += line + " "
                elif current_section == "technical":
                    technical_analysis += line + " "
                elif current_section == "risk":
                    risk_management += line + " "
                elif current_section == "market":
                    market_context += line + " "
        
        # Ensure we have at least some content
        if not good_points:
            good_points = ["エントリーポイントの選択", "チャート分析の実施"]
        if not improvement_points:
            improvement_points = ["より詳細な分析が必要"]
        if not recommendations:
            recommendations = ["複数時間足での確認を推奨", "リスク管理の明確化"]
        
        return {
            "overall_score": overall_score,
            "entry_analysis": entry_analysis.strip() or "エントリーポイントは矢印で示された位置で実行されています。",
            "good_points": good_points,
            "improvement_points": improvement_points,
            "technical_analysis": technical_analysis.strip() or "チャートパターンとテクニカル指標の分析が必要です。",
            "risk_management": risk_management.strip() or "リスク管理の観点からの評価が必要です。",
            "market_context": market_context.strip() or "市場環境の分析が必要です。",
            "recommendations": recommendations,
            "confidence_level": 0.85,
            "raw_analysis": analysis_text
        }