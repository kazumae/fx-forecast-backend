#!/bin/bash
# 全テストを実行するスクリプト

set -e

echo "🧪 Running all tests..."

# Change to backend directory
cd "$(dirname "$0")/.."

echo -e "\n📋 Unit Tests"
echo "============="
python tests/unit/core/test_tradermade_config.py
python tests/unit/stream/test_error_handler.py

echo -e "\n🔗 Integration Tests"
echo "==================="
echo "Note: Integration tests require Docker environment and external services"
echo "Run manually with:"
echo "  docker-compose exec app python tests/integration/test_slack_integration.py"
echo "  docker-compose exec tradermade-stream python tests/integration/test_slack_notifications.py"

echo -e "\n🌐 E2E Tests"
echo "============"
if [ -f /.dockerenv ]; then
    echo "Running in Docker container..."
    bash tests/e2e/test_api_endpoints.sh
else
    echo "E2E tests require Docker environment. Run with:"
    echo "  bash tests/e2e/test_api_endpoints.sh"
fi

echo -e "\n✅ Test execution completed!"