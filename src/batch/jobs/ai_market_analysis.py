"""
AI市場分析バッチジョブ
"""
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import json
import os
import fcntl
import tempfile

from src.batch.base import BaseBatchJob
from src.services.analysis.data_collector import AnalysisDataCollector
from src.services.analysis.anthropic_client import AnthropicAnalysisClient
from src.services.analysis.slack_formatter import SlackAnalysisFormatter
from src.batch.utils.slack_notifier import SlackNotifier
from src.db.session import AsyncSessionLocal


class AIMarketAnalysisJob(BaseBatchJob):
    """AI市場分析バッチジョブ"""
    
    def __init__(self):
        super().__init__(job_name="ai_market_analysis")
        self.data_collector = None  # 実行時に初期化
        self.ai_client = None  # 実行時に初期化
        self.async_session = None  # 実行時に初期化
        self.slack_formatter = SlackAnalysisFormatter()
        self.slack_notifier = SlackNotifier()
        
    async def _initialize_services(self):
        """サービスの初期化（DB接続が必要なため実行時に行う）"""
        if not self.data_collector:
            self.async_session = AsyncSessionLocal()
            self.data_collector = AnalysisDataCollector(self.async_session)
        if not self.ai_client:
            try:
                self.ai_client = AnthropicAnalysisClient()
            except ValueError as e:
                self.logger.error(f"Failed to initialize Anthropic client: {e}")
                raise
        
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """バッチジョブの実行
        
        Args:
            **kwargs: 実行時パラメータ
                - symbol: 分析対象通貨ペア（デフォルト: XAUUSD）
                - dry_run: ドライラン（通知を送らない）
                
        Returns:
            実行結果
        """
        symbol = kwargs.get("symbol", "XAUUSD")
        dry_run = kwargs.get("dry_run", False)
        
        # ロックファイルパスを作成
        lock_file_path = os.path.join(tempfile.gettempdir(), f"ai_market_analysis_{symbol}.lock")
        
        # 排他制御
        try:
            lock_file = open(lock_file_path, 'w')
            fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.logger.info(f"Lock acquired for {symbol} analysis")
        except IOError:
            self.logger.warning(f"Another AI analysis for {symbol} is already running. Skipping this execution.")
            return {
                "success": False,
                "error": "Another analysis is already in progress",
                "symbol": symbol
            }
        
        try:
            # サービスを初期化
            await self._initialize_services()
            # 1. データ収集
            self.logger.info(f"Collecting data for {symbol}...")
            market_data = await self.data_collector.collect_all_data(symbol)
            
            if not market_data:
                raise ValueError("No market data collected")
            
            # 2. AI分析
            self.logger.info("Analyzing market with AI...")
            analysis_result = await self._analyze_with_ai(market_data)
            
            if not analysis_result["success"]:
                raise ValueError(f"AI analysis failed: {analysis_result.get('error')}")
            
            # 3. 分析結果のパース
            parsed_analysis = self._parse_analysis_result(analysis_result["content"])
            parsed_analysis["symbol"] = symbol
            parsed_analysis["timestamp"] = datetime.now(timezone.utc).isoformat()
            
            # 4. Slack通知の送信
            if not dry_run:
                await self._send_slack_notification(parsed_analysis)
            
            # 実行詳細の設定
            self.set_execution_detail("symbol", symbol)
            self.set_execution_detail("importance", parsed_analysis.get("importance", "INFO"))
            self.set_execution_detail("trend", parsed_analysis.get("trend", "unknown"))
            self.set_execution_detail("signal_count", len(parsed_analysis.get("signals", [])))
            self.set_execution_detail("dry_run", dry_run)
            self.set_execution_detail("ai_tokens_used", analysis_result["usage"]["total_tokens"])
            
            return {
                "success": True,
                "symbol": symbol,
                "analysis": parsed_analysis,
                "data_collected": self._summarize_collected_data(market_data),
                "ai_usage": analysis_result["usage"]
            }
            
        except Exception as e:
            self.logger.error(f"AI market analysis failed: {str(e)}")
            
            # エラー通知
            if not dry_run:
                await self._send_error_notification(e, {"symbol": symbol})
            
            raise
        
        finally:
            # Async session cleanup
            if hasattr(self, 'async_session') and self.async_session:
                await self.async_session.close()
            
            # ロックファイルの解放
            try:
                fcntl.lockf(lock_file, fcntl.LOCK_UN)
                lock_file.close()
                os.remove(lock_file_path)
                self.logger.info(f"Lock released for {symbol} analysis")
            except Exception as e:
                self.logger.warning(f"Failed to release lock: {e}")
    
    async def _analyze_with_ai(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """AIによる市場分析
        
        Args:
            market_data: 収集した市場データ
            
        Returns:
            AI分析結果
        """
        system_prompt = """
あなたは金（XAUUSD）取引で実際にポジションを持つプロトレーダーです。エントリーする前提で明確な判断を下してください。
「上がるかもしれないし下がるかもしれない」といった曖昧な分析は不要です。今エントリーするならどちらか、具体的なレベルと根拠を示してください。

重要：レスポンスは有効なJSONオブジェクトのみを返し、```json```ブロックや説明文は含めないでください。

## 分析の基本姿勢
- エントリーする前提で分析する
- 明確な方向性を示す（BUYかSELLか）
- 具体的な価格レベルを提示
- リスクリワード比を明示
- エントリーしない場合は「待つべき理由と条件」を明確に

## 重視すべきポイント
1. EMAの並び順とローソク足の位置関係
   - パーフェクトオーダーの方向
   - EMAブレイクアウト/プルバックの状況
   - 直近のEMAタッチからの反応

2. 価格アクション
   - 直近高値/安値のブレイク
   - サポート/レジスタンスでの反応
   - ローソク足パターン（ピンバー、エンゴルフィング等）

3. マルチタイムフレーム分析
   - 上位足のトレンド方向
   - 下位足でのエントリータイミング

4. リスク管理
   - 明確なストップロス位置
   - 現実的なターゲット価格
   - ポジションサイズ

レスポンスは以下の構造の有効なJSONオブジェクトである必要があります：
{
    "importance": "INFO|WARNING|ALERT",
    "executive_summary": "今すぐエントリーするならどうするか。明確な判断と根拠（日本語）",
    "trend": "強気|弱気|中立",
    "short_term_trend": "1-4時間の具体的な見通し（日本語）",
    "medium_term_trend": "本日〜明日の具体的な見通し（日本語）", 
    "long_term_trend": "今週の具体的な見通し（日本語）",
    "signals": [
        {
            "type": "BUY|SELL|WAIT",
            "confidence": 0.0-1.0,
            "entry_price": number,
            "stop_loss": number,
            "take_profit": number,
            "risk_reward": "例: 1:2.5",
            "pattern": "エントリー根拠となるパターン（日本語）"
        }
    ],
    "risk_assessment": {
        "level": "低|中|高",
        "volatility": "現在のボラティリティ状況（日本語）",
        "key_risks": ["具体的なリスク1", "具体的なリスク2", "具体的なリスク3"],
        "position_size": "推奨ロット数または%",
        "max_loss": "具体的な最大損失額"
    },
    "recommendations": ["具体的な行動1", "具体的な行動2", "具体的な行動3"],
    "detailed_analysis": {
        "ema_analysis": {
            "price_position": "現在価格とEMAの具体的な位置関係",
            "ema_trend": "EMAが示す明確な方向性",
            "ema_spacing": "EMA間隔から読み取れる相場の勢い",
            "crossover_status": "直近のクロスオーバーと今後の可能性"
        },
        "support_resistance": {
            "key_levels": "トレードに使える具体的な価格帯",
            "nearest_support": "エントリー/ストップに使える直近サポート",
            "nearest_resistance": "ターゲットに使える直近レジスタンス",
            "level_strength": "各レベルの信頼度（強/中/弱）"
        },
        "entry_rationale": {
            "primary_reason": "エントリーする最大の理由",
            "confirmation_signals": "エントリーを裏付ける追加シグナル",
            "invalidation_level": "このシナリオが崩れる具体的な価格"
        }
    }
}

重要度の設定基準：
- INFO: エントリーチャンスなし、様子見推奨
- WARNING: エントリー準備、条件が揃いつつある
- ALERT: 今すぐエントリーすべき明確なチャンス
"""
        
        # 現在の市場セッションを判定
        current_time = datetime.now(timezone.utc)
        current_hour = current_time.hour
        
        active_sessions = []
        if 0 <= current_hour < 9:
            active_sessions.append("東京")
        if 8 <= current_hour < 17:
            active_sessions.append("ロンドン")
        if 13 <= current_hour < 22:
            active_sessions.append("ニューヨーク")
        
        session_info = f"現在開いている市場: {', '.join(active_sessions) if active_sessions else '市場クローズ時間'}"
        
        user_prompt = f"""
{market_data.get('symbol', 'XAUUSD')}の以下の市場データを分析してください：

現在時刻（UTC）: {current_time.strftime('%Y-%m-%d %H:%M:%S')}
{session_info}

現在の市場データ:
{json.dumps(market_data.get('market_data', {}), indent=2)}

最近のローソク足データ:
{self._format_candlesticks(market_data.get('candlesticks', []))}

テクニカル指標:
{self._format_indicators(market_data.get('indicators', []))}

最近のシグナル:
{self._format_signals(market_data.get('signals', []))}

今すぐトレードする前提で、以下の観点から明確な判断を下してください：

【エントリー判断】
今この瞬間にポジションを持つなら：
- BUY/SELL/WAITのどれか明確に
- エントリー価格（現在価格付近の具体的な数値）
- ストップロス価格（リスクを限定する具体的な数値）
- テイクプロフィット価格（現実的な利確目標）
- なぜ今エントリーすべきか（または待つべきか）の明確な理由

【テクニカル根拠】
1. EMAの状況
   - 価格は75EMAを上抜けたか下抜けたか
   - パーフェクトオーダーは上昇/下降どちらに傾いているか
   - 直近のEMAブレイクやタッチでの反応

2. 価格アクション
   - 直近の高値/安値ブレイクの有無
   - ローソク足パターン（あれば具体名）
   - サポート/レジスタンスでの反応

3. マルチタイムフレーム
   - 4時間足の方向性
   - 1時間足の状況
   - 15分足のエントリータイミング

【リスク管理】
- 最大損失額（ドル単位）
- 推奨ポジションサイズ
- シナリオが崩れる具体的な価格

重要：「上がるかもしれないし下がるかもしれない」は禁句です。
プロトレーダーとして、今どうするか明確に判断してください。
"""
        
        return await self.ai_client.analyze_market(system_prompt, user_prompt)
    
    def _format_candlesticks(self, candlesticks) -> str:
        """ローソク足データのフォーマット"""
        if not candlesticks:
            return "No candlestick data available"
        
        # candlesticks が辞書の場合（時間枠ごと）
        if isinstance(candlesticks, dict):
            formatted = []
            for timeframe, candle_list in candlesticks.items():
                if candle_list:
                    # 最新のローソク足のみ使用
                    latest_candle = candle_list[-1] if candle_list else {}
                    if isinstance(latest_candle, dict):
                        formatted.append(
                            f"{timeframe}: "
                            f"O: {latest_candle.get('open', 0):.2f}, "
                            f"H: {latest_candle.get('high', 0):.2f}, "
                            f"L: {latest_candle.get('low', 0):.2f}, "
                            f"C: {latest_candle.get('close', 0):.2f}"
                        )
            return "\n".join(formatted) if formatted else "No candlestick data available"
        
        return "No candlestick data available"
    
    def _format_indicators(self, indicators) -> str:
        """テクニカル指標のフォーマット"""
        if not indicators:
            return "No indicator data available"
        
        # indicators が辞書の場合（時間枠ごと）
        if isinstance(indicators, dict):
            formatted = []
            for timeframe, ind_data in indicators.items():
                if isinstance(ind_data, dict):
                    formatted.append(
                        f"{timeframe}: "
                        f"RSI: {ind_data.get('rsi', 'N/A')}, "
                        f"EMA20: {ind_data.get('ema_20', 'N/A')}, "
                        f"MACD: {ind_data.get('macd', 'N/A')}"
                    )
            return "\n".join(formatted) if formatted else "No indicator data available"
        
        return "No indicator data available"
    
    def _format_signals(self, signals) -> str:
        """シグナル履歴のフォーマット"""
        if not signals:
            return "No recent signals"
        
        if isinstance(signals, list):
            # 最新3件のみ使用
            recent_signals = signals[:3] if len(signals) > 3 else signals
            
            formatted = []
            for signal in recent_signals:
                if isinstance(signal, dict):
                    formatted.append(
                        f"Time: {signal.get('timestamp', 'N/A')}, "
                        f"Type: {signal.get('signal_type', 'N/A')}, "
                        f"Score: {signal.get('confidence_score', 0):.2f}"
                    )
            return "\n".join(formatted) if formatted else "No recent signals"
        
        return "No recent signals"
    
    def _parse_analysis_result(self, content: str) -> Dict[str, Any]:
        """AI分析結果のパース
        
        Args:
            content: AI応答内容
            
        Returns:
            パースされた分析結果
        """
        try:
            # JSONとして直接パース
            return json.loads(content)
        except json.JSONDecodeError:
            # ```json ブロックを抽出してパース
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse extracted JSON: {e}")
            
            # { } で囲まれた最初のJSONブロックを抽出
            json_start = content.find('{')
            if json_start != -1:
                # ネストした{}を考慮してJSONの終端を見つける
                brace_count = 0
                json_end = json_start
                for i, char in enumerate(content[json_start:], json_start):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                if json_end > json_start:
                    try:
                        json_content = content[json_start:json_end]
                        return json.loads(json_content)
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Failed to parse extracted JSON block: {e}")
            
            # すべて失敗した場合はフォールバック
            self.logger.warning("Failed to parse AI response as JSON, using fallback")
            return {
                "importance": "INFO",
                "executive_summary": content[:500] + "...",
                "trend": "neutral",
                "signals": [],
                "risk_assessment": {"level": "medium"},
                "recommendations": ["Manual review required"],
                "detailed_analysis": {"raw_response": content}
            }
    
    async def _send_slack_notification(self, analysis: Dict[str, Any]) -> None:
        """Slack通知の送信
        
        Args:
            analysis: 分析結果
        """
        # フォーマット
        message = self.slack_formatter.format_analysis_report(analysis)
        
        # SlackNotifierの適切なメソッドを使用
        if hasattr(self.slack_notifier, 'send_webhook_message') and message.get("attachments"):
            # Webhook経由で送信（attachments対応）
            success = self.slack_notifier.send_webhook_message(
                text=message["text"],
                attachments=message.get("attachments")
            )
        else:
            # Web API経由で送信（blocks対応）
            success = self.slack_notifier.send_message(
                channel=message["channel"],
                text=message["text"],
                blocks=message.get("blocks")
            )
        
        if success:
            self.logger.info(f"Sent analysis notification to {message['channel']}")
        else:
            self.logger.warning("Failed to send Slack notification")
    
    async def _send_error_notification(self, error: Exception, context: Dict[str, Any]) -> None:
        """エラー通知の送信
        
        Args:
            error: 発生したエラー
            context: エラーコンテキスト
        """
        message = self.slack_formatter.format_error_notification(error, context)
        
        # SlackNotifierの適切なメソッドを使用
        if hasattr(self.slack_notifier, 'send_webhook_message') and message.get("attachments"):
            self.slack_notifier.send_webhook_message(
                text=message["text"],
                attachments=message.get("attachments")
            )
        else:
            self.slack_notifier.send_message(
                channel=message["channel"],
                text=message["text"],
                blocks=message.get("blocks")
            )
    
    def _summarize_collected_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """収集データのサマリー作成"""
        return {
            "has_market_data": bool(data.get("market_data")),
            "candlestick_count": len(data.get("candlesticks", [])),
            "indicator_count": len(data.get("indicators", [])),
            "signal_count": len(data.get("signals", [])),
            "latest_price": data.get("market_data", {}).get("current_price")
        }