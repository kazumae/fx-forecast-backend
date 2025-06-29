"""バックテストレポート生成"""
import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path

from src.domain.models.backtest import BacktestResult, OptimizationResult


class BacktestReportGenerator:
    """バックテストレポート生成"""
    
    def __init__(self, output_dir: str = "reports/backtest"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_report(
        self,
        result: BacktestResult,
        report_name: str = None,
        include_trades: bool = True,
        include_charts: bool = True
    ) -> Dict[str, str]:
        """包括的なレポートを生成"""
        if report_name is None:
            report_name = f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        report_dir = self.output_dir / report_name
        report_dir.mkdir(exist_ok=True)
        
        # 生成されたファイルパス
        generated_files = {}
        
        # 1. サマリーレポート（JSON）
        summary_path = report_dir / "summary.json"
        self._save_summary(result, summary_path)
        generated_files["summary"] = str(summary_path)
        
        # 2. パフォーマンスメトリクス（CSV）
        metrics_path = report_dir / "performance_metrics.csv"
        self._save_performance_metrics(result, metrics_path)
        generated_files["metrics"] = str(metrics_path)
        
        # 3. 取引履歴（CSV）
        if include_trades:
            trades_path = report_dir / "trades.csv"
            self._save_trades(result, trades_path)
            generated_files["trades"] = str(trades_path)
        
        # 4. パターン分析（CSV）
        pattern_path = report_dir / "pattern_analysis.csv"
        self._save_pattern_analysis(result, pattern_path)
        generated_files["pattern_analysis"] = str(pattern_path)
        
        # 5. 時間分析（CSV）
        time_path = report_dir / "time_analysis.csv"
        self._save_time_analysis(result, time_path)
        generated_files["time_analysis"] = str(time_path)
        
        # 6. チャート生成
        if include_charts:
            # エクイティカーブ
            equity_chart_path = report_dir / "equity_curve.png"
            self._plot_equity_curve(result, equity_chart_path)
            generated_files["equity_curve_chart"] = str(equity_chart_path)
            
            # ドローダウンチャート
            drawdown_chart_path = report_dir / "drawdown.png"
            self._plot_drawdown(result, drawdown_chart_path)
            generated_files["drawdown_chart"] = str(drawdown_chart_path)
            
            # 月次リターン
            monthly_chart_path = report_dir / "monthly_returns.png"
            self._plot_monthly_returns(result, monthly_chart_path)
            generated_files["monthly_returns_chart"] = str(monthly_chart_path)
            
            # パターン別パフォーマンス
            pattern_chart_path = report_dir / "pattern_performance.png"
            self._plot_pattern_performance(result, pattern_chart_path)
            generated_files["pattern_performance_chart"] = str(pattern_chart_path)
        
        # 7. HTMLレポート
        html_path = report_dir / "report.html"
        self._generate_html_report(result, html_path, generated_files)
        generated_files["html_report"] = str(html_path)
        
        return generated_files
    
    def _save_summary(self, result: BacktestResult, path: Path):
        """サマリーをJSON形式で保存"""
        summary = result.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
    
    def _save_performance_metrics(self, result: BacktestResult, path: Path):
        """パフォーマンスメトリクスをCSVで保存"""
        metrics = result.performance
        data = {
            "総取引数": metrics.total_trades,
            "勝ち取引": metrics.winning_trades,
            "負け取引": metrics.losing_trades,
            "勝率": f"{metrics.win_rate:.2%}",
            "総利益": float(metrics.gross_profit),
            "総損失": float(metrics.gross_loss),
            "純利益": float(metrics.net_profit),
            "プロフィットファクター": metrics.profit_factor,
            "最大ドローダウン": float(metrics.max_drawdown),
            "最大ドローダウン率": f"{metrics.max_drawdown_percent:.2%}",
            "シャープレシオ": metrics.sharpe_ratio,
            "平均利益": float(metrics.avg_win),
            "平均損失": float(metrics.avg_loss),
            "平均取引": float(metrics.avg_trade),
            "実現平均RR": metrics.avg_rr_realized,
            "最大連勝": metrics.max_consecutive_wins,
            "最大連敗": metrics.max_consecutive_losses,
            "平均保有時間（分）": metrics.avg_holding_time
        }
        
        df = pd.DataFrame([data]).T
        df.columns = ["値"]
        df.to_csv(path, encoding="utf-8-sig")
    
    def _save_trades(self, result: BacktestResult, path: Path):
        """取引履歴をCSVで保存"""
        trades_data = []
        for trade in result.trades:
            trades_data.append({
                "ID": trade.id,
                "エントリー時刻": trade.entry_time,
                "決済時刻": trade.exit_time,
                "方向": trade.direction,
                "エントリー価格": float(trade.entry_price),
                "決済価格": float(trade.exit_price) if trade.exit_price else None,
                "サイズ": float(trade.size),
                "損益": float(trade.pnl) if trade.pnl else None,
                "損益率": f"{float(trade.pnl_percentage):.2f}%" if trade.pnl_percentage else None,
                "パターン": trade.pattern,
                "スコア": trade.entry_score,
                "決済理由": trade.exit_reason.value if trade.exit_reason else None
            })
        
        df = pd.DataFrame(trades_data)
        df.to_csv(path, index=False, encoding="utf-8-sig")
    
    def _save_pattern_analysis(self, result: BacktestResult, path: Path):
        """パターン分析をCSVで保存"""
        pattern_data = []
        for pattern in result.pattern_analysis:
            pattern_data.append({
                "パターン": pattern.pattern_type,
                "取引数": pattern.count,
                "勝率": f"{pattern.win_rate:.2%}",
                "平均利益": float(pattern.avg_profit),
                "総利益": float(pattern.total_profit),
                "平均保有時間": pattern.avg_holding_time,
                "最良取引": float(pattern.best_trade),
                "最悪取引": float(pattern.worst_trade)
            })
        
        df = pd.DataFrame(pattern_data)
        df.to_csv(path, index=False, encoding="utf-8-sig")
    
    def _save_time_analysis(self, result: BacktestResult, path: Path):
        """時間分析をCSVで保存"""
        time_data = []
        for time_stat in result.time_analysis:
            time_data.append({
                "時間": f"{time_stat.hour:02d}:00",
                "取引数": time_stat.trade_count,
                "勝率": f"{time_stat.win_rate:.2%}",
                "平均利益": float(time_stat.avg_profit)
            })
        
        df = pd.DataFrame(time_data)
        df.to_csv(path, index=False, encoding="utf-8-sig")
    
    def _plot_equity_curve(self, result: BacktestResult, path: Path):
        """エクイティカーブをプロット"""
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # データ準備
        dates = [ep.timestamp for ep in result.equity_curve]
        equity = [float(ep.equity) for ep in result.equity_curve]
        
        # プロット
        ax.plot(dates, equity, linewidth=2, color='blue')
        ax.fill_between(dates, equity, float(result.config.initial_capital), 
                       where=[e >= float(result.config.initial_capital) for e in equity],
                       color='green', alpha=0.3, label='利益')
        ax.fill_between(dates, equity, float(result.config.initial_capital),
                       where=[e < float(result.config.initial_capital) for e in equity],
                       color='red', alpha=0.3, label='損失')
        
        # 初期資本ライン
        ax.axhline(y=float(result.config.initial_capital), color='black', 
                  linestyle='--', alpha=0.5, label='初期資本')
        
        # フォーマット
        ax.set_title('エクイティカーブ', fontsize=16, fontweight='bold')
        ax.set_xlabel('日付', fontsize=12)
        ax.set_ylabel('資産額', fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # 日付フォーマット
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_drawdown(self, result: BacktestResult, path: Path):
        """ドローダウンチャートをプロット"""
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # データ準備
        dates = [ep.timestamp for ep in result.equity_curve]
        drawdowns = [-float(ep.drawdown) for ep in result.equity_curve]
        
        # プロット
        ax.fill_between(dates, 0, drawdowns, color='red', alpha=0.5)
        ax.plot(dates, drawdowns, color='darkred', linewidth=2)
        
        # 最大ドローダウン表示
        max_dd_idx = drawdowns.index(min(drawdowns))
        ax.annotate(f'最大DD: {min(drawdowns):.2f}',
                   xy=(dates[max_dd_idx], drawdowns[max_dd_idx]),
                   xytext=(10, -30), textcoords='offset points',
                   bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5),
                   arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
        
        # フォーマット
        ax.set_title('ドローダウン', fontsize=16, fontweight='bold')
        ax.set_xlabel('日付', fontsize=12)
        ax.set_ylabel('ドローダウン', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(top=0)
        
        # 日付フォーマット
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_monthly_returns(self, result: BacktestResult, path: Path):
        """月次リターンをプロット"""
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # データ準備
        months = list(result.monthly_returns.keys())
        returns = [float(r) for r in result.monthly_returns.values()]
        
        # カラーマップ
        colors = ['green' if r >= 0 else 'red' for r in returns]
        
        # プロット
        bars = ax.bar(months, returns, color=colors, alpha=0.7)
        
        # 値表示
        for bar, ret in zip(bars, returns):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{ret:.1f}%', ha='center', 
                   va='bottom' if height >= 0 else 'top')
        
        # フォーマット
        ax.set_title('月次リターン', fontsize=16, fontweight='bold')
        ax.set_xlabel('月', fontsize=12)
        ax.set_ylabel('リターン (%)', fontsize=12)
        ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_pattern_performance(self, result: BacktestResult, path: Path):
        """パターン別パフォーマンスをプロット"""
        if not result.pattern_analysis:
            return
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        
        # データ準備
        patterns = [p.pattern_type for p in result.pattern_analysis]
        counts = [p.count for p in result.pattern_analysis]
        win_rates = [p.win_rate for p in result.pattern_analysis]
        avg_profits = [float(p.avg_profit) for p in result.pattern_analysis]
        total_profits = [float(p.total_profit) for p in result.pattern_analysis]
        
        # 1. 取引数
        ax1.bar(patterns, counts, color='skyblue', alpha=0.7)
        ax1.set_title('パターン別取引数', fontsize=14)
        ax1.set_ylabel('取引数')
        ax1.tick_params(axis='x', rotation=45)
        
        # 2. 勝率
        ax2.bar(patterns, [w*100 for w in win_rates], color='lightgreen', alpha=0.7)
        ax2.set_title('パターン別勝率', fontsize=14)
        ax2.set_ylabel('勝率 (%)')
        ax2.axhline(y=50, color='red', linestyle='--', alpha=0.5)
        ax2.tick_params(axis='x', rotation=45)
        
        # 3. 平均利益
        colors = ['green' if p >= 0 else 'red' for p in avg_profits]
        ax3.bar(patterns, avg_profits, color=colors, alpha=0.7)
        ax3.set_title('パターン別平均利益', fontsize=14)
        ax3.set_ylabel('平均利益')
        ax3.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax3.tick_params(axis='x', rotation=45)
        
        # 4. 総利益
        colors = ['green' if p >= 0 else 'red' for p in total_profits]
        ax4.bar(patterns, total_profits, color=colors, alpha=0.7)
        ax4.set_title('パターン別総利益', fontsize=14)
        ax4.set_ylabel('総利益')
        ax4.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax4.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def _generate_html_report(
        self,
        result: BacktestResult,
        path: Path,
        generated_files: Dict[str, str]
    ):
        """HTMLレポートを生成"""
        html_content = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>バックテストレポート - {result.config.symbol}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        h1, h2 {{
            color: #333;
        }}
        .metric {{
            display: inline-block;
            margin: 10px 20px 10px 0;
            padding: 10px;
            background-color: #f0f0f0;
            border-radius: 5px;
        }}
        .metric-label {{
            font-size: 12px;
            color: #666;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }}
        .positive {{
            color: #4CAF50;
        }}
        .negative {{
            color: #f44336;
        }}
        img {{
            max-width: 100%;
            height: auto;
            margin: 20px 0;
            border: 1px solid #ddd;
            border-radius: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f0f0f0;
            font-weight: bold;
        }}
        .section {{
            margin: 30px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>バックテストレポート</h1>
        
        <div class="section">
            <h2>設定</h2>
            <p><strong>シンボル:</strong> {result.config.symbol}</p>
            <p><strong>期間:</strong> {result.config.start_date.strftime('%Y-%m-%d')} 〜 {result.config.end_date.strftime('%Y-%m-%d')}</p>
            <p><strong>初期資本:</strong> ${result.config.initial_capital:,.2f}</p>
        </div>
        
        <div class="section">
            <h2>主要メトリクス</h2>
            <div class="metric">
                <div class="metric-label">純利益</div>
                <div class="metric-value {'positive' if result.performance.net_profit >= 0 else 'negative'}">
                    ${result.performance.net_profit:,.2f}
                </div>
            </div>
            <div class="metric">
                <div class="metric-label">勝率</div>
                <div class="metric-value">{result.performance.win_rate:.1%}</div>
            </div>
            <div class="metric">
                <div class="metric-label">シャープレシオ</div>
                <div class="metric-value">{result.performance.sharpe_ratio:.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">最大DD</div>
                <div class="metric-value negative">{result.performance.max_drawdown_percent:.1f}%</div>
            </div>
            <div class="metric">
                <div class="metric-label">取引数</div>
                <div class="metric-value">{result.performance.total_trades}</div>
            </div>
        </div>
        
        <div class="section">
            <h2>エクイティカーブ</h2>
            <img src="equity_curve.png" alt="エクイティカーブ">
        </div>
        
        <div class="section">
            <h2>ドローダウン</h2>
            <img src="drawdown.png" alt="ドローダウン">
        </div>
        
        <div class="section">
            <h2>月次リターン</h2>
            <img src="monthly_returns.png" alt="月次リターン">
        </div>
        
        <div class="section">
            <h2>パターン別パフォーマンス</h2>
            <img src="pattern_performance.png" alt="パターン別パフォーマンス">
        </div>
        
        <div class="section">
            <h2>詳細データ</h2>
            <ul>
                <li><a href="summary.json">サマリー (JSON)</a></li>
                <li><a href="performance_metrics.csv">パフォーマンスメトリクス (CSV)</a></li>
                <li><a href="trades.csv">取引履歴 (CSV)</a></li>
                <li><a href="pattern_analysis.csv">パターン分析 (CSV)</a></li>
                <li><a href="time_analysis.csv">時間分析 (CSV)</a></li>
            </ul>
        </div>
    </div>
</body>
</html>
"""
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)
    
    def generate_optimization_report(
        self,
        result: OptimizationResult,
        report_name: str = None
    ) -> Dict[str, str]:
        """最適化レポートを生成"""
        if report_name is None:
            report_name = f"optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        report_dir = self.output_dir / report_name
        report_dir.mkdir(exist_ok=True)
        
        generated_files = {}
        
        # 最適化結果サマリー
        summary_data = {
            "best_parameters": result.best_parameters,
            "optimization_time": result.optimization_time,
            "total_combinations": len(result.all_results),
            "best_performance": {
                "sharpe_ratio": result.best_performance.sharpe_ratio,
                "profit_factor": result.best_performance.profit_factor,
                "win_rate": result.best_performance.win_rate,
                "net_profit": float(result.best_performance.net_profit),
                "max_drawdown": float(result.best_performance.max_drawdown_percent)
            }
        }
        
        summary_path = report_dir / "optimization_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)
        generated_files["summary"] = str(summary_path)
        
        # トップ10結果
        top10_path = report_dir / "top10_results.csv"
        top10_data = []
        for res in result.all_results[:10]:
            row = res["parameters"].copy()
            row.update({
                "metric_value": res["metric_value"],
                "sharpe_ratio": res["performance"].sharpe_ratio,
                "win_rate": res["performance"].win_rate,
                "net_profit": float(res["performance"].net_profit)
            })
            top10_data.append(row)
        
        df = pd.DataFrame(top10_data)
        df.to_csv(top10_path, index=False, encoding="utf-8-sig")
        generated_files["top10"] = str(top10_path)
        
        return generated_files