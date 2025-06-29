# Tests Directory Structure

このディレクトリには、FX Forecast バックエンドシステムのテストが整理されています。

## ディレクトリ構造

```
tests/
├── unit/                # 単体テスト（外部依存なし）
│   ├── core/           # コア機能のテスト
│   └── stream/         # ストリーミング機能のテスト
├── integration/        # 統合テスト（Docker環境必須）
├── e2e/               # エンドツーエンドテスト
└── manual/            # 手動実行用の特殊テスト
```

## テストの実行方法

### 全テストの実行
```bash
bash scripts/test.sh
```

### 単体テストのみ
```bash
bash scripts/test_unit.sh
# または
python tests/unit/core/test_tradermade_config.py
python tests/unit/stream/test_error_handler.py
```

### 統合テスト
```bash
# Docker環境で実行
docker-compose exec app python tests/integration/test_slack_integration.py
docker-compose exec tradermade-stream python tests/integration/test_slack_notifications.py
```

### E2Eテスト
```bash
# 全サービスが起動している状態で実行
docker-compose up -d
bash tests/e2e/test_api_endpoints.sh
```

### 手動テスト
```bash
# 特定の状況を再現するテスト
python tests/manual/docker_network_test.py
```

## テストの種類

### Unit Tests (単体テスト)
- **目的**: 個々のクラスや関数の動作を検証
- **特徴**: 高速、外部依存なし、モック使用
- **例**: 設定クラスのバリデーション、エラー分類ロジック

### Integration Tests (統合テスト)
- **目的**: 複数のコンポーネントの連携を検証
- **特徴**: Docker環境必須、実際の外部サービスとの接続
- **例**: Slack通知の送信、WebSocket接続

### E2E Tests (エンドツーエンドテスト)
- **目的**: システム全体の動作を検証
- **特徴**: 全サービス起動必須、ユーザーシナリオベース
- **例**: APIエンドポイントの動作確認

### Manual Tests (手動テスト)
- **目的**: 特定の状況や障害を再現
- **特徴**: デバッグや負荷テスト用
- **例**: ネットワーク切断シミュレーション

## pytest の使用

今後、pytestフレームワークへの移行を推奨します：

```bash
# pytest のインストール
pip install -r requirements-dev.txt

# pytest での実行
pytest tests/unit/  # 単体テストのみ
pytest tests/       # 全テスト
pytest -v          # 詳細出力
pytest -k "config" # "config"を含むテストのみ
```

## CI/CD 統合

GitHub Actions などの CI/CD パイプラインでは：

```yaml
# 単体テストは常に実行
- run: bash scripts/test_unit.sh

# 統合テストは Docker 環境で実行
- run: docker-compose up -d
- run: bash scripts/test_integration.sh
```