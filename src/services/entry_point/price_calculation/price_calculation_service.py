from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from src.domain.models.price_calculation import (
    PriceCalculationInput, PriceCalculationResult, StopLossCalculation,
    TakeProfitLevel, RiskRewardAnalysis, PriceAdjustments
)
from src.domain.models.entry_signal import SignalDirection
from .stop_loss_calculator import StopLossCalculator
from .take_profit_calculator import TakeProfitCalculator
from .risk_reward_validator import RiskRewardValidator
from .special_case_handler import SpecialCaseHandler


class PriceCalculationService:
    """価格計算統合サービス"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # 各計算器を初期化
        self.sl_calculator = StopLossCalculator(self.config.get("stop_loss", {}))
        self.tp_calculator = TakeProfitCalculator(self.config.get("take_profit", {}))
        self.rr_validator = RiskRewardValidator(self.config.get("risk_reward", {}))
        self.special_handler = SpecialCaseHandler(self.config.get("special_cases", {}))
        
        # デフォルト設定
        self.min_sl_pips = self.config.get("min_sl_pips", 10.0)
        self.max_sl_pips = self.config.get("max_sl_pips", 50.0)
        self.min_rr_ratio = self.config.get("min_rr_ratio", 1.5)
    
    def calculate_price_levels(
        self,
        entry_price: Decimal,
        pattern_type: str,
        direction: SignalDirection,
        current_atr: float,
        zone_info: Dict[str, Any],
        market_data: Optional[Dict[str, Any]] = None
    ) -> PriceCalculationResult:
        """価格レベルを総合的に計算"""
        
        # 入力データを準備
        input_data = PriceCalculationInput(
            entry_price=entry_price,
            pattern_type=pattern_type,
            current_atr=current_atr,
            zone_info=zone_info,
            volatility_level=market_data.get("volatility_level", "normal") if market_data else "normal",
            existing_positions=market_data.get("existing_positions", []) if market_data else [],
            market_session=market_data.get("market_session", "london") if market_data else "london",
            news_impact=market_data.get("news_impact", False) if market_data else False
        )
        
        # スイングポイントとゾーン情報を取得
        swing_points = market_data.get("swing_points", []) if market_data else []
        nearby_zones = market_data.get("nearby_zones", []) if market_data else []
        
        # 1. ストップロスを計算
        stop_loss = self.sl_calculator.calculate_stop_loss(
            input_data, direction, swing_points
        )
        
        # 2. テイクプロフィットを計算
        take_profits = self.tp_calculator.calculate_take_profits(
            input_data, direction, stop_loss.distance_pips, nearby_zones
        )
        
        # 3. リスクリワード比を検証
        rr_analysis = self.rr_validator.validate_and_analyze(
            stop_loss, take_profits, entry_price, direction
        )
        
        # 4. RR比が不足している場合は調整
        if not rr_analysis.meets_minimum:
            stop_loss, take_profits = self.rr_validator.adjust_for_minimum_rr(
                stop_loss, take_profits, entry_price, direction, input_data
            )
            # 再度分析
            rr_analysis = self.rr_validator.validate_and_analyze(
                stop_loss, take_profits, entry_price, direction
            )
        
        # 5. 特殊ケースの調整を適用
        adjusted_sl, adjusted_tps, adjustments = self.special_handler.apply_adjustments(
            stop_loss, take_profits,
            {
                "current_atr": current_atr,
                "market_session": input_data.market_session,
                "news_impact": input_data.news_impact,
                "news_events": market_data.get("news_events", []) if market_data else [],
                "existing_positions": input_data.existing_positions,
                "entry_price": entry_price,
                "direction": direction,
                "symbol": market_data.get("symbol", "XAUUSD") if market_data else "XAUUSD"
            }
        )
        
        # 6. 最終的なRR分析
        final_rr_analysis = self.rr_validator.validate_and_analyze(
            adjusted_sl, adjusted_tps, entry_price, direction
        )
        
        # 7. 結果を構築
        result = PriceCalculationResult(
            stop_loss=adjusted_sl,
            take_profits=adjusted_tps,
            risk_reward_analysis=final_rr_analysis,
            adjustments=adjustments,
            calculated_at=datetime.now(timezone.utc)
        )
        
        return result
    
    def validate_price_levels(
        self,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        take_profit_prices: List[Decimal],
        direction: SignalDirection
    ) -> Dict[str, Any]:
        """既存の価格レベルを検証"""
        
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": []
        }
        
        # SL距離を計算
        sl_distance_pips = abs(float(entry_price - stop_loss_price)) * 10000
        
        # 1. SL位置の検証
        if direction == SignalDirection.LONG:
            if stop_loss_price >= entry_price:
                validation_result["is_valid"] = False
                validation_result["errors"].append("ロングポジションのSLはエントリー価格より低い必要があります")
        else:
            if stop_loss_price <= entry_price:
                validation_result["is_valid"] = False
                validation_result["errors"].append("ショートポジションのSLはエントリー価格より高い必要があります")
        
        # 2. SL距離の検証
        if sl_distance_pips < self.min_sl_pips:
            validation_result["warnings"].append(f"SL距離が最小値({self.min_sl_pips}pips)を下回っています")
        elif sl_distance_pips > self.max_sl_pips:
            validation_result["warnings"].append(f"SL距離が最大値({self.max_sl_pips}pips)を上回っています")
        
        # 3. TP位置の検証
        for i, tp_price in enumerate(take_profit_prices):
            tp_distance_pips = abs(float(entry_price - tp_price)) * 10000
            
            if direction == SignalDirection.LONG:
                if tp_price <= entry_price:
                    validation_result["is_valid"] = False
                    validation_result["errors"].append(f"ロングポジションのTP{i+1}はエントリー価格より高い必要があります")
            else:
                if tp_price >= entry_price:
                    validation_result["is_valid"] = False
                    validation_result["errors"].append(f"ショートポジションのTP{i+1}はエントリー価格より低い必要があります")
            
            # RR比チェック
            rr_ratio = tp_distance_pips / sl_distance_pips if sl_distance_pips > 0 else 0
            if rr_ratio < 1.0:
                validation_result["warnings"].append(f"TP{i+1}のRR比({rr_ratio:.2f})が1.0未満です")
        
        # 4. 最初のTPのRR比チェック
        if take_profit_prices:
            tp1_distance_pips = abs(float(entry_price - take_profit_prices[0])) * 10000
            rr_ratio_tp1 = tp1_distance_pips / sl_distance_pips if sl_distance_pips > 0 else 0
            
            if rr_ratio_tp1 < self.min_rr_ratio:
                validation_result["warnings"].append(
                    f"最初のTPのRR比({rr_ratio_tp1:.2f})が推奨最小値({self.min_rr_ratio})を下回っています"
                )
        
        return validation_result
    
    def suggest_improvements(
        self,
        current_sl: StopLossCalculation,
        current_tps: List[TakeProfitLevel],
        entry_price: Decimal,
        direction: SignalDirection,
        pattern_type: str,
        current_atr: float
    ) -> Dict[str, Any]:
        """現在の価格設定に対する改善提案を生成"""
        
        suggestions = {
            "sl_suggestions": [],
            "tp_suggestions": [],
            "general_suggestions": []
        }
        
        # 現在のRR分析
        rr_analysis = self.rr_validator.validate_and_analyze(
            current_sl, current_tps, entry_price, direction
        )
        
        # 1. SLの改善提案
        if current_sl.distance_pips > current_atr * 2:
            suggestions["sl_suggestions"].append({
                "type": "reduce_sl",
                "reason": f"SL距離({current_sl.distance_pips:.1f}pips)がATRの2倍を超えています",
                "suggested_distance": round(current_atr * 1.5, 1)
            })
        
        # 2. TPの改善提案
        if not current_tps:
            suggestions["tp_suggestions"].append({
                "type": "add_tps",
                "reason": "TPが設定されていません",
                "suggested_count": 3
            })
        elif len(current_tps) == 1:
            suggestions["tp_suggestions"].append({
                "type": "add_more_tps",
                "reason": "複数のTPを設定することでリスクを分散できます",
                "suggested_count": 2
            })
        
        # 3. RR比の改善提案
        if not rr_analysis.meets_minimum:
            if rr_analysis.recommended_adjustment:
                suggestions["general_suggestions"].append({
                    "type": "improve_rr",
                    "reason": f"RR比({rr_analysis.rr_ratio_weighted:.2f})が最小要件を満たしていません",
                    "adjustment": rr_analysis.recommended_adjustment
                })
        
        # 4. パターン別の提案
        pattern_suggestions = self._get_pattern_specific_suggestions(
            pattern_type, current_sl, current_tps, current_atr
        )
        if pattern_suggestions:
            suggestions["general_suggestions"].extend(pattern_suggestions)
        
        return suggestions
    
    def _get_pattern_specific_suggestions(
        self,
        pattern_type: str,
        current_sl: StopLossCalculation,
        current_tps: List[TakeProfitLevel],
        current_atr: float
    ) -> List[Dict[str, Any]]:
        """パターン別の改善提案"""
        
        suggestions = []
        
        if pattern_type == "V_SHAPE_REVERSAL":
            if current_sl.calculation_method.value != "swing_based":
                suggestions.append({
                    "type": "use_swing_sl",
                    "reason": "V字反転パターンではスイングベースのSLが推奨されます"
                })
        
        elif pattern_type == "EMA_SQUEEZE":
            if current_sl.distance_pips > current_atr:
                suggestions.append({
                    "type": "tighter_sl",
                    "reason": "EMAスクイーズではタイトなSLが推奨されます",
                    "suggested_distance": round(current_atr * 0.8, 1)
                })
        
        elif pattern_type == "FALSE_BREAKOUT":
            # ブレイクアウト失敗パターンの場合
            if not any(tp.zone_reference for tp in current_tps):
                suggestions.append({
                    "type": "use_zone_tps",
                    "reason": "ブレイクアウト失敗パターンではゾーンベースのTPが効果的です"
                })
        
        return suggestions