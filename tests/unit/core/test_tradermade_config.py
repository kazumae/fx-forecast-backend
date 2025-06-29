#!/usr/bin/env python3
"""TraderMade設定のテストスクリプト"""

import os
import sys
# Add backend directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from src.core.tradermade_config import TraderMadeConfig

def test_without_api_key():
    """APIキーなしでエラーになることを確認"""
    print("Test 1: APIキーなしでの実行")
    # 環境変数をクリア
    os.environ.pop('TRADERMADE_API_KEY', None)
    os.environ.pop('TRADERMADE_STREAMING_API_KEY', None)
    
    try:
        config = TraderMadeConfig.from_env()
        print("❌ エラーが発生しませんでした")
    except ValueError as e:
        print(f"✅ 期待通りのエラー: {e}")

def test_with_api_key():
    """正常な設定で動作することを確認"""
    print("\nTest 2: 正常な設定での実行")
    os.environ['TRADERMADE_API_KEY'] = 'test_key_12345678'
    
    try:
        config = TraderMadeConfig.from_env()
        print(f"✅ 設定の読み込み成功")
        print(f"   API Key (masked): {config.get_masked_api_key()}")
        print(f"   WebSocket URL: {config.websocket_url}")
        print(f"   Target Symbol: {config.target_symbol}")
        print(f"   Log Level: {config.log_level}")
        print(f"   Reconnect Interval: {config.reconnect_interval}")
    except Exception as e:
        print(f"❌ エラー: {e}")

def test_validation():
    """バリデーションのテスト"""
    print("\nTest 3: バリデーションテスト")
    os.environ['TRADERMADE_API_KEY'] = 'test_key'
    
    # 正常な設定
    try:
        config = TraderMadeConfig.from_env()
        config.validate()
        print("✅ 正常な設定のバリデーション成功")
    except Exception as e:
        print(f"❌ エラー: {e}")
    
    # 不正なWebSocket URL
    try:
        config = TraderMadeConfig.from_env()
        config.websocket_url = "http://invalid.url"
        config.validate()
        print("❌ 不正なURLでエラーが発生しませんでした")
    except ValueError as e:
        print(f"✅ 期待通りのエラー: {e}")
    
    # 不正なlog level
    try:
        config = TraderMadeConfig.from_env()
        config.log_level = "INVALID"
        config.validate()
        print("❌ 不正なログレベルでエラーが発生しませんでした")
    except ValueError as e:
        print(f"✅ 期待通りのエラー: {e}")

def test_env_override():
    """環境変数のオーバーライドテスト"""
    print("\nTest 4: 環境変数のオーバーライド")
    os.environ['TRADERMADE_API_KEY'] = 'test_key'
    os.environ['TARGET_SYMBOL'] = 'EURUSD'
    os.environ['LOG_LEVEL'] = 'DEBUG'
    os.environ['RECONNECT_INTERVAL'] = '5'
    
    try:
        config = TraderMadeConfig.from_env()
        print(f"✅ 環境変数のオーバーライド成功")
        print(f"   Target Symbol: {config.target_symbol}")
        print(f"   Log Level: {config.log_level}")
        print(f"   Reconnect Interval: {config.reconnect_interval}")
    except Exception as e:
        print(f"❌ エラー: {e}")

if __name__ == "__main__":
    print("TraderMade設定テストを開始します...")
    print("=" * 50)
    
    test_without_api_key()
    test_with_api_key()
    test_validation()
    test_env_override()
    
    print("\n" + "=" * 50)
    print("テスト完了")