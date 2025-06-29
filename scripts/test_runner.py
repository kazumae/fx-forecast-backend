#!/usr/bin/env python3
"""テスト実行スクリプト"""
import subprocess
import sys
import argparse
from pathlib import Path


def run_tests(test_type="all", coverage=True, verbose=True):
    """テストを実行"""
    
    # ベースコマンド
    cmd = ["pytest"]
    
    # テストタイプに応じたマーカー
    if test_type == "unit":
        cmd.extend(["-m", "unit"])
    elif test_type == "integration":
        cmd.extend(["-m", "integration"])
    elif test_type == "e2e":
        cmd.extend(["-m", "e2e"])
    elif test_type == "pattern":
        cmd.extend(["-m", "pattern"])
    elif test_type == "evaluation":
        cmd.extend(["-m", "evaluation"])
    elif test_type == "signal":
        cmd.extend(["-m", "signal"])
    elif test_type == "validation":
        cmd.extend(["-m", "validation"])
    
    # カバレッジオプション
    if coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-report=xml"
        ])
    
    # 詳細出力
    if verbose:
        cmd.append("-v")
    
    # 実行
    print(f"実行コマンド: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
    
    return result.returncode


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="テスト実行スクリプト")
    parser.add_argument(
        "--type",
        choices=["all", "unit", "integration", "e2e", "pattern", "evaluation", "signal", "validation"],
        default="all",
        help="実行するテストタイプ"
    )
    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="カバレッジ計測を無効化"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="詳細出力を無効化"
    )
    
    args = parser.parse_args()
    
    # テスト実行
    exit_code = run_tests(
        test_type=args.type,
        coverage=not args.no_coverage,
        verbose=not args.quiet
    )
    
    # カバレッジレポートの場所を表示
    if not args.no_coverage and exit_code == 0:
        print("\n✅ テストが成功しました！")
        print("📊 カバレッジレポート: htmlcov/index.html")
    elif exit_code != 0:
        print("\n❌ テストが失敗しました")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()