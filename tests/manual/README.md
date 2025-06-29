# Manual Tests

このディレクトリには、特定の状況を再現するための手動実行スクリプトが含まれています。

## docker_network_test.py

Dockerコンテナのネットワーク接続を操作して、再接続機能をテストするスクリプトです。

### 使用方法
```bash
# ホストマシンから実行（Docker Python SDKが必要）
python tests/manual/docker_network_test.py
```

### 前提条件
- Docker Python SDK (`pip install docker`)
- tradermade-streamコンテナが実行中であること

### テスト内容
1. コンテナを一時停止（ネットワーク切断をシミュレート）
2. 30秒待機
3. コンテナを再開
4. 再接続動作を確認