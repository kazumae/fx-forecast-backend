# 学習データシステム ドキュメント

## 概要

このシステムは、FX予測の分析結果、レビュー、コメントから学習データを抽出・蓄積し、新規の解析精度を向上させるための機能を提供します。

## 主な機能

### 1. メタデータ抽出 (`LearningDataService`)

- **予測分析からのパターン抽出**
  - 使用されたかむかむ流ポイント（1-9）
  - トレンド方向
  - エントリータイプ（ブレイクアウト/プルバック/リバーサル）
  - 重要価格レベル
  - ボラティリティ状況

- **レビューからの学習データ抽出**
  - 成功要因
  - 失敗要因
  - 学んだ教訓
  - パターンの有効性評価

- **コメントQ&Aからの洞察抽出**
  - 重要なポイント
  - 明確化された事項
  - 追加の洞察

### 2. データ蓄積

学習データは以下の2つの形式で保存されます：

- **テキストファイル** (`data/learning/learning_data_YYYYMMDD_HHMMSS.txt`)
  - 人間が読みやすい形式
  - パターン成功率、成功要因、失敗要因などを整理

- **JSONファイル** (`data/learning/learning_data_YYYYMMDD_HHMMSS.json`)
  - プログラムで処理しやすい形式
  - 詳細な構造化データ

### 3. 新規解析での活用

`/analyze/v2` エンドポイントで新規解析を行う際、以下のデータが自動的に参照されます：

- 過去30日間のパターン成功率
- 成功要因トップ5
- 失敗要因トップ5
- 類似パターンの過去の結果

## 使用方法

### バッチ処理の実行

定期的に学習データをコンパイルするには、以下のコマンドを実行します：

```bash
# Docker環境での実行
docker-compose exec api python scripts/compile_learning_data.py

# 過去7日間のデータをコンパイル
docker-compose exec api python scripts/compile_learning_data.py --days 7

# 日次レポートの生成
docker-compose exec api python scripts/compile_learning_data.py --daily-report
```

### Cronでの自動実行

毎日深夜に自動的に学習データをコンパイルする場合：

```bash
# crontab -e で以下を追加
0 0 * * * cd /path/to/backend && docker-compose exec -T api python scripts/compile_learning_data.py
```

## データ構造

### 学習データの主要フィールド

```json
{
  "compilation_date": "2024-01-01T00:00:00",
  "period": "last_30_days",
  "pattern_success_rates": {
    "ポイント1": {
      "total": 10,
      "success": 7,
      "failure": 3,
      "success_rate": 0.7
    }
  },
  "successful_patterns": [...],
  "failed_patterns": [...],
  "common_mistakes": [...],
  "best_practices": [...],
  "comment_insights": [...],
  "trade_execution_insights": [...]
}
```

## 実装の詳細

### 1. メタデータ抽出の流れ

1. 新規予測が作成される
2. `LearningDataService.extract_pattern_metadata()` が自動的に呼び出される
3. AIがテキストからパターン情報を抽出
4. `extra_metadata` フィールドに保存

### 2. バッチ処理の流れ

1. 指定期間の予測、レビュー、コメントを取得
2. 各データからメタデータを抽出
3. パターン成功率を集計
4. テキストとJSONファイルに保存

### 3. 新規解析での活用

1. `EnhancedPatternService` が過去のパターンデータを取得
2. `LearningDataService` が蓄積された成功/失敗要因を提供
3. これらの情報がAIのプロンプトに含まれる
4. AIがより精度の高い分析を実施

## 効果

- **パターン認識の改善**: 過去の成功率データに基づいた判断
- **失敗の回避**: 過去の失敗要因を考慮
- **成功要因の活用**: 実績のある成功パターンを優先
- **継続的な改善**: データが蓄積されるほど精度が向上

## 注意事項

- データベースへの接続が必要です（SQLiteまたは設定されたDB）
- 学習データディレクトリ (`data/learning/`) への書き込み権限が必要です
- APIキー（ANTHROPIC_API_KEY）が設定されている必要があります