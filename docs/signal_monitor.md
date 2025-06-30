# Signal Monitor - エントリーポイント監視システム

## 概要
Signal Monitorは、1分毎にFXのエントリーポイントを自動的に監視し、トレーディングシグナルを検出するバッチジョブです。検出されたシグナルはSlackに通知されます。

## 機能

### 主要機能
- **定期実行**: 毎分00秒に正確に実行
- **マルチタイムフレーム**: 1分、15分、1時間の複数時間枠を同時監視
- **重複防止**: Redisを使用した重複シグナルの検出と防止
- **エラーハンドリング**: 自動リトライとエラー通知
- **Slack通知**: シグナル検出時の即時通知

### 監視対象
- 通貨ペア: XAUUSD（金/USD）
- 時間枠: 1m, 15m, 1h

## 使用方法

### 1. 単発実行
```bash
# バッチジョブとして実行
docker-compose exec app python run_batch.py signal_monitor
```

### 2. 継続実行（デーモンモード）
```bash
# デーモンとして起動
docker-compose exec app python run_signal_monitor.py

# バックグラウンドで実行
docker-compose exec -d app python run_signal_monitor.py

# ログを確認
docker-compose logs -f app | grep signal_monitor
```

### 3. 停止方法
```bash
# プロセスIDを確認
docker-compose exec app ps aux | grep signal_monitor

# プロセスを停止
docker-compose exec app kill -TERM <PID>
```

## 設定

### 環境変数
```bash
# Redis接続（オプション）
REDIS_URL=redis://redis:6379

# Slack通知（必須）
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

### カスタマイズ
`src/batch/jobs/signal_monitor.py`で以下の設定が可能：

```python
# 監視対象シンボル
self.target_symbols = ["XAUUSD", "EURUSD"]  

# 監視時間枠
self.timeframes = ["1m", "15m", "1h", "4h"]

# 実行間隔（秒）
self.check_interval = 60  

# 最大リトライ回数
self.max_retries = 3
```

## アーキテクチャ

### コンポーネント構成
```
SignalMonitorJob
├── EntrySignalGenerator    # シグナル生成
├── SignalValidationService # シグナル検証
├── Redis Client           # 重複検出
└── SlackNotifier         # 通知送信
```

### 処理フロー
1. 毎分00秒に起動
2. 各シンボル・時間枠の最新データを取得
3. エントリーポイントシグナルを生成
4. シグナルの有効性を検証
5. 重複チェック（Redis）
6. 新規シグナルをSlackに通知

## 通知形式

### Slack通知例
```
🎯 エントリーポイント検出
2件のシグナルを検出しました

XAUUSD - 1m: Signal: BUY
XAUUSD - 15m: Signal: SELL
```

## エラーハンドリング

### リトライ機構
- 最大3回まで自動リトライ
- エラー発生時は10秒待機後にリトライ
- 3回失敗で実行停止

### エラー通知
- データベース接続エラー
- シグナル生成エラー
- その他の予期しないエラー

## パフォーマンス

### 実行時間
- 平均実行時間: < 1秒
- 最大実行時間: < 5秒

### リソース使用
- メモリ: < 100MB
- CPU: < 5%

## トラブルシューティング

### よくある問題

1. **Redisに接続できない**
   ```
   WARNING: Redis connection failed
   ```
   → Redisコンテナが起動していることを確認

2. **シグナルが検出されない**
   - データベースにデータが存在することを確認
   - EntrySignalGeneratorの設定を確認

3. **Slack通知が送信されない**
   - SLACK_WEBHOOK_URLが正しく設定されていることを確認
   - ネットワーク接続を確認

## 開発者向け情報

### テスト実行
```bash
# 単体テスト
pytest tests/unit/batch/test_signal_monitor.py

# 統合テスト
pytest tests/integration/batch/test_signal_monitor_integration.py
```

### ログレベル変更
```python
logging.basicConfig(level=logging.DEBUG)
```

### デバッグモード
```python
monitor = SignalMonitorJob()
monitor.logger.setLevel(logging.DEBUG)
```