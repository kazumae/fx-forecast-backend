#!/bin/bash
# Signal monitor loop script - runs every minute

echo "Starting signal monitor loop..."

while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running signal monitor..."
    docker exec fx-backend-app python run_batch.py signal_monitor_v2
    
    # Wait 60 seconds
    sleep 60
done