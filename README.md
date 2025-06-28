# FX Forecast Backend API

FastAPIを使用した為替予測バックエンドAPIです。

## 技術スタック

- **Python 3.11**
- **FastAPI** - Webフレームワーク
- **SQLAlchemy** - ORM
- **PostgreSQL** - データベース
- **Docker** - コンテナ化

## プロジェクト構造

```
backend/
├── docker/
│   ├── app/
│   │   └── Dockerfile          # Python/FastAPIコンテナ
│   └── postgres/
│       └── Dockerfile          # PostgreSQLコンテナ
├── alembic/
│   ├── versions/               # マイグレーションファイル
│   ├── env.py                  # Alembic環境設定
│   └── script.py.mako          # マイグレーションテンプレート
├── src/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── api.py          # APIルーター集約
│   │   │   └── endpoints/      # エンドポイント定義
│   │   │       ├── users.py    # ユーザー関連API
│   │   │       └── forex.py    # 為替関連API
│   │   └── deps.py             # 依存関係
│   ├── core/
│   │   └── config.py           # アプリケーション設定
│   ├── db/
│   │   ├── session.py          # データベースセッション
│   │   └── init_db.py          # DB初期化スクリプト
│   ├── models/                 # SQLAlchemyモデル
│   │   ├── base.py
│   │   ├── user.py             # ユーザーモデル
│   │   └── forex.py            # 為替モデル
│   ├── schemas/                # Pydanticスキーマ
│   │   ├── user.py             # ユーザースキーマ
│   │   └── forex.py            # 為替スキーマ
│   ├── services/               # ビジネスロジック
│   │   ├── user.py             # ユーザーサービス
│   │   └── forex.py            # 為替サービス
│   ├── batch/                  # バッチ処理
│   │   ├── base.py             # バッチジョブ基底クラス
│   │   ├── jobs/               # バッチジョブ実装
│   │   │   ├── fetch_forex_rates.py
│   │   │   ├── cleanup_old_data.py
│   │   │   └── generate_daily_report.py
│   │   └── utils/              # バッチ用ユーティリティ
│   └── main.py                 # アプリケーションエントリーポイント
├── docker-compose.yml
├── alembic.ini                 # Alembic設定ファイル
├── requirements.txt
├── run_batch.py                # バッチ実行スクリプト
├── .dockerignore
└── .env.example
```

## セットアップ

### 1. 環境変数の設定

`.env.example`をコピーして`.env`を作成し、必要な環境変数を設定します。

```bash
cp .env.example .env
```

**重要**: `.env`ファイルはGitにコミットされないよう`.gitignore`に含まれています。本番環境では適切な値に変更してください。

主な環境変数：
- `DATABASE_URL` - PostgreSQLの接続URL
- `SECRET_KEY` - セキュリティ用のシークレットキー
- `FOREX_API_KEY` - 外部為替APIのキー（使用する場合）

### 2. Dockerコンテナの起動

```bash
# コンテナのビルドと起動
docker-compose up --build

# バックグラウンドで起動
docker-compose up -d

# ログの確認
docker-compose logs -f
```

### 3. データベースのマイグレーション

初回起動時は自動的にマイグレーションが実行されます。

手動でマイグレーションを実行する場合：
```bash
# 新しいマイグレーションファイルを作成
docker-compose exec app alembic revision --autogenerate -m "説明"

# マイグレーションを適用
docker-compose exec app alembic upgrade head

# マイグレーションの履歴を確認
docker-compose exec app alembic history

# 特定のリビジョンにロールバック
docker-compose exec app alembic downgrade -1
```

## データベースアクセス

### PostgreSQL接続情報

ローカル環境からPostgreSQLにアクセスする場合の接続情報：

- **ホスト**: localhost
- **ポート**: 6543
- **データベース名**: fx_forecast
- **ユーザー名**: fx_user
- **パスワード**: fx_password

#### psqlでの接続
```bash
# コンテナ内から接続
docker-compose exec db psql -U fx_user -d fx_forecast

# ローカルから接続（psqlがインストールされている場合）
# パスワードを環境変数で指定
PGPASSWORD=fx_password psql -h localhost -p 6543 -U fx_user -d fx_forecast

# または対話的にパスワードを入力
psql -h localhost -p 6543 -U fx_user -d fx_forecast
# パスワード: fx_password
```

#### GUI クライアントでの接続
TablePlus、DBeaver、pgAdmin等のGUIクライアントを使用する場合：
- **Host**: `localhost` または `127.0.0.1`
- **Port**: `6543`
- **Database**: `fx_forecast`
- **Username**: `fx_user`
- **Password**: `fx_password`

**注意**: パスワード認証に失敗する場合は、上記の情報が正しく入力されているか確認してください。

#### 便利なデータベースコマンド
```bash
# テーブル一覧を表示
docker-compose exec db psql -U fx_user -d fx_forecast -c "\dt"

# テーブル構造を確認
docker-compose exec db psql -U fx_user -d fx_forecast -c "\d users"

# データベースのバックアップ
docker-compose exec db pg_dump -U fx_user fx_forecast > backup.sql

# データベースのリストア
docker-compose exec -T db psql -U fx_user fx_forecast < backup.sql
```

## 開発

### ローカル開発環境

```bash
# 仮想環境の作成
python -m venv venv

# 仮想環境の有効化
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate  # Windows

# 依存関係のインストール
pip install -r requirements.txt

# アプリケーションの起動
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### コンテナの操作

```bash
# コンテナの停止
docker-compose down

# コンテナの再起動
docker-compose restart

# コンテナのログ確認
docker-compose logs -f app

# コンテナに入る
docker-compose exec app bash
```

## API エンドポイント

### 基本情報
- **ベースURL**: `http://localhost:8900`
- **APIドキュメント**: `http://localhost:8900/docs`
- **OpenAPI仕様**: `http://localhost:8900/api/v1/openapi.json`

### 主なエンドポイント

#### ヘルスチェック
```
GET /health
```

#### ユーザー管理
```
GET    /api/v1/users/           # ユーザー一覧取得
GET    /api/v1/users/{user_id}  # ユーザー詳細取得
POST   /api/v1/users/           # ユーザー作成
```

#### 為替レート
```
GET    /api/v1/forex/rates              # 為替レート取得
GET    /api/v1/forex/rates/latest       # 最新レート取得
POST   /api/v1/forex/forecast           # 為替予測作成
```

## テスト

```bash
# テストの実行
docker-compose exec app pytest

# カバレッジ付きテスト
docker-compose exec app pytest --cov=src tests/
```

## バッチ処理

### バッチジョブの実行

バッチジョブは `run_batch.py` スクリプトで実行します。

#### 利用可能なバッチジョブ

1. **fetch_forex_rates** - 為替レートを取得
   ```bash
   # Docker内で実行
   docker-compose exec app python run_batch.py fetch_forex_rates
   
   # 特定の通貨ペアを指定
   docker-compose exec app python run_batch.py fetch_forex_rates --pairs USD/JPY EUR/USD
   ```

2. **cleanup_old_data** - 古いデータを削除
   ```bash
   # デフォルト（30日より古いデータを削除）
   docker-compose exec app python run_batch.py cleanup_old_data
   
   # 90日より古いデータを削除
   docker-compose exec app python run_batch.py cleanup_old_data --days 90
   ```

3. **generate_daily_report** - 日次レポートを生成
   ```bash
   docker-compose exec app python run_batch.py generate_daily_report
   ```

4. **slack_notification** - Slack通知を送信
   ```bash
   # 日次サマリーを送信
   docker-compose exec app python run_batch.py slack_notification --notification-type daily_summary
   
   # レート変動アラートを送信
   docker-compose exec app python run_batch.py slack_notification --notification-type rate_alert
   
   # システムステータスを送信
   docker-compose exec app python run_batch.py slack_notification --notification-type system_status
   ```

### カスタムバッチジョブの作成

1. `src/batch/jobs/` に新しいファイルを作成
2. `BaseBatchJob` を継承
3. `execute()` メソッドを実装
4. `run_batch.py` の `JOB_REGISTRY` に登録

例：
```python
from src.batch.base import BaseBatchJob

class MyCustomBatch(BaseBatchJob):
    def __init__(self):
        super().__init__("MyCustomJob")
    
    def execute(self):
        # バッチ処理のロジック
        # self.db でデータベースアクセス可能
        # self.logger でロギング可能
        result = self.db.query(SomeModel).all()
        self.logger.info(f"Processed {len(result)} records")
        return {"processed": len(result)}
```

### Slack通知機能

バッチジョブの基底クラス `BaseBatchJob` には、Slack通知機能が統合されています。

#### 基本的な使い方

デフォルトでは、バッチジョブは完了時とエラー時にSlack通知を送信します：

```python
class MyBatch(BaseBatchJob):
    def __init__(self):
        super().__init__("MyBatch")  # 通知は自動的に有効
    
    def execute(self):
        # 実行詳細を設定（完了通知に含まれる）
        self.set_execution_detail("処理件数", 100)
        self.set_execution_detail("成功率", "95%")
        
        return {"status": "success"}
```

#### 通知設定のカスタマイズ

```python
class CustomNotificationBatch(BaseBatchJob):
    def __init__(self):
        # 通知を無効化する場合
        super().__init__("CustomBatch", enable_slack_notification=False)
    
    def should_notify_on_start(self) -> bool:
        """開始時も通知を送る"""
        return True
    
    def should_notify_on_complete(self) -> bool:
        """完了時の通知を無効化"""
        return False
    
    def should_notify_on_error(self) -> bool:
        """エラー時のみ通知"""
        return True
```

#### カスタム通知の送信

```python
def execute(self):
    # 処理中にカスタム通知を送信
    self.send_custom_notification(
        title="処理進捗",
        message="50%完了しました",
        color="warning",  # good, warning, danger, または16進数カラー
        fields=[
            {"title": "処理済み", "value": "500件", "short": True},
            {"title": "残り", "value": "500件", "short": True}
        ],
        emoji="📊"
    )
```

#### 通知に含まれる情報

- **開始通知**: ジョブ名、開始時刻
- **完了通知**: ジョブ名、実行時間、開始/終了時刻、カスタム詳細
- **エラー通知**: ジョブ名、エラー内容、スタックトレース

### Cronジョブの設定

`docker/app/crontab` ファイルでスケジュール設定：
```cron
# 毎時実行
0 * * * * cd /app && python run_batch.py fetch_forex_rates

# 毎日午前3時に実行
0 3 * * * cd /app && python run_batch.py cleanup_old_data
```

## トラブルシューティング

### ポートが使用中の場合
`docker-compose.yml`の`ports`セクションで別のポートに変更してください：
```yaml
ports:
  - "8901:8000"  # 8901を任意のポートに変更
```

### データベース接続エラー
1. PostgreSQLコンテナが起動しているか確認
2. `.env`ファイルの`DATABASE_URL`が正しいか確認
3. ネットワーク設定を確認

### モジュールインポートエラー
```bash
# 依存関係の再インストール
docker-compose exec app pip install -r requirements.txt
```

## 開発のヒント

1. **APIドキュメント**: FastAPIの自動生成ドキュメント（`/docs`）を活用
2. **ホットリロード**: 開発時はコード変更が自動的に反映される
3. **型ヒント**: Pydanticスキーマで型安全性を確保
4. **非同期処理**: FastAPIの非同期機能を活用してパフォーマンス向上

## ライセンス

このプロジェクトはプライベートプロジェクトです。