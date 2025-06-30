"""
Anthropic Claude API クライアント
"""
from anthropic import AsyncAnthropic
from typing import Optional, Dict, Any, List
import os
from datetime import datetime, timezone
import logging
import asyncio
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RateLimitInfo:
    """レート制限情報"""
    requests_per_minute: int = 50
    request_times: List[datetime] = None
    
    def __post_init__(self):
        if self.request_times is None:
            self.request_times = []


class AnthropicAnalysisClient:
    """Anthropic Claude API クライアント"""
    
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
            
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")
        self.max_tokens = 4096
        self.temperature = 0.7
        self.rate_limiter = RateLimitInfo()
        
    async def analyze_market(
        self, 
        system_prompt: str, 
        user_prompt: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """市場分析リクエストを送信
        
        Args:
            system_prompt: システムプロンプト
            user_prompt: ユーザープロンプト
            max_retries: 最大リトライ回数
            
        Returns:
            分析結果の辞書
        """
        # レート制限チェック
        await self._wait_for_rate_limit()
        
        for attempt in range(max_retries):
            try:
                # API呼び出し
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )
                
                # レート制限記録
                self._record_request()
                
                # レスポンス処理
                content = response.content[0].text if response.content else ""
                
                return {
                    "success": True,
                    "content": content,
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                        "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                    },
                    "model": response.model,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "attempt": attempt + 1
                }
                
            except Exception as e:
                logger.error(f"API call failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                
                if attempt < max_retries - 1:
                    # エクスポネンシャルバックオフ
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    return {
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "attempts": max_retries
                    }
    
    async def validate_api_key(self) -> bool:
        """APIキーの検証
        
        Returns:
            有効な場合True
        """
        try:
            # 最小限のリクエストでAPIキーを検証
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
            return True
        except Exception as e:
            logger.error(f"API key validation failed: {str(e)}")
            return False
    
    async def _wait_for_rate_limit(self):
        """レート制限に基づいて待機"""
        now = datetime.now(timezone.utc)
        
        # 1分以上前のリクエストを削除
        self.rate_limiter.request_times = [
            t for t in self.rate_limiter.request_times 
            if (now - t).total_seconds() < 60
        ]
        
        # レート制限チェック
        if len(self.rate_limiter.request_times) >= self.rate_limiter.requests_per_minute:
            # 最も古いリクエストから1分経過するまで待機
            oldest_request = self.rate_limiter.request_times[0]
            wait_seconds = 60 - (now - oldest_request).total_seconds()
            
            if wait_seconds > 0:
                logger.info(f"Rate limit reached. Waiting {wait_seconds:.1f} seconds...")
                await asyncio.sleep(wait_seconds)
    
    def _record_request(self):
        """リクエストを記録"""
        self.rate_limiter.request_times.append(datetime.now(timezone.utc))
    
    def get_token_cost(self, usage: Dict[str, int]) -> float:
        """トークン使用量からコストを計算
        
        Args:
            usage: トークン使用量の辞書
            
        Returns:
            推定コスト（USD）
        """
        # Claude 3 Opus の価格（2024年6月時点）
        # Input: $15 per million tokens
        # Output: $75 per million tokens
        input_cost = (usage.get("input_tokens", 0) / 1_000_000) * 15
        output_cost = (usage.get("output_tokens", 0) / 1_000_000) * 75
        
        return input_cost + output_cost