"""バックテスト関連のドメインモデル"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from enum import Enum


class TradeStatus(Enum):
    """取引ステータス"""
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class ExitReason(Enum):
    """決済理由"""
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    MANUAL = "manual"
    TIMEOUT = "timeout"
    SYSTEM = "system"


@dataclass
class BacktestTrade:
    """バックテストの取引記録"""
    id: str
    entry_time: datetime
    exit_time: Optional[datetime]
    symbol: str
    direction: str  # "long" or "short"
    entry_price: Decimal
    exit_price: Optional[Decimal]
    size: Decimal
    pnl: Optional[Decimal]
    pnl_percentage: Optional[Decimal]
    pattern: str
    entry_score: float
    exit_reason: Optional[ExitReason]
    status: TradeStatus
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """パフォーマンスメトリクス"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    gross_profit: Decimal
    gross_loss: Decimal
    net_profit: Decimal
    profit_factor: float
    max_drawdown: Decimal
    max_drawdown_percent: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    avg_win: Decimal
    avg_loss: Decimal
    avg_trade: Decimal
    avg_rr_realized: float
    best_trade: Decimal
    worst_trade: Decimal
    max_consecutive_wins: int
    max_consecutive_losses: int
    avg_holding_time: float  # in minutes
    total_commission: Decimal
    total_slippage: Decimal
    
    
@dataclass
class PatternPerformance:
    """パターン別パフォーマンス"""
    pattern_type: str
    count: int
    win_rate: float
    avg_profit: Decimal
    total_profit: Decimal
    avg_holding_time: float
    best_trade: Decimal
    worst_trade: Decimal
    

@dataclass
class TimeAnalysis:
    """時間帯別分析"""
    hour: int
    trade_count: int
    win_rate: float
    avg_profit: Decimal
    

@dataclass
class EquityPoint:
    """エクイティカーブのポイント"""
    timestamp: datetime
    equity: Decimal
    drawdown: Decimal
    trade_count: int
    

@dataclass
class BacktestConfig:
    """バックテスト設定"""
    symbol: str
    start_date: datetime
    end_date: datetime
    initial_capital: Decimal
    position_size: Decimal  # Fixed size or percentage
    commission: Decimal  # Per trade commission
    slippage: Decimal  # Expected slippage in pips
    max_positions: int
    use_fixed_size: bool  # True: fixed size, False: percentage
    risk_per_trade: Optional[Decimal] = None  # Risk percentage if using risk-based sizing
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestResult:
    """バックテスト結果"""
    config: BacktestConfig
    performance: PerformanceMetrics
    trades: List[BacktestTrade]
    pattern_analysis: List[PatternPerformance]
    time_analysis: List[TimeAnalysis]
    equity_curve: List[EquityPoint]
    monthly_returns: Dict[str, Decimal]
    summary: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "config": {
                "symbol": self.config.symbol,
                "start_date": self.config.start_date.isoformat(),
                "end_date": self.config.end_date.isoformat(),
                "initial_capital": str(self.config.initial_capital),
                "position_size": str(self.config.position_size),
                "parameters": self.config.parameters
            },
            "performance": {
                "total_trades": self.performance.total_trades,
                "winning_trades": self.performance.winning_trades,
                "losing_trades": self.performance.losing_trades,
                "win_rate": self.performance.win_rate,
                "gross_profit": str(self.performance.gross_profit),
                "gross_loss": str(self.performance.gross_loss),
                "net_profit": str(self.performance.net_profit),
                "profit_factor": self.performance.profit_factor,
                "max_drawdown": str(self.performance.max_drawdown),
                "max_drawdown_percent": self.performance.max_drawdown_percent,
                "sharpe_ratio": self.performance.sharpe_ratio,
                "avg_win": str(self.performance.avg_win),
                "avg_loss": str(self.performance.avg_loss),
                "avg_rr_realized": self.performance.avg_rr_realized
            },
            "pattern_analysis": [
                {
                    "pattern_type": p.pattern_type,
                    "count": p.count,
                    "win_rate": p.win_rate,
                    "avg_profit": str(p.avg_profit),
                    "total_profit": str(p.total_profit)
                }
                for p in self.pattern_analysis
            ],
            "trades": [
                {
                    "id": t.id,
                    "entry_time": t.entry_time.isoformat(),
                    "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                    "symbol": t.symbol,
                    "direction": t.direction,
                    "entry_price": str(t.entry_price),
                    "exit_price": str(t.exit_price) if t.exit_price else None,
                    "size": str(t.size),
                    "pnl": str(t.pnl) if t.pnl else None,
                    "pattern": t.pattern,
                    "entry_score": t.entry_score
                }
                for t in self.trades[:100]  # 最初の100件のみ
            ],
            "equity_curve": [
                {
                    "date": ep.timestamp.date().isoformat(),
                    "equity": str(ep.equity)
                }
                for ep in self.equity_curve[::10]  # 10件毎にサンプリング
            ],
            "summary": self.summary
        }


@dataclass
class OptimizationResult:
    """最適化結果"""
    best_parameters: Dict[str, Any]
    best_performance: PerformanceMetrics
    all_results: List[Dict[str, Any]]
    optimization_time: float  # seconds