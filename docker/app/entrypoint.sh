#!/bin/bash
# エントリーポイントスクリプト

# cronサービスを開始（バックグラウンド）
if [ -f /etc/cron.d/fx-cron ]; then
    echo "Starting cron service..."
    service cron start
fi

# メインコマンドを実行
exec "$@"