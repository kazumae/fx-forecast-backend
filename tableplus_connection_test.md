# TablePlus接続設定

## 接続情報

### 基本設定
- **Name**: FX Forecast Local
- **Host/Socket**: 127.0.0.1 (localhostではなく127.0.0.1を使用)
- **Port**: 6543
- **User**: fx_user
- **Password**: fx_password
- **Database**: fx_forecast

### 詳細設定
- **Connection Type**: Standard Connection
- **SSL Mode**: Disable (またはPrefer)
- **SSH**: 使用しない

## トラブルシューティング

### 1. 接続テスト
```bash
# コマンドラインから接続確認
PGPASSWORD=fx_password psql -h 127.0.0.1 -p 6543 -U fx_user -d fx_forecast -c "SELECT 1"
```

### 2. よくある問題と解決方法

#### 問題: "password authentication failed"
- パスワードが正確に `fx_password` であることを確認
- コピー＆ペースト時の余分なスペースに注意

#### 問題: "could not connect to server"
- Dockerコンテナが起動していることを確認: `docker-compose ps`
- ポート6543が使用可能か確認: `lsof -i :6543`

#### 問題: "database does not exist"
- データベース名が正確に `fx_forecast` であることを確認

### 3. TablePlus設定画面での注意点
1. "Test Connection"ボタンで接続テストを実行
2. エラーメッセージを確認
3. 必要に応じて"Show Password"で入力内容を確認

### 4. 代替接続方法
もし127.0.0.1で接続できない場合は、以下を試してください：
- Host: `host.docker.internal`
- Host: `localhost`

### 5. 現在の接続状態確認
```bash
# PostgreSQLプロセスの確認
docker-compose exec db ps aux | grep postgres

# 接続中のセッション確認
docker-compose exec db psql -U fx_user -d fx_forecast -c "SELECT * FROM pg_stat_activity WHERE datname = 'fx_forecast';"
```