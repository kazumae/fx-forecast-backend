from decimal import Decimal
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
from src.domain.models.price_calculation import (
    PriceAdjustments, AdjustmentType, StopLossCalculation, TakeProfitLevel
)
from src.domain.models.entry_signal import SignalDirection


class SpecialCaseHandler:
    """特殊ケース処理器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # ボラティリティ調整設定
        self.volatility_thresholds = self.config.get("volatility_thresholds", {
            "low": 10.0,      # ATR < 10pips
            "normal": 20.0,   # 10 <= ATR < 20pips
            "high": 30.0      # ATR >= 30pips
        })
        
        self.volatility_factors = self.config.get("volatility_factors", {
            "low": 0.8,       # 低ボラ時は縮小
            "normal": 1.0,    # 通常
            "high": 1.3,      # 高ボラ時は拡大
            "extreme": 1.5    # 極端な高ボラ
        })
        
        # セッション調整設定
        self.session_factors = self.config.get("session_factors", {
            "asian": 0.9,     # アジア時間（低ボラ）
            "london": 1.1,    # ロンドン時間（高ボラ）
            "newyork": 1.0,   # ニューヨーク時間
            "overlap": 1.2    # セッション重複時
        })
        
        # ニュース時間帯設定
        self.news_buffer_minutes = self.config.get("news_buffer_minutes", 30)
        self.news_factor = self.config.get("news_factor", 1.5)
        
        # 既存ポジション干渉設定
        self.position_buffer_pips = self.config.get("position_buffer_pips", 5.0)
        self.correlation_threshold = self.config.get("correlation_threshold", 0.7)
    
    def apply_adjustments(
        self,
        stop_loss: StopLossCalculation,
        take_profits: List[TakeProfitLevel],
        input_data: Dict[str, Any],
        current_time: Optional[datetime] = None
    ) -> Tuple[StopLossCalculation, List[TakeProfitLevel], PriceAdjustments]:
        """特殊ケースに基づく調整を適用"""
        
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        adjustments = PriceAdjustments()
        
        # 1. ボラティリティ調整
        adjustments = self._apply_volatility_adjustment(
            adjustments, input_data.get("current_atr", 15.0)
        )
        
        # 2. セッション調整
        adjustments = self._apply_session_adjustment(
            adjustments, current_time, input_data.get("market_session")
        )
        
        # 3. ニュース時間帯調整
        if input_data.get("news_impact", False):
            adjustments = self._apply_news_adjustment(
                adjustments, current_time, input_data.get("news_events", [])
            )
        
        # 4. 調整を価格に適用
        adjusted_sl, adjusted_tps = self._apply_price_adjustments(
            stop_loss, take_profits, adjustments, 
            input_data.get("entry_price"), 
            input_data.get("direction", SignalDirection.LONG)
        )
        
        # 5. 既存ポジションとの干渉チェック
        if input_data.get("existing_positions"):
            adjusted_sl, adjusted_tps = self._check_position_interference(
                adjusted_sl, adjusted_tps,
                input_data.get("existing_positions", []),
                input_data.get("entry_price"),
                input_data.get("symbol", "XAUUSD")
            )
        
        return adjusted_sl, adjusted_tps, adjustments
    
    def _apply_volatility_adjustment(
        self,
        adjustments: PriceAdjustments,
        current_atr: float
    ) -> PriceAdjustments:
        """ボラティリティに基づく調整"""
        
        # ボラティリティレベルを判定
        if current_atr < self.volatility_thresholds["low"]:
            adjustments.volatility_factor = self.volatility_factors["low"]
            adjustments.adjustment_reasons.append(f"低ボラティリティ調整 (ATR: {current_atr:.1f}pips)")
        elif current_atr < self.volatility_thresholds["normal"]:
            adjustments.volatility_factor = self.volatility_factors["normal"]
        elif current_atr < self.volatility_thresholds["high"]:
            adjustments.volatility_factor = self.volatility_factors["high"]
            adjustments.adjustment_reasons.append(f"高ボラティリティ調整 (ATR: {current_atr:.1f}pips)")
        else:
            adjustments.volatility_factor = self.volatility_factors["extreme"]
            adjustments.adjustment_reasons.append(f"極端な高ボラティリティ調整 (ATR: {current_atr:.1f}pips)")
        
        return adjustments
    
    def _apply_session_adjustment(
        self,
        adjustments: PriceAdjustments,
        current_time: datetime,
        market_session: Optional[str] = None
    ) -> PriceAdjustments:
        """市場セッションに基づく調整"""
        
        # セッションを自動判定（市場セッションが指定されていない場合）
        if market_session is None:
            market_session = self._determine_market_session(current_time)
        
        # セッション重複をチェック
        if self._is_session_overlap(current_time):
            adjustments.session_factor = self.session_factors["overlap"]
            adjustments.adjustment_reasons.append("セッション重複時間帯")
        else:
            adjustments.session_factor = self.session_factors.get(market_session, 1.0)
            if market_session != "normal":
                adjustments.adjustment_reasons.append(f"{market_session.capitalize()}セッション調整")
        
        return adjustments
    
    def _apply_news_adjustment(
        self,
        adjustments: PriceAdjustments,
        current_time: datetime,
        news_events: List[Dict[str, Any]]
    ) -> PriceAdjustments:
        """ニュースイベントに基づく調整"""
        
        # 近い将来のニュースイベントをチェック
        for event in news_events:
            event_time = event.get("time")
            if isinstance(event_time, str):
                # 文字列をdatetimeに変換（必要に応じて）
                continue
            
            # イベントまでの時間を計算
            time_to_event = (event_time - current_time).total_seconds() / 60
            
            # バッファー時間内かチェック
            if abs(time_to_event) <= self.news_buffer_minutes:
                adjustments.news_factor = self.news_factor
                adjustments.adjustment_reasons.append(
                    f"ニュースイベント調整: {event.get('title', 'Unknown')} "
                    f"({abs(time_to_event):.0f}分{'前' if time_to_event < 0 else '後'})"
                )
                break
        
        return adjustments
    
    def _apply_price_adjustments(
        self,
        stop_loss: StopLossCalculation,
        take_profits: List[TakeProfitLevel],
        adjustments: PriceAdjustments,
        entry_price: Decimal,
        direction: SignalDirection
    ) -> Tuple[StopLossCalculation, List[TakeProfitLevel]]:
        """調整係数を価格に適用"""
        
        # 最終調整係数を計算
        adjustments.final_multiplier = (
            adjustments.volatility_factor * 
            adjustments.session_factor * 
            adjustments.news_factor
        )
        
        # SLを調整
        adjusted_sl_distance = stop_loss.distance_pips * adjustments.final_multiplier
        sl_adjustment = Decimal(str((adjusted_sl_distance - stop_loss.distance_pips) / 10000))
        
        if direction == SignalDirection.LONG:
            adjusted_sl_price = stop_loss.price - sl_adjustment
        else:
            adjusted_sl_price = stop_loss.price + sl_adjustment
        
        adjusted_sl = StopLossCalculation(
            price=adjusted_sl_price,
            distance_pips=adjusted_sl_distance,
            calculation_method=stop_loss.calculation_method,
            details=stop_loss.details + f" (調整係数: ×{adjustments.final_multiplier:.2f})",
            zone_reference=stop_loss.zone_reference,
            swing_reference=stop_loss.swing_reference,
            atr_factor=stop_loss.atr_factor
        )
        
        # TPを調整
        adjusted_tps = []
        for tp in take_profits:
            adjusted_tp_distance = tp.distance_pips * adjustments.final_multiplier
            tp_adjustment = Decimal(str((adjusted_tp_distance - tp.distance_pips) / 10000))
            
            if direction == SignalDirection.LONG:
                adjusted_tp_price = tp.price + tp_adjustment
            else:
                adjusted_tp_price = tp.price - tp_adjustment
            
            adjusted_tp = TakeProfitLevel(
                level=tp.level,
                price=adjusted_tp_price,
                distance_pips=adjusted_tp_distance,
                percentage=tp.percentage,
                reason=tp.reason,
                zone_reference=tp.zone_reference,
                psychological_level=tp.psychological_level,
                fibonacci_level=tp.fibonacci_level
            )
            adjusted_tps.append(adjusted_tp)
        
        return adjusted_sl, adjusted_tps
    
    def _check_position_interference(
        self,
        stop_loss: StopLossCalculation,
        take_profits: List[TakeProfitLevel],
        existing_positions: List[Dict[str, Any]],
        entry_price: Decimal,
        symbol: str
    ) -> Tuple[StopLossCalculation, List[TakeProfitLevel]]:
        """既存ポジションとの干渉をチェック"""
        
        for position in existing_positions:
            # 同じ通貨ペアまたは相関の高い通貨ペアをチェック
            if position.get("symbol") == symbol or self._is_correlated(symbol, position.get("symbol")):
                pos_entry = Decimal(str(position.get("entry_price", 0)))
                pos_sl = Decimal(str(position.get("stop_loss", 0)))
                pos_tp = Decimal(str(position.get("take_profit", 0)))
                
                # SLの干渉チェック
                sl_distance = abs(float(stop_loss.price - pos_sl)) * 10000
                if sl_distance < self.position_buffer_pips:
                    # SLを調整して干渉を回避
                    buffer_adjustment = Decimal(str(self.position_buffer_pips / 10000))
                    if stop_loss.price < pos_sl:
                        stop_loss.price -= buffer_adjustment
                    else:
                        stop_loss.price += buffer_adjustment
                    
                    stop_loss.details += f" (既存ポジション回避: {self.position_buffer_pips}pips)"
                
                # TPの干渉チェック
                for tp in take_profits:
                    tp_distance = abs(float(tp.price - pos_tp)) * 10000
                    if tp_distance < self.position_buffer_pips:
                        # TPを調整して干渉を回避
                        buffer_adjustment = Decimal(str(self.position_buffer_pips / 10000))
                        if tp.price < pos_tp:
                            tp.price -= buffer_adjustment
                        else:
                            tp.price += buffer_adjustment
        
        return stop_loss, take_profits
    
    def _determine_market_session(self, current_time: datetime) -> str:
        """現在の市場セッションを判定"""
        
        hour_utc = current_time.hour
        
        # 簡易的なセッション判定（UTC基準）
        if 0 <= hour_utc < 8:  # 00:00-08:00 UTC
            return "asian"
        elif 8 <= hour_utc < 13:  # 08:00-13:00 UTC
            return "london"
        elif 13 <= hour_utc < 22:  # 13:00-22:00 UTC
            return "newyork"
        else:  # 22:00-00:00 UTC
            return "asian"
    
    def _is_session_overlap(self, current_time: datetime) -> bool:
        """セッション重複時間帯かチェック"""
        
        hour_utc = current_time.hour
        
        # ロンドン/NYの重複: 13:00-17:00 UTC
        if 13 <= hour_utc < 17:
            return True
        
        # アジア/ロンドンの重複: 07:00-08:00 UTC
        if 7 <= hour_utc < 8:
            return True
        
        return False
    
    def _is_correlated(self, symbol1: str, symbol2: str) -> bool:
        """通貨ペアの相関をチェック"""
        
        # 簡易的な相関チェック（同じ基軸通貨）
        base1 = symbol1[:3]
        base2 = symbol2[:3]
        
        # ゴールド関連
        if "XAU" in symbol1 and "XAU" in symbol2:
            return True
        
        # 同じ基軸通貨
        if base1 == base2:
            return True
        
        # 主要通貨ペアの相関（簡易版）
        correlated_pairs = [
            ("EUR", "GBP"),
            ("AUD", "NZD"),
            ("USD", "JPY")  # 逆相関だが干渉を考慮
        ]
        
        for pair in correlated_pairs:
            if (base1 in pair and base2 in pair):
                return True
        
        return False