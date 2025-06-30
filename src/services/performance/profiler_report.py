"""プロファイラーレポート生成"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle

from src.domain.models.performance import (
    PerformanceAnalysisResult, LoadTestResult,
    ModuleMetrics, Bottleneck
)


class ProfilerReportGenerator:
    """プロファイラーレポート生成"""
    
    def __init__(self, output_dir: str = "reports/performance"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_performance_report(
        self,
        analysis_result: PerformanceAnalysisResult,
        report_name: str = None,
        include_charts: bool = True
    ) -> Dict[str, str]:
        """パフォーマンス分析レポートを生成"""
        if report_name is None:
            report_name = f"performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        report_dir = self.output_dir / report_name
        report_dir.mkdir(exist_ok=True)
        
        generated_files = {}
        
        # 1. JSON形式の詳細レポート
        json_path = report_dir / "performance_analysis.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(analysis_result.to_dict(), f, indent=2, ensure_ascii=False)
        generated_files["json_report"] = str(json_path)
        
        # 2. チャート生成
        if include_charts:
            # モジュール実行時間
            module_chart_path = report_dir / "module_breakdown.png"
            self._plot_module_breakdown(analysis_result, module_chart_path)
            generated_files["module_chart"] = str(module_chart_path)
            
            # ボトルネック分析
            bottleneck_chart_path = report_dir / "bottlenecks.png"
            self._plot_bottlenecks(analysis_result, bottleneck_chart_path)
            generated_files["bottleneck_chart"] = str(bottleneck_chart_path)
            
            # リソース使用状況
            resource_chart_path = report_dir / "resource_usage.png"
            self._plot_resource_usage(analysis_result, resource_chart_path)
            generated_files["resource_chart"] = str(resource_chart_path)
        
        # 3. HTMLレポート
        html_path = report_dir / "report.html"
        self._generate_html_report(analysis_result, html_path, generated_files)
        generated_files["html_report"] = str(html_path)
        
        # 4. 最適化推奨事項（Markdown）
        recommendations_path = report_dir / "optimization_recommendations.md"
        self._generate_recommendations_report(analysis_result, recommendations_path)
        generated_files["recommendations"] = str(recommendations_path)
        
        return generated_files
    
    def generate_load_test_report(
        self,
        load_test_result: LoadTestResult,
        analysis: Dict[str, Any],
        report_name: str = None
    ) -> Dict[str, str]:
        """負荷テストレポートを生成"""
        if report_name is None:
            report_name = f"load_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        report_dir = self.output_dir / report_name
        report_dir.mkdir(exist_ok=True)
        
        generated_files = {}
        
        # 1. 結果サマリー
        summary_path = report_dir / "load_test_summary.json"
        summary_data = {
            "test_name": load_test_result.test_name,
            "duration_seconds": load_test_result.duration_seconds,
            "concurrent_users": load_test_result.concurrent_users,
            "results": {
                "total_requests": load_test_result.total_requests,
                "successful_requests": load_test_result.successful_requests,
                "failed_requests": load_test_result.failed_requests,
                "avg_response_time": load_test_result.avg_response_time,
                "max_response_time": load_test_result.max_response_time,
                "requests_per_second": load_test_result.requests_per_second
            },
            "analysis": analysis
        }
        
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)
        generated_files["summary"] = str(summary_path)
        
        # 2. リソース使用率チャート
        if load_test_result.resource_usage_timeline:
            resource_timeline_path = report_dir / "resource_timeline.png"
            self._plot_resource_timeline(load_test_result, resource_timeline_path)
            generated_files["resource_timeline"] = str(resource_timeline_path)
        
        # 3. レスポンスタイム分布（仮想データ）
        response_dist_path = report_dir / "response_distribution.png"
        self._plot_response_distribution(load_test_result, response_dist_path)
        generated_files["response_distribution"] = str(response_dist_path)
        
        return generated_files
    
    def _plot_module_breakdown(self, result: PerformanceAnalysisResult, path: Path):
        """モジュール別実行時間をプロット"""
        modules = result.module_breakdown[:10]  # 上位10件
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # 棒グラフ
        module_names = [m.name for m in modules]
        times = [m.total_time for m in modules]
        percentages = [m.percentage for m in modules]
        
        bars = ax1.barh(module_names, times, color='skyblue')
        ax1.set_xlabel('実行時間 (ms)')
        ax1.set_title('モジュール別実行時間')
        
        # 値表示
        for bar, time in zip(bars, times):
            ax1.text(bar.get_width(), bar.get_y() + bar.get_height()/2,
                    f'{time:.1f}ms', ha='left', va='center')
        
        # 円グラフ
        ax2.pie(percentages, labels=module_names, autopct='%1.1f%%', startangle=90)
        ax2.set_title('実行時間の割合')
        
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_bottlenecks(self, result: PerformanceAnalysisResult, path: Path):
        """ボトルネック分析をプロット"""
        if not result.bottlenecks:
            return
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        bottlenecks = result.bottlenecks[:5]  # 上位5件
        
        # データ準備
        labels = [b.description[:40] + '...' if len(b.description) > 40 else b.description
                 for b in bottlenecks]
        times = [b.time_cost for b in bottlenecks]
        colors = ['red' if b.impact.value == 'high' else 'orange' for b in bottlenecks]
        
        # 横棒グラフ
        bars = ax.barh(labels, times, color=colors)
        
        # インパクトレベル表示
        for bar, bottleneck in zip(bars, bottlenecks):
            ax.text(bar.get_width() + 10, bar.get_y() + bar.get_height()/2,
                   bottleneck.impact.value.upper(), ha='left', va='center',
                   fontweight='bold')
        
        ax.set_xlabel('時間コスト (ms)')
        ax.set_title('検出されたボトルネック')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_resource_usage(self, result: PerformanceAnalysisResult, path: Path):
        """リソース使用状況をプロット"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 10))
        
        resource = result.resource_usage
        
        # CPU使用率
        ax1.bar(['CPU使用率'], [resource.cpu_percent], color='green')
        ax1.set_ylim(0, 100)
        ax1.set_ylabel('使用率 (%)')
        ax1.set_title('CPU使用率')
        ax1.text(0, resource.cpu_percent + 2, f'{resource.cpu_percent:.1f}%', ha='center')
        
        # メモリ使用量
        ax2.bar(['メモリ'], [resource.memory_mb], color='blue')
        ax2.set_ylabel('使用量 (MB)')
        ax2.set_title('メモリ使用量')
        ax2.text(0, resource.memory_mb + 10, f'{resource.memory_mb:.1f}MB', ha='center')
        
        # スレッド数
        ax3.bar(['スレッド数'], [resource.thread_count], color='purple')
        ax3.set_ylabel('数')
        ax3.set_title('スレッド数')
        ax3.text(0, resource.thread_count + 0.5, str(resource.thread_count), ha='center')
        
        # I/O統計
        io_data = {
            '読み込み': resource.io_read_mb,
            '書き込み': resource.io_write_mb,
            'ネット送信': resource.network_sent_mb,
            'ネット受信': resource.network_recv_mb
        }
        
        ax4.bar(io_data.keys(), io_data.values(), color='orange')
        ax4.set_ylabel('データ量 (MB)')
        ax4.set_title('I/O統計')
        ax4.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_resource_timeline(self, result: LoadTestResult, path: Path):
        """リソース使用率のタイムライン"""
        if not result.resource_usage_timeline:
            return
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        
        # データ準備
        timestamps = [r.timestamp for r in result.resource_usage_timeline]
        cpu_values = [r.cpu_percent for r in result.resource_usage_timeline]
        memory_values = [r.memory_mb for r in result.resource_usage_timeline]
        
        # CPU使用率
        ax1.plot(timestamps, cpu_values, 'b-', linewidth=2)
        ax1.fill_between(timestamps, cpu_values, alpha=0.3)
        ax1.set_ylabel('CPU使用率 (%)')
        ax1.set_title('負荷テスト中のリソース使用率')
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim(0, max(100, max(cpu_values) * 1.1))
        
        # メモリ使用量
        ax2.plot(timestamps, memory_values, 'r-', linewidth=2)
        ax2.fill_between(timestamps, memory_values, alpha=0.3)
        ax2.set_ylabel('メモリ使用量 (MB)')
        ax2.set_xlabel('時刻')
        ax2.grid(True, alpha=0.3)
        
        # 日付フォーマット
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_response_distribution(self, result: LoadTestResult, path: Path):
        """レスポンスタイム分布（仮想）"""
        import numpy as np
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # 仮想的な分布データ生成
        np.random.seed(42)
        response_times = np.random.gamma(
            result.avg_response_time / 50,
            50,
            result.successful_requests
        )
        
        # ヒストグラム
        ax.hist(response_times, bins=50, color='green', alpha=0.7, edgecolor='black')
        
        # 統計線
        ax.axvline(result.avg_response_time, color='red', linestyle='--',
                  linewidth=2, label=f'平均: {result.avg_response_time:.1f}ms')
        ax.axvline(result.max_response_time, color='orange', linestyle='--',
                  linewidth=2, label=f'最大: {result.max_response_time:.1f}ms')
        
        ax.set_xlabel('レスポンスタイム (ms)')
        ax.set_ylabel('リクエスト数')
        ax.set_title('レスポンスタイム分布')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def _generate_html_report(
        self,
        result: PerformanceAnalysisResult,
        path: Path,
        files: Dict[str, str]
    ):
        """HTMLレポートを生成"""
        status_color = {
            "PASS": "green",
            "WARNING": "orange",
            "FAIL": "red"
        }[result.summary.performance_status.value]
        
        html_content = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>パフォーマンス分析レポート</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .summary {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .status {{ color: {status_color}; font-weight: bold; font-size: 24px; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-label {{ font-size: 12px; color: #666; }}
        .metric-value {{ font-size: 20px; font-weight: bold; }}
        img {{ max-width: 100%; margin: 20px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 10px; text-align: left; border: 1px solid #ddd; }}
        th {{ background: #f0f0f0; }}
        .section {{ margin: 30px 0; }}
    </style>
</head>
<body>
    <h1>パフォーマンス分析レポート</h1>
    
    <div class="summary">
        <div class="status">{result.summary.performance_status.value}</div>
        <div class="metric">
            <div class="metric-label">総実行時間</div>
            <div class="metric-value">{result.summary.total_execution_time:.1f}ms</div>
        </div>
        <div class="metric">
            <div class="metric-label">目標時間</div>
            <div class="metric-value">{result.summary.target_time:.1f}ms</div>
        </div>
        <div class="metric">
            <div class="metric-label">スループット</div>
            <div class="metric-value">{result.summary.throughput:.1f} req/s</div>
        </div>
    </div>
    
    <div class="section">
        <h2>モジュール別実行時間</h2>
        <img src="module_breakdown.png" alt="モジュール別実行時間">
    </div>
    
    <div class="section">
        <h2>検出されたボトルネック</h2>
        <img src="bottlenecks.png" alt="ボトルネック">
        
        <table>
            <tr>
                <th>タイプ</th>
                <th>説明</th>
                <th>影響度</th>
                <th>推奨対策</th>
            </tr>
"""
        
        for bottleneck in result.bottlenecks[:5]:
            html_content += f"""
            <tr>
                <td>{bottleneck.type.value}</td>
                <td>{bottleneck.description}</td>
                <td>{bottleneck.impact.value}</td>
                <td>{bottleneck.suggestion}</td>
            </tr>
"""
        
        html_content += """
        </table>
    </div>
    
    <div class="section">
        <h2>リソース使用状況</h2>
        <img src="resource_usage.png" alt="リソース使用状況">
    </div>
    
    <div class="section">
        <h2>詳細データ</h2>
        <ul>
            <li><a href="performance_analysis.json">詳細分析結果 (JSON)</a></li>
            <li><a href="optimization_recommendations.md">最適化推奨事項</a></li>
        </ul>
    </div>
</body>
</html>
"""
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)
    
    def _generate_recommendations_report(
        self,
        result: PerformanceAnalysisResult,
        path: Path
    ):
        """最適化推奨事項レポートを生成"""
        content = """# パフォーマンス最適化推奨事項

## 概要
このドキュメントは、パフォーマンス分析結果に基づく最適化推奨事項をまとめています。

## 推奨事項一覧
"""
        
        for i, rec in enumerate(result.optimization_recommendations, 1):
            content += f"""
### {i}. {rec.action} (優先度: {rec.priority})

**期待される改善効果**: {rec.expected_improvement}  
**実装工数**: {rec.effort} ({rec.estimated_hours}時間)  

**実装方法**:
{rec.implementation}

**リスク**:
"""
            for risk in rec.risks:
                content += f"- {risk}\n"
            
            content += "\n**依存関係**:\n"
            for dep in rec.dependencies:
                content += f"- {dep}\n"
            
            content += "\n---\n"
        
        content += """
## 実装順序の推奨

1. 低工数・高効果の項目から着手
2. 依存関係を考慮した実装順序の決定
3. 段階的な実装とベンチマークによる効果測定

## 注意事項

- 最適化前に必ずベースラインを測定
- 各最適化後に回帰テストを実施
- 可読性とのバランスを考慮
"""
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)