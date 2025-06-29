import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, List
from src.domain.models.entry_signal import (
    EntrySignal, SignalDirection, SignalConfidence, 
    SignalMetadata, ExecutionInfo
)
from src.domain.models.pattern import PatternSignal
from src.domain.models.scoring import ScoringResult
from src.domain.models.priority_ranking import PriorityRankingResult
from .direction_determiner import DirectionDeterminer
from .price_calculator import PriceCalculator
from .signal_validator import SignalValidator


class EntrySignalGenerator:
    """エントリーシグナル生成器 - 全コンポーネントを統合"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.direction_determiner = DirectionDeterminer()
        self.price_calculator = PriceCalculator(self.config.get("price_config"))
        self.signal_validator = SignalValidator(self.config.get("validation_config"))
    
    def generate_signal(
        self,
        pattern_signal: PatternSignal,
        scoring_result: ScoringResult,
        ranking_result: PriorityRankingResult,
        current_price: Decimal,
        market_data: Dict[str, Any],
        risk_params: Optional[Dict[str, Any]] = None
    ) -> Optional[EntrySignal]:
        """パターンシグナルからエントリーシグナルを生成"""
        
        try:
            # リスクパラメータのデフォルト設定
            risk_params = risk_params or self._get_default_risk_params()
            
            # 1. エントリー方向を決定
            direction = self.direction_determiner.determine_direction(
                pattern_signal, market_data
            )
            
            # 2. パターン詳細を準備
            pattern_details = self._prepare_pattern_details(
                pattern_signal, scoring_result, ranking_result
            )
            
            # 3. エントリー価格を計算
            entry_info = self.price_calculator.calculate_entry_price(
                current_price, direction, pattern_details, market_data
            )
            
            # 4. ストップロスを計算
            stop_loss = self.price_calculator.calculate_stop_loss(
                entry_info.price, direction, pattern_details, risk_params
            )
            
            # 5. テイクプロフィットを計算
            take_profits = self.price_calculator.calculate_take_profits(
                entry_info.price, direction, pattern_details, risk_params
            )
            
            # 6. リスクリワード比を計算
            risk_reward = self.price_calculator.calculate_risk_reward(
                entry_info.price, stop_loss, take_profits
            )
            
            # 7. メタデータを構築
            metadata = self._build_metadata(
                pattern_signal, scoring_result, ranking_result
            )
            
            # 8. 実行情報を構築
            execution_info = self._build_execution_info(
                pattern_signal, ranking_result, risk_params, risk_reward
            )
            
            # 9. シグナルIDを生成
            signal_id = self._generate_signal_id(pattern_signal.symbol)
            
            # 10. エントリーシグナルを構築
            entry_signal = EntrySignal(
                id=signal_id,
                symbol=pattern_signal.symbol,
                timestamp=pattern_signal.detected_at,
                direction=direction,
                entry=entry_info,
                stop_loss=stop_loss,
                take_profits=take_profits,
                risk_reward=risk_reward,
                metadata=metadata,
                execution=execution_info,
                timeframe=pattern_signal.timeframe
            )
            
            # 11. シグナルの検証
            validation_result = self.signal_validator.validate_signal(
                entry_signal, market_data
            )
            
            if not validation_result.is_valid:
                # エラーログを記録（実装では適切なロギングを使用）
                print(f"Signal validation failed: {validation_result.errors}")
                return None
            
            # 警告がある場合はログに記録
            if validation_result.warnings:
                print(f"Signal validation warnings: {validation_result.warnings}")
            
            return entry_signal
            
        except Exception as e:
            # エラーログを記録
            print(f"Error generating entry signal: {str(e)}")
            return None
    
    def _prepare_pattern_details(
        self,
        pattern_signal: PatternSignal,
        scoring_result: ScoringResult,
        ranking_result: PriorityRankingResult
    ) -> Dict[str, Any]:
        """パターン詳細情報を準備"""
        
        details = {
            "symbol": pattern_signal.symbol,
            "pattern_type": pattern_signal.pattern_type.value,
            "immediate_execution": ranking_result.metadata.get("immediate_execution", False),
            "is_power_zone": scoring_result.metadata.get("is_power_zone", False),
            "power_level": scoring_result.metadata.get("power_level", 0)
        }
        
        # パターン固有の詳細をマージ
        if hasattr(pattern_signal, 'details'):
            details.update(pattern_signal.details)
        else:
            details.update(pattern_signal.parameters)
        
        return details
    
    def _build_metadata(
        self,
        pattern_signal: PatternSignal,
        scoring_result: ScoringResult,
        ranking_result: PriorityRankingResult
    ) -> SignalMetadata:
        """シグナルメタデータを構築"""
        
        # 信頼度レベルを決定
        confidence = self._determine_confidence_level(scoring_result.total_score)
        
        # 検出されたパターンのリスト
        detected_patterns = [pattern_signal.pattern_type.value]
        pattern_params = getattr(pattern_signal, 'details', pattern_signal.parameters)
        if "sub_patterns" in pattern_params:
            detected_patterns.extend(pattern_params["sub_patterns"])
        
        return SignalMetadata(
            pattern_type=pattern_signal.pattern_type.value,
            total_score=scoring_result.total_score,
            confidence=confidence,
            priority=ranking_result.priority_rank,
            detected_patterns=detected_patterns,
            zone_id=pattern_signal.zone_id,
            source_indicators=pattern_params.get("indicators"),
            market_conditions=scoring_result.metadata.get("market_conditions")
        )
    
    def _build_execution_info(
        self,
        pattern_signal: PatternSignal,
        ranking_result: PriorityRankingResult,
        risk_params: Dict[str, Any],
        risk_reward: Any
    ) -> ExecutionInfo:
        """実行情報を構築"""
        
        # 推奨ロットサイズを計算
        recommended_size = self._calculate_recommended_size(
            risk_params, risk_reward.risk_pips
        )
        
        # 最大リスク金額
        max_risk_amount = risk_params.get("max_risk_amount", 100.0)
        
        # エントリー方法
        if ranking_result.metadata.get("immediate_execution", False):
            entry_method = "market"
            urgency = "immediate"
        else:
            entry_method = "limit"
            urgency = "normal"
        
        # 特別な実行指示
        special_instructions = []
        if ranking_result.metadata.get("bypass_correlation", False):
            special_instructions.append("bypass_correlation_check")
        if pattern_signal.confidence > 80:  # 0-100スケール
            special_instructions.append("high_confidence_trade")
        
        return ExecutionInfo(
            recommended_size=recommended_size,
            max_risk_amount=max_risk_amount,
            entry_method=entry_method,
            urgency=urgency,
            special_instructions=special_instructions if special_instructions else None
        )
    
    def _determine_confidence_level(self, total_score: float) -> SignalConfidence:
        """スコアから信頼度レベルを決定"""
        
        if total_score >= 85:
            return SignalConfidence.VERY_HIGH
        elif total_score >= 70:
            return SignalConfidence.HIGH
        elif total_score >= 50:
            return SignalConfidence.MEDIUM
        else:
            return SignalConfidence.LOW
    
    def _calculate_recommended_size(
        self, 
        risk_params: Dict[str, Any],
        risk_pips: float
    ) -> float:
        """推奨ロットサイズを計算"""
        
        # アカウントリスク率
        risk_percentage = risk_params.get("risk_percentage", 1.0)  # 1%
        account_balance = risk_params.get("account_balance", 10000)  # $10,000
        
        # リスク金額
        risk_amount = account_balance * (risk_percentage / 100)
        
        # ピップ価値（XAUUSDの場合、1ロット = $10/pip）
        pip_value_per_lot = risk_params.get("pip_value_per_lot", 10.0)
        
        # 推奨ロットサイズ
        if risk_pips > 0:
            recommended_size = risk_amount / (risk_pips * pip_value_per_lot)
        else:
            recommended_size = 0.1  # デフォルト
        
        # 最小/最大制限
        min_lot = risk_params.get("min_lot_size", 0.01)
        max_lot = risk_params.get("max_lot_size", 5.0)
        
        # 小数点以下2桁に丸める
        recommended_size = round(max(min_lot, min(recommended_size, max_lot)), 2)
        
        return recommended_size
    
    def _generate_signal_id(self, symbol: str) -> str:
        """ユニークなシグナルIDを生成"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_part = str(uuid.uuid4())[:8]
        
        return f"entry_{timestamp}_{symbol}_{unique_part}"
    
    def _get_default_risk_params(self) -> Dict[str, Any]:
        """デフォルトのリスクパラメータを取得"""
        
        return {
            "risk_percentage": 1.0,  # 1%リスク
            "account_balance": 10000,  # $10,000
            "pip_value_per_lot": 10.0,  # XAUUSD
            "min_lot_size": 0.01,
            "max_lot_size": 5.0,
            "max_risk_amount": 100.0,  # $100
            "default_sl_pips": 20.0,
            "tp_levels": [
                {"ratio": 1.0, "percentage": 50},
                {"ratio": 1.5, "percentage": 30},
                {"ratio": 2.0, "percentage": 20}
            ],
            "enable_trailing": False,
            "volatility_factor": 1.0
        }
    
    def generate_batch_signals(
        self,
        pattern_signals: List[PatternSignal],
        scoring_results: Dict[str, ScoringResult],
        ranking_results: Dict[str, PriorityRankingResult],
        market_data: Dict[str, Any],
        risk_params: Optional[Dict[str, Any]] = None
    ) -> List[EntrySignal]:
        """複数のパターンシグナルから一括でエントリーシグナルを生成"""
        
        entry_signals = []
        
        for pattern_signal in pattern_signals:
            signal_key = pattern_signal.id
            
            # 対応するスコアリング結果と優先順位結果を取得
            scoring_result = scoring_results.get(signal_key)
            ranking_result = ranking_results.get(signal_key)
            
            if not scoring_result or not ranking_result:
                continue
            
            # 現在価格を取得
            current_price = Decimal(str(market_data.get("current_price", 0)))
            
            if current_price <= 0:
                continue
            
            # シグナルを生成
            entry_signal = self.generate_signal(
                pattern_signal,
                scoring_result,
                ranking_result,
                current_price,
                market_data,
                risk_params
            )
            
            if entry_signal:
                entry_signals.append(entry_signal)
        
        return entry_signals