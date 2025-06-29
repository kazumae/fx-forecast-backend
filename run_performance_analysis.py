"""パフォーマンス分析実行スクリプト"""
import asyncio
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from src.services.performance import (
    PerformanceAnalyzer,
    LoadTester,
    ProfilerReportGenerator
)

# 実際のモジュールをインポート（簡易版のため一部のみ）
from src.services.pattern_detection import PatternDetectionService
from src.services.entry_point.evaluation import EntryEvaluationService
from src.services.entry_point.signal_generation import SignalGenerationService
from src.domain.models.market_data import Candlestick
from tests.utils import CandlestickFactory, ZoneFactory


async def analyze_entry_point_performance():
    """エントリーポイント判定のパフォーマンス分析"""
    analyzer = PerformanceAnalyzer(target_time_ms=1000.0)
    
    # テストデータ準備
    candles = CandlestickFactory.create_trend_candles(num_candles=100)
    zones = ZoneFactory.create_major_zones()
    
    # 分析開始
    print("エントリーポイント判定のパフォーマンス分析を開始...")
    
    # 1. パターン検出
    with analyzer.measure("pattern_detection") as ctx:
        pattern_service = PatternDetectionService()
        patterns = await pattern_service.detect_all_patterns(candles)
    
    # 2. エントリー評価
    with analyzer.measure("entry_evaluation") as ctx:
        eval_service = EntryEvaluationService()
        evaluations = await eval_service.evaluate_entries(patterns, zones, {})
    
    # 3. シグナル生成
    with analyzer.measure("signal_generation") as ctx:
        signal_service = SignalGenerationService()
        signals = await signal_service.generate_signals(evaluations, zones, {})
    
    # 4. データベースアクセス（シミュレーション）
    with analyzer.measure("database_access") as ctx:
        # 実際のDBアクセスの代わりにスリープ
        await asyncio.sleep(0.1)
        analyzer.record_db_query(
            "SELECT * FROM candlesticks WHERE symbol = 'XAUUSD' ORDER BY timestamp DESC LIMIT 100",
            100.0
        )
    
    # リソースキャプチャ
    analyzer.capture_resource_snapshot()
    
    # 分析実行
    result = analyzer.analyze()
    
    return result


async def run_load_test():
    """負荷テストの実行"""
    load_tester = LoadTester()
    
    # テスト関数
    async def test_function():
        # 簡易的なエントリーポイント判定シミュレーション
        await asyncio.sleep(0.05)  # 50msの処理
        
        # ランダムにエラーを発生（5%の確率）
        import random
        if random.random() < 0.05:
            raise Exception("シミュレートされたエラー")
    
    # 負荷テスト実行
    result = await load_tester.run_load_test(
        test_name="エントリーポイント判定負荷テスト",
        test_function=test_function,
        concurrent_users=10,
        duration_seconds=30.0,
        ramp_up_seconds=5.0
    )
    
    # 結果分析
    analysis = load_tester.analyze_results(result)
    
    return result, analysis


async def run_stress_tests():
    """ストレステストの実行"""
    load_tester = LoadTester()
    
    print("\n=== ストレステスト開始 ===")
    
    # メモリストレステスト
    print("\n1. メモリストレステスト")
    load_tester.stress_test_memory(size_mb=200, duration_seconds=5)
    
    # CPUストレステスト
    print("\n2. CPUストレステスト")
    await load_tester.stress_test_cpu(duration_seconds=5, threads=4)
    
    print("\nストレステスト完了")


async def main():
    parser = argparse.ArgumentParser(description="パフォーマンス分析ツール")
    parser.add_argument(
        "command",
        choices=["analyze", "load-test", "stress-test", "report"],
        help="実行するコマンド"
    )
    parser.add_argument("--output-dir", default="reports/performance", help="レポート出力先")
    parser.add_argument("--profile", action="store_true", help="詳細プロファイリングを有効化")
    
    args = parser.parse_args()
    
    if args.command == "analyze":
        # パフォーマンス分析
        result = await analyze_entry_point_performance()
        
        # 結果表示
        print("\n=== パフォーマンス分析結果 ===")
        print(f"ステータス: {result.summary.performance_status.value}")
        print(f"総実行時間: {result.summary.total_execution_time:.1f}ms")
        print(f"目標時間: {result.summary.target_time:.1f}ms")
        
        print("\n--- モジュール別実行時間 ---")
        for module in result.module_breakdown[:5]:
            print(f"{module.name}: {module.total_time:.1f}ms ({module.percentage:.1f}%)")
        
        print("\n--- 検出されたボトルネック ---")
        for bottleneck in result.bottlenecks:
            print(f"- {bottleneck.type.value}: {bottleneck.description}")
            print(f"  影響: {bottleneck.impact.value}, 推奨: {bottleneck.suggestion}")
        
        # レポート生成
        generator = ProfilerReportGenerator(output_dir=args.output_dir)
        files = generator.generate_performance_report(result)
        
        print("\n生成されたレポート:")
        for name, path in files.items():
            print(f"  - {name}: {path}")
    
    elif args.command == "load-test":
        # 負荷テスト
        result, analysis = await run_load_test()
        
        # 結果表示
        print("\n=== 負荷テスト結果 ===")
        print(f"テスト名: {result.test_name}")
        print(f"実行時間: {result.duration_seconds:.1f}秒")
        print(f"同時ユーザー数: {result.concurrent_users}")
        print(f"総リクエスト数: {result.total_requests}")
        print(f"成功率: {analysis['summary']['success_rate']:.1f}%")
        print(f"平均レスポンスタイム: {result.avg_response_time:.1f}ms")
        print(f"スループット: {result.requests_per_second:.1f} req/s")
        print(f"評価: {analysis['assessment']}")
        
        # エラー内訳
        if result.error_breakdown:
            print("\n--- エラー内訳 ---")
            for error_type, count in result.error_breakdown.items():
                print(f"  {error_type}: {count}件")
        
        # レポート生成
        generator = ProfilerReportGenerator(output_dir=args.output_dir)
        files = generator.generate_load_test_report(result, analysis)
        
        print("\n生成されたレポート:")
        for name, path in files.items():
            print(f"  - {name}: {path}")
    
    elif args.command == "stress-test":
        # ストレステスト
        await run_stress_tests()
    
    elif args.command == "report":
        # 既存の分析結果からレポート生成
        print("既存の分析結果からレポートを生成する機能は未実装です")


if __name__ == "__main__":
    asyncio.run(main())