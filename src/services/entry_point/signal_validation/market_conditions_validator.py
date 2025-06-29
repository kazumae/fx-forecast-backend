from datetime import datetime, timezone, timedelta
from typing import List, Optional
from src.domain.models.entry_signal import EntrySignal
from src.domain.models.signal_validation import (
    ValidationCheck, ValidationCheckType, ValidationSeverity,
    MarketConditions
)


class MarketConditionsValidator:
    """市場条件検証器"""
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.max_spread_multiplier = self.config.get("max_spread_multiplier", 3.0)
        self.max_absolute_spread = self.config.get("max_absolute_spread", 5.0)
        self.min_liquidity_score = self.config.get("min_liquidity_score", 30.0)
        self.news_buffer_minutes = self.config.get("news_buffer_minutes", 30)
        
        # 市場時間設定（UTC）
        self.market_hours = self.config.get("market_hours", {
            "forex": {
                "sunday_open": 21,    # 日曜21:00 UTC
                "friday_close": 21,   # 金曜21:00 UTC
                "daily_break": None   # 24時間取引
            },
            "gold": {
                "sunday_open": 22,    # 日曜22:00 UTC
                "friday_close": 21,   # 金曜21:00 UTC
                "daily_break": (21, 22)  # 21:00-22:00 UTC休憩
            }
        })
    
    def validate(
        self,
        signal: EntrySignal,
        market_conditions: MarketConditions
    ) -> List[ValidationCheck]:
        """市場条件を検証"""
        checks = []
        
        # 市場時間チェック
        checks.append(self._check_market_hours(signal, market_conditions))
        
        # スプレッドチェック
        checks.append(self._check_spread(signal, market_conditions))
        
        # 流動性チェック
        checks.append(self._check_liquidity(signal, market_conditions))
        
        # ニュース時間チェック
        checks.append(self._check_news_time(signal, market_conditions))
        
        return checks
    
    def _check_market_hours(
        self,
        signal: EntrySignal,
        market_conditions: MarketConditions
    ) -> ValidationCheck:
        """市場が開いている時間か確認"""
        
        if not market_conditions.is_market_open:
            return ValidationCheck(
                check_name=ValidationCheckType.MARKET_HOURS,
                passed=False,
                message="市場が閉まっています",
                severity=ValidationSeverity.CRITICAL
            )
        
        # より詳細な時間チェック
        current_time = signal.timestamp
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        
        weekday = current_time.weekday()
        hour = current_time.hour
        
        # 商品タイプを判定
        instrument_type = "gold" if "XAU" in signal.symbol else "forex"
        hours_config = self.market_hours.get(instrument_type, self.market_hours["forex"])
        
        # 週末チェック
        if weekday == 6:  # 日曜日
            if hour < hours_config["sunday_open"]:
                return ValidationCheck(
                    check_name=ValidationCheckType.MARKET_HOURS,
                    passed=False,
                    message=f"日曜日の市場開始前です（{hours_config['sunday_open']}:00 UTCから）",
                    severity=ValidationSeverity.CRITICAL
                )
        elif weekday == 4:  # 金曜日
            if hour >= hours_config["friday_close"]:
                return ValidationCheck(
                    check_name=ValidationCheckType.MARKET_HOURS,
                    passed=False,
                    message=f"金曜日の市場終了後です（{hours_config['friday_close']}:00 UTCまで）",
                    severity=ValidationSeverity.CRITICAL
                )
        elif weekday == 5:  # 土曜日
            return ValidationCheck(
                check_name=ValidationCheckType.MARKET_HOURS,
                passed=False,
                message="土曜日は市場が閉まっています",
                severity=ValidationSeverity.CRITICAL
            )
        
        # 日次休憩時間チェック（ゴールドなど）
        if hours_config.get("daily_break"):
            break_start, break_end = hours_config["daily_break"]
            if break_start <= hour < break_end:
                return ValidationCheck(
                    check_name=ValidationCheckType.MARKET_HOURS,
                    passed=False,
                    message=f"日次休憩時間です（{break_start}:00-{break_end}:00 UTC）",
                    severity=ValidationSeverity.WARNING
                )
        
        # セッション情報を追加
        session_info = self._get_session_info(hour)
        
        return ValidationCheck(
            check_name=ValidationCheckType.MARKET_HOURS,
            passed=True,
            message=f"市場は開いています（{session_info}セッション）",
            details={"session": session_info, "hour_utc": hour}
        )
    
    def _check_spread(
        self,
        signal: EntrySignal,
        market_conditions: MarketConditions
    ) -> ValidationCheck:
        """スプレッドが異常でないか検証"""
        
        current_spread = market_conditions.current_spread
        average_spread = market_conditions.average_spread
        
        # 絶対値チェック
        if current_spread > self.max_absolute_spread:
            return ValidationCheck(
                check_name=ValidationCheckType.SPREAD_CHECK,
                passed=False,
                message=f"スプレッドが絶対最大値を超過: {current_spread:.1f}pips > {self.max_absolute_spread}pips",
                severity=ValidationSeverity.CRITICAL
            )
        
        # 平均との比較チェック
        if average_spread > 0:
            spread_ratio = current_spread / average_spread
            if spread_ratio > self.max_spread_multiplier:
                return ValidationCheck(
                    check_name=ValidationCheckType.SPREAD_CHECK,
                    passed=False,
                    message=f"スプレッドが平均の{spread_ratio:.1f}倍（最大{self.max_spread_multiplier}倍）",
                    severity=ValidationSeverity.WARNING,
                    details={
                        "current_spread": current_spread,
                        "average_spread": average_spread,
                        "ratio": spread_ratio
                    }
                )
        
        # スプレッドレベルの評価
        spread_level = "正常"
        if current_spread > average_spread * 2:
            spread_level = "やや高い"
        elif current_spread > average_spread * 1.5:
            spread_level = "高め"
        
        return ValidationCheck(
            check_name=ValidationCheckType.SPREAD_CHECK,
            passed=True,
            message=f"スプレッドは{spread_level}範囲内: {current_spread:.1f}pips",
            details={
                "current_spread": current_spread,
                "average_spread": average_spread,
                "level": spread_level
            }
        )
    
    def _check_liquidity(
        self,
        signal: EntrySignal,
        market_conditions: MarketConditions
    ) -> ValidationCheck:
        """流動性が十分か確認"""
        
        liquidity_score = market_conditions.liquidity_score
        
        if liquidity_score < self.min_liquidity_score:
            # 流動性レベルを判定
            if liquidity_score < 10:
                severity = ValidationSeverity.CRITICAL
                level = "極めて低い"
            elif liquidity_score < 20:
                severity = ValidationSeverity.CRITICAL
                level = "非常に低い"
            else:
                severity = ValidationSeverity.WARNING
                level = "低い"
            
            return ValidationCheck(
                check_name=ValidationCheckType.LIQUIDITY_CHECK,
                passed=False,
                message=f"流動性が{level}: スコア {liquidity_score:.1f} < {self.min_liquidity_score}",
                severity=severity,
                details={
                    "liquidity_score": liquidity_score,
                    "min_required": self.min_liquidity_score,
                    "session": market_conditions.market_session
                }
            )
        
        # 流動性レベルの評価
        if liquidity_score >= 80:
            level = "非常に高い"
        elif liquidity_score >= 60:
            level = "高い"
        elif liquidity_score >= 40:
            level = "適切"
        else:
            level = "やや低い"
        
        return ValidationCheck(
            check_name=ValidationCheckType.LIQUIDITY_CHECK,
            passed=True,
            message=f"流動性は{level}: スコア {liquidity_score:.1f}",
            details={"liquidity_score": liquidity_score, "level": level}
        )
    
    def _check_news_time(
        self,
        signal: EntrySignal,
        market_conditions: MarketConditions
    ) -> ValidationCheck:
        """重要ニュース時間を考慮"""
        
        if not market_conditions.upcoming_news:
            return ValidationCheck(
                check_name=ValidationCheckType.NEWS_TIME_CHECK,
                passed=True,
                message="近い将来の重要ニュースはありません"
            )
        
        current_time = signal.timestamp
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        
        critical_news = []
        warning_news = []
        
        for news in market_conditions.upcoming_news:
            news_time = news.get("time")
            if isinstance(news_time, str):
                # 文字列の場合はdatetimeに変換
                try:
                    news_time = datetime.fromisoformat(news_time)
                except:
                    continue
            
            if news_time.tzinfo is None:
                news_time = news_time.replace(tzinfo=timezone.utc)
            
            # ニュースまでの時間を計算
            time_to_news = (news_time - current_time).total_seconds() / 60
            
            # バッファー時間内かチェック
            if abs(time_to_news) <= self.news_buffer_minutes:
                impact = news.get("impact", "medium")
                title = news.get("title", "Unknown")
                
                news_info = {
                    "title": title,
                    "impact": impact,
                    "time_minutes": abs(time_to_news),
                    "direction": "前" if time_to_news < 0 else "後"
                }
                
                if impact == "high":
                    critical_news.append(news_info)
                else:
                    warning_news.append(news_info)
        
        # 重要ニュースがある場合
        if critical_news:
            news_desc = "; ".join([
                f"{n['title']} ({n['time_minutes']:.0f}分{n['direction']})"
                for n in critical_news[:2]  # 最大2つまで表示
            ])
            
            return ValidationCheck(
                check_name=ValidationCheckType.NEWS_TIME_CHECK,
                passed=False,
                message=f"重要ニュースイベント近辺: {news_desc}",
                severity=ValidationSeverity.WARNING,
                details={"critical_news": critical_news, "warning_news": warning_news}
            )
        
        # 中程度のニュースのみの場合
        if warning_news:
            return ValidationCheck(
                check_name=ValidationCheckType.NEWS_TIME_CHECK,
                passed=True,
                message=f"中程度のニュースイベントあり（{len(warning_news)}件）",
                severity=ValidationSeverity.INFO,
                details={"warning_news": warning_news}
            )
        
        return ValidationCheck(
            check_name=ValidationCheckType.NEWS_TIME_CHECK,
            passed=True,
            message="ニュースイベントの影響なし"
        )
    
    def _get_session_info(self, hour_utc: int) -> str:
        """現在の取引セッションを判定"""
        if 0 <= hour_utc < 8:
            return "アジア"
        elif 8 <= hour_utc < 13:
            return "ロンドン"
        elif 13 <= hour_utc < 17:
            return "ロンドン/NY重複"
        elif 17 <= hour_utc < 22:
            return "ニューヨーク"
        else:
            return "アジア早朝"