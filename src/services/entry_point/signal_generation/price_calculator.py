from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional, Tuple, List
from src.domain.models.entry_signal import (
    OrderType, EntryOrderInfo, StopLossInfo, TakeProfitLevel,
    RiskRewardInfo, SignalDirection
)


class PriceCalculator:
    """価格計算器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        # デフォルト設定
        self.default_slippage_tolerance = 2.0  # pips
        self.default_order_validity_minutes = 5
        self.pip_decimal_places = {
            "XAUUSD": 2,  # 金は小数点以下2桁
            "EURUSD": 5,  # 通常の通貨ペアは5桁
            "USDJPY": 3   # 円ペアは3桁
        }
    
    def calculate_entry_price(
        self,
        current_price: Decimal,
        direction: SignalDirection,
        pattern_details: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> EntryOrderInfo:
        """エントリー価格と注文タイプを計算"""
        
        # 注文タイプを決定
        order_type = self._determine_order_type(
            pattern_details, market_data
        )
        
        # エントリー価格を計算
        if order_type == OrderType.MARKET:
            entry_price = current_price
            slippage_tolerance = self.default_slippage_tolerance
        elif order_type == OrderType.LIMIT:
            entry_price, slippage_tolerance = self._calculate_limit_price(
                current_price, direction, pattern_details, market_data
            )
        else:  # OrderType.STOP
            entry_price, slippage_tolerance = self._calculate_stop_price(
                current_price, direction, pattern_details, market_data
            )
        
        # 有効期限を設定
        valid_until = datetime.now() + timedelta(
            minutes=self.config.get("order_validity_minutes", self.default_order_validity_minutes)
        )
        
        return EntryOrderInfo(
            price=self._round_price(entry_price, pattern_details.get("symbol", "XAUUSD")),
            type=order_type,
            valid_until=valid_until,
            slippage_tolerance=slippage_tolerance
        )
    
    def calculate_stop_loss(
        self,
        entry_price: Decimal,
        direction: SignalDirection,
        pattern_details: Dict[str, Any],
        risk_params: Dict[str, Any]
    ) -> StopLossInfo:
        """ストップロス価格を計算"""
        
        # パターンに基づくSL距離を取得
        base_sl_distance = self._get_pattern_based_sl_distance(
            pattern_details, risk_params
        )
        
        # 方向に応じてSL価格を計算
        if direction == SignalDirection.LONG:
            sl_price = entry_price - Decimal(str(base_sl_distance / 10000))
        else:
            sl_price = entry_price + Decimal(str(base_sl_distance / 10000))
        
        # トレーリング設定
        trailing = risk_params.get("enable_trailing", False)
        trail_distance_pips = risk_params.get("trail_distance_pips", 10.0) if trailing else None
        
        return StopLossInfo(
            price=self._round_price(sl_price, pattern_details.get("symbol", "XAUUSD")),
            trailing=trailing,
            trail_distance_pips=trail_distance_pips
        )
    
    def calculate_take_profits(
        self,
        entry_price: Decimal,
        direction: SignalDirection,
        pattern_details: Dict[str, Any],
        risk_params: Dict[str, Any]
    ) -> List[TakeProfitLevel]:
        """テイクプロフィット価格を計算"""
        
        take_profits = []
        
        # デフォルトのTP設定
        tp_levels = risk_params.get("tp_levels", [
            {"ratio": 1.0, "percentage": 50},
            {"ratio": 1.5, "percentage": 30},
            {"ratio": 2.0, "percentage": 20}
        ])
        
        # 基準となるリスク距離
        base_risk_distance = self._get_pattern_based_sl_distance(
            pattern_details, risk_params
        )
        
        for tp_config in tp_levels:
            tp_distance = base_risk_distance * tp_config["ratio"]
            
            if direction == SignalDirection.LONG:
                tp_price = entry_price + Decimal(str(tp_distance / 10000))
            else:
                tp_price = entry_price - Decimal(str(tp_distance / 10000))
            
            take_profits.append(TakeProfitLevel(
                price=self._round_price(tp_price, pattern_details.get("symbol", "XAUUSD")),
                percentage=tp_config["percentage"]
            ))
        
        return take_profits
    
    def calculate_risk_reward(
        self,
        entry_price: Decimal,
        stop_loss: StopLossInfo,
        take_profits: List[TakeProfitLevel]
    ) -> RiskRewardInfo:
        """リスクリワード比を計算"""
        
        # リスク（pips）を計算
        risk_pips = abs(float(entry_price - stop_loss.price)) * 10000
        
        # 平均リワード（pips）を計算
        total_reward = 0.0
        total_percentage = 0.0
        
        for tp in take_profits:
            reward_pips = abs(float(tp.price - entry_price)) * 10000
            weighted_reward = reward_pips * (tp.percentage / 100)
            total_reward += weighted_reward
            total_percentage += tp.percentage
        
        # 加重平均リワード
        avg_reward_pips = total_reward if total_percentage > 0 else 0
        
        # RR比を計算
        rr_ratio = avg_reward_pips / risk_pips if risk_pips > 0 else 0
        
        return RiskRewardInfo(
            risk_pips=round(risk_pips, 1),
            reward_pips=round(avg_reward_pips, 1),
            ratio=round(rr_ratio, 2)
        )
    
    def _determine_order_type(
        self,
        pattern_details: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> OrderType:
        """注文タイプを決定"""
        
        # 即時実行フラグがある場合は成行
        if pattern_details.get("immediate_execution", False):
            return OrderType.MARKET
        
        # ボラティリティが高い場合は成行
        volatility = market_data.get("volatility", "normal")
        if volatility == "high":
            return OrderType.MARKET
        
        # パターンタイプに応じて判定
        pattern_type = pattern_details.get("pattern_type")
        
        if pattern_type in ["V_SHAPE_REVERSAL", "FALSE_BREAKOUT"]:
            # 反転系は指値
            return OrderType.LIMIT
        elif pattern_type == "TREND_CONTINUATION":
            # トレンド継続は逆指値
            return OrderType.STOP
        else:
            # デフォルトは指値
            return OrderType.LIMIT
    
    def _calculate_limit_price(
        self,
        current_price: Decimal,
        direction: SignalDirection,
        pattern_details: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> Tuple[Decimal, float]:
        """指値価格を計算"""
        
        # より有利な価格で約定を狙う
        price_improvement_pips = pattern_details.get("price_improvement_pips", 2.0)
        
        if direction == SignalDirection.LONG:
            # ロングの場合は現在価格より低い価格
            limit_price = current_price - Decimal(str(price_improvement_pips / 10000))
        else:
            # ショートの場合は現在価格より高い価格
            limit_price = current_price + Decimal(str(price_improvement_pips / 10000))
        
        # スリッページ許容値は小さめ
        slippage_tolerance = 1.0
        
        return limit_price, slippage_tolerance
    
    def _calculate_stop_price(
        self,
        current_price: Decimal,
        direction: SignalDirection,
        pattern_details: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> Tuple[Decimal, float]:
        """逆指値価格を計算"""
        
        # ブレイクアウトを確認する距離
        breakout_distance_pips = pattern_details.get("breakout_distance_pips", 3.0)
        
        if direction == SignalDirection.LONG:
            # ロングの場合は現在価格より高い価格
            stop_price = current_price + Decimal(str(breakout_distance_pips / 10000))
        else:
            # ショートの場合は現在価格より低い価格
            stop_price = current_price - Decimal(str(breakout_distance_pips / 10000))
        
        # スリッページ許容値は大きめ
        slippage_tolerance = 3.0
        
        return stop_price, slippage_tolerance
    
    def _get_pattern_based_sl_distance(
        self,
        pattern_details: Dict[str, Any],
        risk_params: Dict[str, Any]
    ) -> float:
        """パターンに基づくSL距離を取得（pips）"""
        
        # デフォルトSL距離
        default_sl_pips = risk_params.get("default_sl_pips", 20.0)
        
        # パターン固有のSL距離
        pattern_sl_map = {
            "V_SHAPE_REVERSAL": 15.0,  # V字は比較的タイト
            "EMA_SQUEEZE": 12.0,       # スクイーズは最もタイト
            "TREND_CONTINUATION": 25.0, # トレンド継続は余裕を持つ
            "FALSE_BREAKOUT": 18.0     # 偽ブレイクアウトは中間
        }
        
        pattern_type = pattern_details.get("pattern_type")
        base_sl = pattern_sl_map.get(pattern_type, default_sl_pips)
        
        # ボラティリティ調整
        volatility_factor = risk_params.get("volatility_factor", 1.0)
        adjusted_sl = base_sl * volatility_factor
        
        # パワーゾーンによる調整
        if pattern_details.get("is_power_zone", False):
            power_level = pattern_details.get("power_level", 0)
            reduction_factor = 1.0 - (power_level * 0.05)  # レベルごとに5%縮小
            adjusted_sl *= reduction_factor
        
        return max(adjusted_sl, 5.0)  # 最小5pips
    
    def _round_price(self, price: Decimal, symbol: str) -> Decimal:
        """価格を適切な小数点以下桁数に丸める"""
        
        decimal_places = self.pip_decimal_places.get(symbol, 5)
        
        # 小数点以下の桁数を指定して丸める
        quantizer = Decimal(f"1e-{decimal_places}")
        return price.quantize(quantizer, rounding=ROUND_HALF_UP)