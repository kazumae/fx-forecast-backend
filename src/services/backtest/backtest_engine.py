"""バックテストエンジン"""
import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass

from src.domain.models.backtest import (
    BacktestConfig, BacktestResult, BacktestTrade,
    PerformanceMetrics, PatternPerformance, TimeAnalysis,
    EquityPoint, TradeStatus, ExitReason
)
from src.domain.models.market_data import Candlestick
from src.domain.models.entry_signal import EntrySignal, SignalDirection
from src.services.pattern_detection import PatternDetectionService
from src.services.entry_point.evaluation import EntryEvaluationService
from src.services.entry_point.signal_generation import SignalGenerationService
from src.services.entry_point.signal_validation import SignalValidationService


class BacktestEngine:
    """バックテストエンジン"""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.pattern_detector = PatternDetectionService()
        self.entry_evaluator = EntryEvaluationService()
        self.signal_generator = SignalGenerationService()
        self.signal_validator = SignalValidationService()
        
        # 内部状態
        self.current_equity = config.initial_capital
        self.open_positions: List[BacktestTrade] = []
        self.closed_trades: List[BacktestTrade] = []
        self.equity_curve: List[EquityPoint] = []
        self.max_equity = config.initial_capital
        self.max_drawdown = Decimal("0")
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.max_consecutive_wins = 0
        self.max_consecutive_losses = 0
        
    async def run(
        self,
        data: pd.DataFrame,
        zones: List[Any],
        market_context: Optional[Dict[str, Any]] = None
    ) -> BacktestResult:
        """バックテストを実行"""
        # データ準備
        candles = self._prepare_candles(data)
        
        # タイムスタンプ生成
        timestamps = self._generate_timestamps(
            self.config.start_date,
            self.config.end_date,
            candles
        )
        
        # 初期エクイティポイント
        self.equity_curve.append(EquityPoint(
            timestamp=self.config.start_date,
            equity=self.current_equity,
            drawdown=Decimal("0"),
            trade_count=0
        ))
        
        # メインループ
        for timestamp in timestamps:
            # 現在のコンテキスト作成
            context = self._create_context(candles, timestamp, zones, market_context)
            
            # オープンポジションの管理
            await self._manage_positions(context, timestamp)
            
            # 新規シグナルの検出
            if len(self.open_positions) < self.config.max_positions:
                signals = await self._detect_and_evaluate_signals(context, timestamp)
                
                # シグナルの実行
                for signal in signals:
                    if len(self.open_positions) >= self.config.max_positions:
                        break
                    await self._execute_signal(signal, timestamp)
            
            # エクイティカーブ更新
            self._update_equity_curve(timestamp)
        
        # 残ポジションをクローズ
        await self._close_all_positions(self.config.end_date)
        
        # 結果計算
        return self._calculate_results()
    
    def _prepare_candles(self, data: pd.DataFrame) -> List[Candlestick]:
        """DataFrameからCandlestickリストを作成"""
        candles = []
        for _, row in data.iterrows():
            candle = Candlestick(
                symbol=self.config.symbol,
                timeframe="1m",  # TODO: configから取得
                timestamp=pd.to_datetime(row["timestamp"]),
                open=Decimal(str(row["open"])),
                close=Decimal(str(row["close"])),
                high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])),
                volume=int(row.get("volume", 0))
            )
            candles.append(candle)
        return candles
    
    def _generate_timestamps(
        self,
        start: datetime,
        end: datetime,
        candles: List[Candlestick]
    ) -> List[datetime]:
        """評価タイムスタンプを生成"""
        timestamps = []
        for candle in candles:
            if start <= candle.timestamp <= end:
                timestamps.append(candle.timestamp)
        return timestamps
    
    def _create_context(
        self,
        candles: List[Candlestick],
        timestamp: datetime,
        zones: List[Any],
        market_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """現在のコンテキストを作成"""
        # 過去のローソク足を取得
        historical_candles = [c for c in candles if c.timestamp <= timestamp]
        recent_candles = historical_candles[-100:] if len(historical_candles) > 100 else historical_candles
        
        # 現在価格
        current_price = recent_candles[-1].close if recent_candles else Decimal("0")
        
        context = {
            "candles": recent_candles,
            "zones": zones,
            "current_price": current_price,
            "timestamp": timestamp,
            "open_positions": len(self.open_positions),
            "equity": self.current_equity
        }
        
        if market_context:
            context.update(market_context)
            
        return context
    
    async def _detect_and_evaluate_signals(
        self,
        context: Dict[str, Any],
        timestamp: datetime
    ) -> List[EntrySignal]:
        """シグナルを検出・評価"""
        valid_signals = []
        
        # パターン検出
        patterns = await self.pattern_detector.detect_all_patterns(context["candles"])
        
        if patterns:
            # エントリー評価
            evaluations = await self.entry_evaluator.evaluate_entries(
                patterns,
                context["zones"],
                context
            )
            
            # シグナル生成
            signals = await self.signal_generator.generate_signals(
                evaluations,
                context["zones"],
                context
            )
            
            # シグナル検証
            for signal in signals:
                validation = await self.signal_validator.validate_signal(
                    signal,
                    context
                )
                if validation.is_valid:
                    valid_signals.append(signal)
        
        return valid_signals
    
    async def _execute_signal(
        self,
        signal: EntrySignal,
        timestamp: datetime
    ) -> Optional[BacktestTrade]:
        """シグナルを実行"""
        # ポジションサイズ計算
        position_size = self._calculate_position_size(signal)
        if position_size <= 0:
            return None
        
        # スリッページ適用
        entry_price = signal.entry.price
        if signal.direction == SignalDirection.LONG:
            entry_price += Decimal(str(self.config.slippage / 100))
        else:
            entry_price -= Decimal(str(self.config.slippage / 100))
        
        # 取引作成
        trade = BacktestTrade(
            id=f"bt_{uuid.uuid4().hex[:8]}",
            entry_time=timestamp,
            exit_time=None,
            symbol=self.config.symbol,
            direction="long" if signal.direction == SignalDirection.LONG else "short",
            entry_price=entry_price,
            exit_price=None,
            size=position_size,
            pnl=None,
            pnl_percentage=None,
            pattern=signal.metadata.pattern_type,
            entry_score=signal.metadata.confidence_score,
            exit_reason=None,
            status=TradeStatus.OPEN,
            metadata={
                "stop_loss": float(signal.stop_loss.price),
                "take_profits": [
                    {"level": tp.level, "price": float(tp.price)}
                    for tp in signal.take_profits
                ],
                "signal_id": signal.id
            }
        )
        
        # ポジション追加
        self.open_positions.append(trade)
        
        # コミッション差し引き
        self.current_equity -= self.config.commission
        
        return trade
    
    async def _manage_positions(
        self,
        context: Dict[str, Any],
        timestamp: datetime
    ):
        """オープンポジションを管理"""
        current_price = context["current_price"]
        positions_to_close = []
        
        for position in self.open_positions:
            # ストップロスチェック
            sl_price = Decimal(str(position.metadata["stop_loss"]))
            if position.direction == "long":
                if current_price <= sl_price:
                    positions_to_close.append((position, ExitReason.STOP_LOSS, current_price))
            else:
                if current_price >= sl_price:
                    positions_to_close.append((position, ExitReason.STOP_LOSS, current_price))
            
            # テイクプロフィットチェック
            for tp in position.metadata["take_profits"]:
                tp_price = Decimal(str(tp["price"]))
                if position.direction == "long":
                    if current_price >= tp_price:
                        positions_to_close.append((position, ExitReason.TAKE_PROFIT, tp_price))
                        break
                else:
                    if current_price <= tp_price:
                        positions_to_close.append((position, ExitReason.TAKE_PROFIT, tp_price))
                        break
        
        # ポジションクローズ
        for position, reason, exit_price in positions_to_close:
            await self._close_position(position, exit_price, timestamp, reason)
    
    async def _close_position(
        self,
        position: BacktestTrade,
        exit_price: Decimal,
        timestamp: datetime,
        reason: ExitReason
    ):
        """ポジションをクローズ"""
        # スリッページ適用
        if position.direction == "long":
            exit_price -= Decimal(str(self.config.slippage / 100))
        else:
            exit_price += Decimal(str(self.config.slippage / 100))
        
        # PnL計算
        if position.direction == "long":
            pnl_pips = float(exit_price - position.entry_price) * 100
        else:
            pnl_pips = float(position.entry_price - exit_price) * 100
        
        pnl = Decimal(str(pnl_pips * float(position.size)))
        pnl_percentage = (pnl / (position.entry_price * position.size)) * 100
        
        # 取引更新
        position.exit_time = timestamp
        position.exit_price = exit_price
        position.pnl = pnl
        position.pnl_percentage = pnl_percentage
        position.exit_reason = reason
        position.status = TradeStatus.CLOSED
        
        # エクイティ更新
        self.current_equity += pnl - self.config.commission
        
        # 連続勝敗カウント
        if pnl > 0:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            self.max_consecutive_wins = max(self.max_consecutive_wins, self.consecutive_wins)
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            self.max_consecutive_losses = max(self.max_consecutive_losses, self.consecutive_losses)
        
        # リストから移動
        self.open_positions.remove(position)
        self.closed_trades.append(position)
    
    async def _close_all_positions(self, timestamp: datetime):
        """すべてのポジションをクローズ"""
        for position in list(self.open_positions):
            # 現在価格で決済（実際は最終価格を使用すべき）
            await self._close_position(
                position,
                position.entry_price,  # 簡略化
                timestamp,
                ExitReason.SYSTEM
            )
    
    def _calculate_position_size(self, signal: EntrySignal) -> Decimal:
        """ポジションサイズを計算"""
        if self.config.use_fixed_size:
            return self.config.position_size
        else:
            # リスクベースサイジング
            if self.config.risk_per_trade:
                risk_amount = self.current_equity * self.config.risk_per_trade / 100
                sl_pips = signal.stop_loss.distance_pips
                if sl_pips > 0:
                    return risk_amount / Decimal(str(sl_pips))
            return self.config.position_size
    
    def _update_equity_curve(self, timestamp: datetime):
        """エクイティカーブを更新"""
        # ドローダウン計算
        if self.current_equity > self.max_equity:
            self.max_equity = self.current_equity
        
        drawdown = self.max_equity - self.current_equity
        drawdown_percent = (drawdown / self.max_equity * 100) if self.max_equity > 0 else Decimal("0")
        
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
        
        # エクイティポイント追加
        self.equity_curve.append(EquityPoint(
            timestamp=timestamp,
            equity=self.current_equity,
            drawdown=drawdown,
            trade_count=len(self.closed_trades)
        ))
    
    def _calculate_results(self) -> BacktestResult:
        """最終結果を計算"""
        # パフォーマンスメトリクス計算
        performance = self._calculate_performance_metrics()
        
        # パターン分析
        pattern_analysis = self._analyze_patterns()
        
        # 時間分析
        time_analysis = self._analyze_time()
        
        # 月次リターン
        monthly_returns = self._calculate_monthly_returns()
        
        # サマリー
        summary = {
            "total_days": (self.config.end_date - self.config.start_date).days,
            "trading_days": len(set(t.entry_time.date() for t in self.closed_trades)),
            "avg_trades_per_day": len(self.closed_trades) / max(1, (self.config.end_date - self.config.start_date).days),
            "final_equity": float(self.current_equity),
            "total_return": float((self.current_equity - self.config.initial_capital) / self.config.initial_capital * 100),
            "best_month": max(monthly_returns.items(), key=lambda x: x[1])[0] if monthly_returns else None,
            "worst_month": min(monthly_returns.items(), key=lambda x: x[1])[0] if monthly_returns else None
        }
        
        return BacktestResult(
            config=self.config,
            performance=performance,
            trades=self.closed_trades,
            pattern_analysis=pattern_analysis,
            time_analysis=time_analysis,
            equity_curve=self.equity_curve,
            monthly_returns=monthly_returns,
            summary=summary
        )
    
    def _calculate_performance_metrics(self) -> PerformanceMetrics:
        """パフォーマンスメトリクスを計算"""
        if not self.closed_trades:
            return self._empty_performance_metrics()
        
        # 基本統計
        winning_trades = [t for t in self.closed_trades if t.pnl > 0]
        losing_trades = [t for t in self.closed_trades if t.pnl <= 0]
        
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = sum(t.pnl for t in losing_trades)
        net_profit = gross_profit + gross_loss
        
        # 平均値
        avg_win = gross_profit / len(winning_trades) if winning_trades else Decimal("0")
        avg_loss = gross_loss / len(losing_trades) if losing_trades else Decimal("0")
        avg_trade = net_profit / len(self.closed_trades)
        
        # リスクリワード
        rr_ratios = []
        for trade in self.closed_trades:
            if trade.metadata.get("stop_loss"):
                sl_distance = abs(float(trade.entry_price) - trade.metadata["stop_loss"]) * 100
                exit_distance = abs(float(trade.exit_price) - float(trade.entry_price)) * 100
                if sl_distance > 0:
                    rr_ratios.append(exit_distance / sl_distance)
        
        avg_rr = sum(rr_ratios) / len(rr_ratios) if rr_ratios else 0
        
        # その他メトリクス
        profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else 999.99
        win_rate = len(winning_trades) / len(self.closed_trades)
        
        # シャープレシオ（簡易版）
        returns = [(t.pnl / self.config.initial_capital) for t in self.closed_trades]
        if len(returns) > 1:
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe_ratio = 0
        
        # 保有時間
        holding_times = [
            (t.exit_time - t.entry_time).total_seconds() / 60
            for t in self.closed_trades
            if t.exit_time
        ]
        avg_holding_time = sum(holding_times) / len(holding_times) if holding_times else 0
        
        return PerformanceMetrics(
            total_trades=len(self.closed_trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            net_profit=net_profit,
            profit_factor=profit_factor,
            max_drawdown=self.max_drawdown,
            max_drawdown_percent=float(self.max_drawdown / self.config.initial_capital * 100),
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=0,  # TODO: 実装
            calmar_ratio=0,  # TODO: 実装
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_trade=avg_trade,
            avg_rr_realized=avg_rr,
            best_trade=max(t.pnl for t in self.closed_trades) if self.closed_trades else Decimal("0"),
            worst_trade=min(t.pnl for t in self.closed_trades) if self.closed_trades else Decimal("0"),
            max_consecutive_wins=self.max_consecutive_wins,
            max_consecutive_losses=self.max_consecutive_losses,
            avg_holding_time=avg_holding_time,
            total_commission=self.config.commission * len(self.closed_trades) * 2,
            total_slippage=self.config.slippage * len(self.closed_trades) * 2
        )
    
    def _empty_performance_metrics(self) -> PerformanceMetrics:
        """空のパフォーマンスメトリクス"""
        return PerformanceMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0,
            gross_profit=Decimal("0"),
            gross_loss=Decimal("0"),
            net_profit=Decimal("0"),
            profit_factor=0,
            max_drawdown=Decimal("0"),
            max_drawdown_percent=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            calmar_ratio=0,
            avg_win=Decimal("0"),
            avg_loss=Decimal("0"),
            avg_trade=Decimal("0"),
            avg_rr_realized=0,
            best_trade=Decimal("0"),
            worst_trade=Decimal("0"),
            max_consecutive_wins=0,
            max_consecutive_losses=0,
            avg_holding_time=0,
            total_commission=Decimal("0"),
            total_slippage=Decimal("0")
        )
    
    def _analyze_patterns(self) -> List[PatternPerformance]:
        """パターン別パフォーマンスを分析"""
        pattern_stats = {}
        
        for trade in self.closed_trades:
            pattern = trade.pattern
            if pattern not in pattern_stats:
                pattern_stats[pattern] = {
                    "trades": [],
                    "count": 0,
                    "wins": 0,
                    "total_profit": Decimal("0"),
                    "holding_times": []
                }
            
            stats = pattern_stats[pattern]
            stats["trades"].append(trade)
            stats["count"] += 1
            if trade.pnl > 0:
                stats["wins"] += 1
            stats["total_profit"] += trade.pnl
            
            if trade.exit_time:
                holding_time = (trade.exit_time - trade.entry_time).total_seconds() / 60
                stats["holding_times"].append(holding_time)
        
        # 集計
        results = []
        for pattern, stats in pattern_stats.items():
            results.append(PatternPerformance(
                pattern_type=pattern,
                count=stats["count"],
                win_rate=stats["wins"] / stats["count"] if stats["count"] > 0 else 0,
                avg_profit=stats["total_profit"] / stats["count"] if stats["count"] > 0 else Decimal("0"),
                total_profit=stats["total_profit"],
                avg_holding_time=sum(stats["holding_times"]) / len(stats["holding_times"]) if stats["holding_times"] else 0,
                best_trade=max(t.pnl for t in stats["trades"]) if stats["trades"] else Decimal("0"),
                worst_trade=min(t.pnl for t in stats["trades"]) if stats["trades"] else Decimal("0")
            ))
        
        return sorted(results, key=lambda x: x.total_profit, reverse=True)
    
    def _analyze_time(self) -> List[TimeAnalysis]:
        """時間帯別分析"""
        hour_stats = {}
        
        for trade in self.closed_trades:
            hour = trade.entry_time.hour
            if hour not in hour_stats:
                hour_stats[hour] = {
                    "count": 0,
                    "wins": 0,
                    "total_profit": Decimal("0")
                }
            
            stats = hour_stats[hour]
            stats["count"] += 1
            if trade.pnl > 0:
                stats["wins"] += 1
            stats["total_profit"] += trade.pnl
        
        # 集計
        results = []
        for hour, stats in hour_stats.items():
            results.append(TimeAnalysis(
                hour=hour,
                trade_count=stats["count"],
                win_rate=stats["wins"] / stats["count"] if stats["count"] > 0 else 0,
                avg_profit=stats["total_profit"] / stats["count"] if stats["count"] > 0 else Decimal("0")
            ))
        
        return sorted(results, key=lambda x: x.hour)
    
    def _calculate_monthly_returns(self) -> Dict[str, Decimal]:
        """月次リターンを計算"""
        monthly_returns = {}
        
        # エクイティカーブから月末値を取得
        for point in self.equity_curve:
            month_key = point.timestamp.strftime("%Y-%m")
            monthly_returns[month_key] = point.equity
        
        # リターン率に変換
        sorted_months = sorted(monthly_returns.keys())
        for i, month in enumerate(sorted_months):
            if i == 0:
                prev_equity = self.config.initial_capital
            else:
                prev_equity = monthly_returns[sorted_months[i-1]]
            
            current_equity = monthly_returns[month]
            monthly_returns[month] = (current_equity - prev_equity) / prev_equity * 100
        
        return monthly_returns