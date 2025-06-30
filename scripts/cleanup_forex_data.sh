#!/bin/bash
# forex_ratesの定期クリーンアップスクリプト

# 保持期間（時間）
HOURS_TO_KEEP=${1:-24}  # デフォルト24時間

echo "Cleaning up forex_rates data older than $HOURS_TO_KEEP hours..."

# SQLコマンドを実行
docker-compose exec -T db psql -U fx_user -d fx_forecast << EOF
-- 古いデータを削除
DELETE FROM forex_rates 
WHERE created_at < NOW() - INTERVAL '$HOURS_TO_KEEP hours';

-- VACUUMで領域を最適化
VACUUM ANALYZE forex_rates;

-- 結果を表示
SELECT 
    'Cleanup completed' as status,
    COUNT(*) as remaining_records,
    MIN(created_at) as oldest_record,
    MAX(created_at) as newest_record,
    pg_size_pretty(pg_total_relation_size('forex_rates')) as table_size
FROM forex_rates;
EOF