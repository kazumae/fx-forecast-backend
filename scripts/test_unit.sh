#!/bin/bash
# 単体テストのみを実行するスクリプト

set -e

echo "🧪 Running unit tests..."

# Change to backend directory
cd "$(dirname "$0")/.."

# Run unit tests
echo -e "\n📋 Core Tests"
python tests/unit/core/test_tradermade_config.py

echo -e "\n📋 Stream Tests"
python tests/unit/stream/test_error_handler.py

echo -e "\n✅ Unit tests completed!"