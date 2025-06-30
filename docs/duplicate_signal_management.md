# Duplicate Signal Management - 重複シグナル管理

## 概要
Duplicate Signal Managementは、短期間に同一または類似のシグナルが複数回検出された場合に重複として扱い、通知を抑制するシステムです。Redisを活用した高速な重複検出により、トレーダーは真に新しいシグナルのみに集中できます。

## 機能

### 主要機能
- **フィンガープリント生成**: MD5ハッシュによる一意識別
- **価格許容誤差**: ±0.1%の価格差は同一として扱う
- **TTL管理**: 5分間の重複防止期間
- **統計収集**: 時間軸別・日次の重複率追跡
- **Redis統合**: 高速なキャッシュベース検出

### 重複判定基準
同じとみなされる条件：
1. 同一シンボル（例: XAUUSD）
2. 同一時間枠（例: 15m）
3. 同一シグナルタイプ（BUY/SELL）
4. 価格差が0.1%以内
5. 同一パターンタイプ

## 使用方法

### 基本的な使用
```python
from src.batch.duplicate_management import DuplicateSignalManager
import redis

# 初期化
redis_client = redis.from_url("redis://localhost:6379")
manager = DuplicateSignalManager(redis_client)

# 重複チェック
if not manager.is_duplicate(validated_signal):
    # 新規シグナルとして処理
    send_notification(validated_signal)
else:
    # 重複なのでスキップ
    logger.info("Duplicate signal detected, skipping")
```

### SignalMonitorJobでの使用
```python
# SignalMonitorJobは自動的にDuplicateSignalManagerを使用
monitor = SignalMonitorJob()
monitor.execute()  # 重複シグナルは自動的にフィルタリング
```

## 統計機能

### 時間軸別統計
```python
# 特定時間軸の統計
stats = await manager.get_duplicate_stats("15m")
print(f"15分足 - 総シグナル: {stats['total_signals']}")
print(f"15分足 - 重複数: {stats['duplicate_signals']}")
print(f"15分足 - 重複率: {stats['duplicate_rate']:.1f}%")

# 全時間軸の統計
all_stats = await manager.get_duplicate_stats()
print(f"全体 - 重複率: {all_stats['duplicate_rate']:.1f}%")
```

### 日次統計
```python
# 今日の統計
today_stats = await manager.get_daily_stats()
print(f"本日の重複率: {today_stats['duplicate_rate']:.1f}%")

# 特定日の統計
stats = await manager.get_daily_stats("20240101")
```

### 最近のシグナル履歴
```python
# 最近10件のシグナルを取得
recent = manager.get_recent_signals(limit=10)
for signal in recent:
    print(f"シグナル: {signal['signal']['type']}")
    print(f"TTL残り: {signal['ttl_remaining']}秒")
```

## 設定とカスタマイズ

### 設定可能なパラメータ
```python
manager = DuplicateSignalManager(redis_client)

# TTL期間の変更（デフォルト: 300秒）
manager.ttl_seconds = 600  # 10分に延長

# 価格許容誤差の変更（デフォルト: 0.1%）
manager.price_tolerance = Decimal("0.002")  # 0.2%に変更
```

## フィンガープリント生成

### アルゴリズム
1. シグナル要素の抽出
   - シンボル（XAUUSD）
   - 時間枠（15m）
   - シグナルタイプ（BUY/SELL）
   - 丸められた価格（1852.0）
   - パターンタイプ（bullish_reversal）

2. 要素の結合
   ```
   "XAUUSD:15m:BUY:1852.0:bullish_reversal"
   ```

3. MD5ハッシュ生成
   ```
   signal:fp:a1b2c3d4e5f6...
   ```

### 価格丸め例
- 1850.0 → 1850.0（変更なし）
- 1850.5 → 1851.0（0.027%差）
- 1851.8 → 1852.0（0.097%差）
- 1852.0 → 1852.0（変更なし）

## Redisキー構造

### シグナルフィンガープリント
```
signal:fp:{md5_hash}
TTL: 300秒
値: シグナルのJSON
```

### 統計カウンター
```
signal_count:{timeframe}      # シグナル総数
duplicate_count:{timeframe}   # 重複数
signal_count:daily:{YYYYMMDD} # 日次シグナル数
duplicate_count:daily:{YYYYMMDD} # 日次重複数
```

## パフォーマンス

### 処理時間
- フィンガープリント生成: < 1ms
- 重複チェック: < 5ms
- 統計取得: < 10ms

### メモリ使用量
- 約1KB/シグナル
- TTL自動削除により古いデータは削除

### スケーラビリティ
- O(1)の検索性能
- 並行処理対応（スレッドセーフ）
- Redis Clusterでの水平スケーリング可能

## トラブルシューティング

### Redis接続エラー
```
WARNING: Redis connection failed
```
→ Redis未接続時は自動的に無効化され、すべてのシグナルが新規として扱われます

### 高い重複率
重複率が異常に高い場合：
1. TTL期間を確認（短すぎないか）
2. 価格許容誤差を確認（大きすぎないか）
3. シグナル生成ロジックを確認

### 統計のリセット
```python
# すべての統計をクリア
manager.clear_stats()
```

## 開発者向け情報

### テスト実行
```bash
# 単体テスト
pytest tests/unit/batch/test_duplicate_signal_manager.py

# 統合テスト（Redis必須）
pytest tests/integration/batch/test_duplicate_signal_manager_integration.py
```

### モック使用例
```python
from unittest.mock import MagicMock

# Redisモック
redis_mock = MagicMock()
redis_mock.exists.return_value = False
manager = DuplicateSignalManager(redis_mock)
```

### ログ設定
```python
import logging
logging.getLogger('src.batch.duplicate_management').setLevel(logging.DEBUG)
```