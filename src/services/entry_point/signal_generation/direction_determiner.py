from typing import Dict, Any, Optional, List
from src.domain.models.entry_signal import SignalDirection
from src.domain.models.pattern import PatternType, PatternSignal


class DirectionDeterminer:
    """エントリー方向決定器"""
    
    def __init__(self):
        # パターンタイプごとの方向マッピング
        self.pattern_direction_map = {
            PatternType.V_SHAPE_REVERSAL: self._determine_v_shape_direction,
            PatternType.EMA_SQUEEZE: self._determine_ema_squeeze_direction,
            PatternType.TREND_CONTINUATION: self._determine_trend_continuation_direction,
            PatternType.FALSE_BREAKOUT: self._determine_false_breakout_direction
        }
    
    def determine_direction(
        self, 
        pattern_signal: PatternSignal,
        market_context: Dict[str, Any]
    ) -> SignalDirection:
        """パターンシグナルから取引方向を決定"""
        
        # パターンタイプに応じた方向決定
        pattern_type = pattern_signal.pattern_type
        
        # pattern.parametersをpattern.detailsとして扱う
        if not hasattr(pattern_signal, 'details'):
            pattern_signal.details = pattern_signal.parameters
        
        if pattern_type in self.pattern_direction_map:
            direction = self.pattern_direction_map[pattern_type](
                pattern_signal, market_context
            )
        else:
            # デフォルトは市場トレンドに従う
            direction = self._determine_default_direction(
                pattern_signal, market_context
            )
        
        # 矛盾チェック
        if self._has_conflicting_signals(direction, market_context):
            # 矛盾がある場合は市場環境を優先
            direction = self._resolve_conflict(direction, market_context)
        
        return direction
    
    def _determine_v_shape_direction(
        self, 
        pattern_signal: PatternSignal,
        market_context: Dict[str, Any]
    ) -> SignalDirection:
        """V字反転パターンの方向決定"""
        
        # V字パターンは反転シグナル
        reversal_type = pattern_signal.details.get("reversal_type", "bullish")
        
        if reversal_type == "bullish":
            return SignalDirection.LONG
        else:
            return SignalDirection.SHORT
    
    def _determine_ema_squeeze_direction(
        self, 
        pattern_signal: PatternSignal,
        market_context: Dict[str, Any]
    ) -> SignalDirection:
        """EMAスクイーズパターンの方向決定"""
        
        # スクイーズ後のブレイクアウト方向
        breakout_direction = pattern_signal.details.get("breakout_direction")
        
        if breakout_direction == "up":
            return SignalDirection.LONG
        elif breakout_direction == "down":
            return SignalDirection.SHORT
        else:
            # 未決定の場合は現在のトレンドに従う
            current_trend = market_context.get("current_trend", "up")
            return SignalDirection.LONG if current_trend == "up" else SignalDirection.SHORT
    
    def _determine_trend_continuation_direction(
        self, 
        pattern_signal: PatternSignal,
        market_context: Dict[str, Any]
    ) -> SignalDirection:
        """トレンド継続パターンの方向決定"""
        
        # 現在のトレンドに従う
        trend_direction = pattern_signal.details.get("trend_direction", "up")
        
        return SignalDirection.LONG if trend_direction == "up" else SignalDirection.SHORT
    
    def _determine_false_breakout_direction(
        self, 
        pattern_signal: PatternSignal,
        market_context: Dict[str, Any]
    ) -> SignalDirection:
        """偽ブレイクアウトパターンの方向決定"""
        
        # 偽ブレイクアウトの反対方向へエントリー
        false_breakout_direction = pattern_signal.details.get("false_breakout_direction")
        
        if false_breakout_direction == "up":
            # 上方向への偽ブレイクアウト → ショート
            return SignalDirection.SHORT
        else:
            # 下方向への偽ブレイクアウト → ロング
            return SignalDirection.LONG
    
    def _determine_default_direction(
        self, 
        pattern_signal: PatternSignal,
        market_context: Dict[str, Any]
    ) -> SignalDirection:
        """デフォルトの方向決定（市場トレンドに従う）"""
        
        # 上位足のトレンドを確認
        higher_tf_trend = market_context.get("higher_timeframe_trend", "neutral")
        
        if higher_tf_trend == "up":
            return SignalDirection.LONG
        elif higher_tf_trend == "down":
            return SignalDirection.SHORT
        else:
            # ニュートラルの場合は現在のモメンタムで判断
            momentum = market_context.get("momentum", 0)
            return SignalDirection.LONG if momentum > 0 else SignalDirection.SHORT
    
    def _has_conflicting_signals(
        self, 
        direction: SignalDirection,
        market_context: Dict[str, Any]
    ) -> bool:
        """矛盾するシグナルの検出"""
        
        # 複数の時間軸での矛盾をチェック
        timeframe_trends = market_context.get("timeframe_trends", {})
        
        if not timeframe_trends:
            return False
        
        # 方向の一致度を計算
        matching_count = 0
        total_count = 0
        
        expected_trend = "up" if direction == SignalDirection.LONG else "down"
        
        for tf, trend in timeframe_trends.items():
            total_count += 1
            if trend == expected_trend:
                matching_count += 1
        
        # 50%未満の一致度の場合は矛盾ありと判断
        if total_count > 0 and matching_count / total_count < 0.5:
            return True
        
        # 重要な指標との矛盾
        major_indicators = market_context.get("major_indicators", {})
        rsi = major_indicators.get("rsi")
        
        if rsi:
            if direction == SignalDirection.LONG and rsi > 70:
                # ロング方向だがRSIが買われすぎ
                return True
            elif direction == SignalDirection.SHORT and rsi < 30:
                # ショート方向だがRSIが売られすぎ
                return True
        
        return False
    
    def _resolve_conflict(
        self, 
        original_direction: SignalDirection,
        market_context: Dict[str, Any]
    ) -> SignalDirection:
        """矛盾の解決"""
        
        # 上位足のトレンドを最優先
        higher_tf_trend = market_context.get("higher_timeframe_trend")
        
        if higher_tf_trend == "up":
            return SignalDirection.LONG
        elif higher_tf_trend == "down":
            return SignalDirection.SHORT
        else:
            # 上位足が不明な場合は元の方向を維持
            return original_direction
    
    def get_direction_confidence(
        self, 
        direction: SignalDirection,
        market_context: Dict[str, Any]
    ) -> float:
        """方向決定の信頼度を計算（0.0-1.0）"""
        
        confidence = 1.0
        
        # 時間軸の一致度
        timeframe_trends = market_context.get("timeframe_trends", {})
        if timeframe_trends:
            expected_trend = "up" if direction == SignalDirection.LONG else "down"
            matching_count = sum(1 for trend in timeframe_trends.values() if trend == expected_trend)
            total_count = len(timeframe_trends)
            
            if total_count > 0:
                alignment_score = matching_count / total_count
                confidence *= alignment_score
        
        # ボリュームの確認
        volume_trend = market_context.get("volume_trend")
        if volume_trend == "increasing":
            confidence *= 1.1  # ボリューム増加は信頼度アップ
        elif volume_trend == "decreasing":
            confidence *= 0.9  # ボリューム減少は信頼度ダウン
        
        # 上限を1.0に制限
        return min(1.0, confidence)