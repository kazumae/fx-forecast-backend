"""バックテスト実行スクリプト"""
import asyncio
import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import pandas as pd

from src.domain.models.backtest import BacktestConfig
from src.services.backtest import (
    BacktestEngine,
    ParameterOptimizer,
    WalkForwardAnalyzer,
    BacktestReportGenerator
)
from src.domain.models.zone import Zone, ZoneType, ZoneStatus


async def load_market_data(file_path: str) -> pd.DataFrame:
    """市場データを読み込み"""
    df = pd.read_csv(file_path, parse_dates=['timestamp'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    return df


def load_zones(file_path: str = None) -> list:
    """ゾーンデータを読み込み（簡易版）"""
    # 実際の実装ではデータベースやファイルから読み込む
    zones = [
        Zone(
            id="zone_001",
            symbol="XAUUSD",
            upper_bound=Decimal("3285.00"),
            lower_bound=Decimal("3283.00"),
            zone_type=ZoneType.RESISTANCE,
            strength=0.85,
            touch_count=4,
            status=ZoneStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            last_touched=datetime.now(timezone.utc)
        ),
        Zone(
            id="zone_002",
            symbol="XAUUSD",
            upper_bound=Decimal("3270.00"),
            lower_bound=Decimal("3268.00"),
            zone_type=ZoneType.SUPPORT,
            strength=0.90,
            touch_count=5,
            status=ZoneStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            last_touched=datetime.now(timezone.utc)
        )
    ]
    return zones


async def run_single_backtest(args):
    """単一バックテストを実行"""
    # データ読み込み
    print(f"市場データを読み込み中: {args.data}")
    data = await load_market_data(args.data)
    zones = load_zones(args.zones)
    
    # 設定作成
    config = BacktestConfig(
        symbol=args.symbol,
        start_date=datetime.fromisoformat(args.start_date).replace(tzinfo=timezone.utc),
        end_date=datetime.fromisoformat(args.end_date).replace(tzinfo=timezone.utc),
        initial_capital=Decimal(args.initial_capital),
        position_size=Decimal(args.position_size),
        commission=Decimal(args.commission),
        slippage=Decimal(args.slippage),
        max_positions=args.max_positions,
        use_fixed_size=not args.risk_based,
        risk_per_trade=Decimal(args.risk_per_trade) if args.risk_based else None,
        parameters={
            "min_confidence": args.min_confidence,
            "min_rr_ratio": args.min_rr_ratio,
            "max_risk_pips": args.max_risk_pips,
            "enable_zone_validation": True,
            "enable_trend_filter": True
        }
    )
    
    # バックテスト実行
    print("バックテストを実行中...")
    engine = BacktestEngine(config)
    result = await engine.run(data, zones, config.parameters)
    
    # 結果表示
    print("\n=== バックテスト結果 ===")
    print(f"期間: {config.start_date.date()} ~ {config.end_date.date()}")
    print(f"初期資本: ${config.initial_capital:,.2f}")
    print(f"最終資本: ${result.equity_curve[-1].equity:,.2f}")
    print(f"\n--- パフォーマンス ---")
    print(f"総取引数: {result.performance.total_trades}")
    print(f"勝率: {result.performance.win_rate:.1%}")
    print(f"純利益: ${result.performance.net_profit:,.2f}")
    print(f"プロフィットファクター: {result.performance.profit_factor:.2f}")
    print(f"シャープレシオ: {result.performance.sharpe_ratio:.2f}")
    print(f"最大ドローダウン: {result.performance.max_drawdown_percent:.1f}%")
    
    # レポート生成
    if args.report:
        print(f"\nレポートを生成中: {args.report_dir}")
        generator = BacktestReportGenerator(output_dir=args.report_dir)
        files = generator.generate_report(
            result,
            report_name=f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            include_trades=True,
            include_charts=True
        )
        print("生成されたファイル:")
        for name, path in files.items():
            print(f"  - {name}: {path}")


async def run_optimization(args):
    """パラメータ最適化を実行"""
    # データ読み込み
    print(f"市場データを読み込み中: {args.data}")
    data = await load_market_data(args.data)
    zones = load_zones(args.zones)
    
    # ベース設定
    base_config = BacktestConfig(
        symbol=args.symbol,
        start_date=datetime.fromisoformat(args.start_date).replace(tzinfo=timezone.utc),
        end_date=datetime.fromisoformat(args.end_date).replace(tzinfo=timezone.utc),
        initial_capital=Decimal(args.initial_capital),
        position_size=Decimal(args.position_size),
        commission=Decimal(args.commission),
        slippage=Decimal(args.slippage),
        max_positions=args.max_positions,
        use_fixed_size=not args.risk_based,
        risk_per_trade=Decimal(args.risk_per_trade) if args.risk_based else None
    )
    
    # パラメータ範囲
    param_ranges = json.loads(args.param_ranges)
    
    # 最適化実行
    print(f"最適化を実行中（評価指標: {args.metric}）...")
    optimizer = ParameterOptimizer(
        base_config=base_config,
        parameter_ranges=param_ranges,
        optimization_metric=args.metric,
        n_jobs=args.jobs
    )
    
    result = await optimizer.optimize(
        data,
        zones,
        validation_split=args.validation_split
    )
    
    # 結果表示
    print("\n=== 最適化結果 ===")
    print(f"最適化時間: {result.optimization_time:.1f}秒")
    print(f"テストした組み合わせ数: {len(result.all_results)}")
    print(f"\n最適パラメータ:")
    for key, value in result.best_parameters.items():
        print(f"  {key}: {value}")
    
    print(f"\n最適パフォーマンス:")
    print(f"  {args.metric}: {optimizer._get_metric_value(result.best_performance):.3f}")
    print(f"  勝率: {result.best_performance.win_rate:.1%}")
    print(f"  シャープレシオ: {result.best_performance.sharpe_ratio:.2f}")
    print(f"  最大DD: {result.best_performance.max_drawdown_percent:.1f}%")
    
    # トップ5表示
    print("\nトップ5の組み合わせ:")
    for i, res in enumerate(result.all_results[:5]):
        print(f"{i+1}. {res['parameters']} - {args.metric}: {res['metric_value']:.3f}")
    
    # レポート生成
    if args.report:
        print(f"\n最適化レポートを生成中: {args.report_dir}")
        generator = BacktestReportGenerator(output_dir=args.report_dir)
        files = generator.generate_optimization_report(result)
        print("生成されたファイル:")
        for name, path in files.items():
            print(f"  - {name}: {path}")


async def run_walk_forward(args):
    """ウォークフォワード分析を実行"""
    # データ読み込み
    print(f"市場データを読み込み中: {args.data}")
    data = await load_market_data(args.data)
    zones = load_zones(args.zones)
    
    # ベース設定
    base_config = BacktestConfig(
        symbol=args.symbol,
        start_date=data['timestamp'].min(),
        end_date=data['timestamp'].max(),
        initial_capital=Decimal(args.initial_capital),
        position_size=Decimal(args.position_size),
        commission=Decimal(args.commission),
        slippage=Decimal(args.slippage),
        max_positions=args.max_positions,
        use_fixed_size=True
    )
    
    # パラメータ範囲
    param_ranges = json.loads(args.param_ranges)
    
    # 最適化器作成
    optimizer = ParameterOptimizer(
        base_config=base_config,
        parameter_ranges=param_ranges,
        optimization_metric=args.metric
    )
    
    # ウォークフォワード分析
    print("ウォークフォワード分析を実行中...")
    analyzer = WalkForwardAnalyzer(
        optimizer=optimizer,
        window_size=args.window_size,
        step_size=args.step_size,
        optimization_period=args.optimization_period
    )
    
    result = await analyzer.analyze(data, zones)
    
    # 結果表示
    print("\n=== ウォークフォワード分析結果 ===")
    print(f"ウィンドウ数: {len(result['windows'])}")
    
    summary = result['summary']
    print(f"\n検証期間の平均パフォーマンス:")
    print(f"  平均シャープレシオ: {summary['avg_validation_sharpe']:.2f}")
    print(f"  平均勝率: {summary['avg_validation_win_rate']:.1%}")
    print(f"  総取引数: {summary['total_validation_trades']}")
    
    print(f"\nパラメータ安定性:")
    for param, stability in summary['parameter_stability'].items():
        print(f"  {param}: {stability['stability_score']:.1%} (ユニーク値: {stability['unique_values']})")
    
    # 各ウィンドウの結果
    print("\n各ウィンドウの詳細:")
    for window in result['windows']:
        print(f"\nウィンドウ {window['window']}:")
        print(f"  最適化期間: {window['optimization_period']['start']} ~ {window['optimization_period']['end']}")
        print(f"  検証期間: {window['validation_period']['start']} ~ {window['validation_period']['end']}")
        print(f"  最適パラメータ: {window['best_parameters']}")
        print(f"  検証シャープレシオ: {window['validation_performance'].sharpe_ratio:.2f}")


def main():
    parser = argparse.ArgumentParser(description="バックテスト実行ツール")
    subparsers = parser.add_subparsers(dest="command", help="実行するコマンド")
    
    # 単一バックテスト
    single_parser = subparsers.add_parser("single", help="単一バックテストを実行")
    single_parser.add_argument("--data", required=True, help="市場データファイル（CSV）")
    single_parser.add_argument("--zones", help="ゾーンデータファイル")
    single_parser.add_argument("--symbol", default="XAUUSD", help="シンボル")
    single_parser.add_argument("--start-date", required=True, help="開始日（YYYY-MM-DD）")
    single_parser.add_argument("--end-date", required=True, help="終了日（YYYY-MM-DD）")
    single_parser.add_argument("--initial-capital", default="10000", help="初期資本")
    single_parser.add_argument("--position-size", default="0.1", help="ポジションサイズ")
    single_parser.add_argument("--commission", default="2", help="手数料")
    single_parser.add_argument("--slippage", default="0.5", help="スリッページ（pips）")
    single_parser.add_argument("--max-positions", type=int, default=3, help="最大ポジション数")
    single_parser.add_argument("--risk-based", action="store_true", help="リスクベースサイジング")
    single_parser.add_argument("--risk-per-trade", default="2.0", help="取引あたりリスク（%）")
    single_parser.add_argument("--min-confidence", type=float, default=70.0, help="最小信頼度")
    single_parser.add_argument("--min-rr-ratio", type=float, default=1.5, help="最小RR比")
    single_parser.add_argument("--max-risk-pips", type=float, default=50.0, help="最大リスク（pips）")
    single_parser.add_argument("--report", action="store_true", help="レポート生成")
    single_parser.add_argument("--report-dir", default="reports/backtest", help="レポート出力先")
    
    # 最適化
    opt_parser = subparsers.add_parser("optimize", help="パラメータ最適化を実行")
    opt_parser.add_argument("--data", required=True, help="市場データファイル（CSV）")
    opt_parser.add_argument("--zones", help="ゾーンデータファイル")
    opt_parser.add_argument("--symbol", default="XAUUSD", help="シンボル")
    opt_parser.add_argument("--start-date", required=True, help="開始日（YYYY-MM-DD）")
    opt_parser.add_argument("--end-date", required=True, help="終了日（YYYY-MM-DD）")
    opt_parser.add_argument("--initial-capital", default="10000", help="初期資本")
    opt_parser.add_argument("--position-size", default="0.1", help="ポジションサイズ")
    opt_parser.add_argument("--commission", default="2", help="手数料")
    opt_parser.add_argument("--slippage", default="0.5", help="スリッページ（pips）")
    opt_parser.add_argument("--max-positions", type=int, default=3, help="最大ポジション数")
    opt_parser.add_argument("--risk-based", action="store_true", help="リスクベースサイジング")
    opt_parser.add_argument("--risk-per-trade", default="2.0", help="取引あたりリスク（%）")
    opt_parser.add_argument("--param-ranges", required=True, help="パラメータ範囲（JSON）")
    opt_parser.add_argument("--metric", default="sharpe_ratio", 
                          choices=["sharpe_ratio", "profit_factor", "win_rate", "net_profit"],
                          help="最適化指標")
    opt_parser.add_argument("--validation-split", type=float, default=0.2, help="検証データ割合")
    opt_parser.add_argument("--jobs", type=int, default=-1, help="並列ジョブ数")
    opt_parser.add_argument("--report", action="store_true", help="レポート生成")
    opt_parser.add_argument("--report-dir", default="reports/backtest", help="レポート出力先")
    
    # ウォークフォワード
    wf_parser = subparsers.add_parser("walk-forward", help="ウォークフォワード分析を実行")
    wf_parser.add_argument("--data", required=True, help="市場データファイル（CSV）")
    wf_parser.add_argument("--zones", help="ゾーンデータファイル")
    wf_parser.add_argument("--symbol", default="XAUUSD", help="シンボル")
    wf_parser.add_argument("--initial-capital", default="10000", help="初期資本")
    wf_parser.add_argument("--position-size", default="0.1", help="ポジションサイズ")
    wf_parser.add_argument("--commission", default="2", help="手数料")
    wf_parser.add_argument("--slippage", default="0.5", help="スリッページ（pips）")
    wf_parser.add_argument("--max-positions", type=int, default=3, help="最大ポジション数")
    wf_parser.add_argument("--param-ranges", required=True, help="パラメータ範囲（JSON）")
    wf_parser.add_argument("--metric", default="sharpe_ratio", help="最適化指標")
    wf_parser.add_argument("--window-size", type=int, default=252, help="ウィンドウサイズ（日数）")
    wf_parser.add_argument("--step-size", type=int, default=63, help="ステップサイズ（日数）")
    wf_parser.add_argument("--optimization-period", type=int, default=189, help="最適化期間（日数）")
    
    args = parser.parse_args()
    
    if args.command == "single":
        asyncio.run(run_single_backtest(args))
    elif args.command == "optimize":
        asyncio.run(run_optimization(args))
    elif args.command == "walk-forward":
        asyncio.run(run_walk_forward(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()