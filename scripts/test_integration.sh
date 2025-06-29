#!/bin/bash
# 統合テストを実行するスクリプト

set -e

echo "🔗 Running integration tests..."

# Change to backend directory
cd "$(dirname "$0")/.."

# Check if running in Docker
if [ -f /.dockerenv ]; then
    echo "Running in Docker container..."
    
    echo -e "\n📋 Slack Integration Tests"
    python tests/integration/test_slack_integration.py
    
    echo -e "\n📋 Slack Notification Tests"
    python tests/integration/test_slack_notifications.py
else
    echo "Integration tests require Docker environment. Run with:"
    echo "  docker-compose exec app python tests/integration/test_slack_integration.py"
    echo "  docker-compose exec tradermade-stream python tests/integration/test_slack_notifications.py"
fi

echo -e "\n✅ Integration tests completed!"