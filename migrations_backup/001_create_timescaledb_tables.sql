-- Migration 001: TimescaleDB テーブル作成
-- 作成日: 2025-06-29
-- 説明: リアルタイムトレード分析システム用のTimescaleDBテーブル構造を作成

-- TimescaleDB拡張の有効化
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ティックデータテーブル（TimescaleDBハイパーテーブル）
CREATE TABLE IF NOT EXISTS tick_data (
    id BIGSERIAL,
    symbol VARCHAR(10) NOT NULL,           -- 通貨ペア (XAUUSD, BTCUSD等)
    timestamp TIMESTAMPTZ NOT NULL,       -- ティック時刻（UTCタイムゾーン）
    bid DECIMAL(12, 6) NOT NULL,          -- ビッド価格
    ask DECIMAL(12, 6) NOT NULL,          -- アスク価格
    spread DECIMAL(12, 6) GENERATED ALWAYS AS (ask - bid) STORED, -- スプレッド
    source VARCHAR(20) DEFAULT 'tradermade', -- データソース
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- TimescaleDBハイパーテーブル化（1時間ごとのチャンク）
SELECT create_hypertable('tick_data', 'timestamp', chunk_time_interval => INTERVAL '1 hour', if_not_exists => TRUE);

-- インデックス設定
CREATE INDEX IF NOT EXISTS idx_tick_data_symbol_time ON tick_data (symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_tick_data_timestamp ON tick_data (timestamp DESC);

-- ローソク足データテーブル
CREATE TABLE IF NOT EXISTS candlestick_data (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,       -- '15m', '1h', '4h'
    open_time TIMESTAMPTZ NOT NULL,      -- ローソク足開始時刻
    close_time TIMESTAMPTZ NOT NULL,     -- ローソク足終了時刻
    open_price DECIMAL(12, 6) NOT NULL,  -- 始値
    high_price DECIMAL(12, 6) NOT NULL,  -- 高値
    low_price DECIMAL(12, 6) NOT NULL,   -- 安値
    close_price DECIMAL(12, 6) NOT NULL, -- 終値
    tick_count INTEGER DEFAULT 0,        -- ティック数
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(symbol, timeframe, open_time)
);

-- TimescaleDBハイパーテーブル化（1日ごとのチャンク）
SELECT create_hypertable('candlestick_data', 'open_time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);

-- インデックス設定
CREATE INDEX IF NOT EXISTS idx_candlestick_symbol_timeframe_time ON candlestick_data (symbol, timeframe, open_time DESC);

-- 技術指標データテーブル
CREATE TABLE IF NOT EXISTS technical_indicators (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    indicator_type VARCHAR(20) NOT NULL,  -- 'sma_20', 'sma_50', 'ema_12' など
    value DECIMAL(12, 6) NOT NULL,
    metadata JSONB,                       -- 追加のパラメータ情報
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(symbol, timeframe, timestamp, indicator_type)
);

-- TimescaleDBハイパーテーブル化（1日ごとのチャンク）
SELECT create_hypertable('technical_indicators', 'timestamp', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);

-- インデックス設定
CREATE INDEX IF NOT EXISTS idx_technical_indicators_lookup ON technical_indicators (symbol, timeframe, indicator_type, timestamp DESC);

-- AI解析結果テーブル
CREATE TABLE IF NOT EXISTS ai_analysis_results (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    analysis_timestamp TIMESTAMPTZ NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    entry_signal VARCHAR(10),             -- 'BUY', 'SELL', 'HOLD'
    confidence_score DECIMAL(5, 4),       -- 信頼度 (0.0000 - 1.0000)
    reasoning TEXT,                       -- AI の判断理由
    technical_data JSONB,                 -- 解析に使用した技術指標データ
    anthropic_response JSONB,             -- Anthropic APIの完全なレスポンス
    notification_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- インデックス設定
CREATE INDEX IF NOT EXISTS idx_ai_analysis_symbol_time ON ai_analysis_results (symbol, analysis_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ai_analysis_signals ON ai_analysis_results (entry_signal, notification_sent);

-- 通知履歴テーブル
CREATE TABLE IF NOT EXISTS notification_history (
    id BIGSERIAL PRIMARY KEY,
    analysis_id BIGINT REFERENCES ai_analysis_results(id),
    notification_type VARCHAR(20) NOT NULL, -- 'slack', 'email', 'push'
    recipient VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',    -- 'pending', 'sent', 'failed'
    sent_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ゾーン管理テーブル（サポート・レジスタンスライン）
CREATE TABLE IF NOT EXISTS price_zones (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    zone_type VARCHAR(20) NOT NULL,       -- 'support', 'resistance'
    price_level DECIMAL(12, 6) NOT NULL,
    strength INTEGER DEFAULT 1,           -- ゾーンの強度
    first_touch TIMESTAMPTZ NOT NULL,     -- 初回タッチ時刻
    last_touch TIMESTAMPTZ,               -- 最終タッチ時刻
    touch_count INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- インデックス設定
CREATE INDEX IF NOT EXISTS idx_price_zones_symbol_active ON price_zones (symbol, is_active);
CREATE INDEX IF NOT EXISTS idx_price_zones_price ON price_zones (symbol, price_level);

-- データ保持ポリシー設定
-- ティックデータ: 30日間保持
SELECT add_retention_policy('tick_data', INTERVAL '30 days', if_not_exists => TRUE);

-- ローソク足データ: 1年間保持
SELECT add_retention_policy('candlestick_data', INTERVAL '1 year', if_not_exists => TRUE);

-- 技術指標: 1年間保持
SELECT add_retention_policy('technical_indicators', INTERVAL '1 year', if_not_exists => TRUE);

-- 圧縮ポリシー設定（パフォーマンス向上）
-- ティックデータ: 1日後に圧縮
SELECT add_compression_policy('tick_data', INTERVAL '1 day', if_not_exists => TRUE);

-- ローソク足データ: 7日後に圧縮
SELECT add_compression_policy('candlestick_data', INTERVAL '7 days', if_not_exists => TRUE);

-- 技術指標: 7日後に圧縮
SELECT add_compression_policy('technical_indicators', INTERVAL '7 days', if_not_exists => TRUE);

-- 統計情報更新の継続的な集計ビュー（パフォーマンス向上）
CREATE MATERIALIZED VIEW IF NOT EXISTS candlestick_hourly_stats
WITH (timescaledb.continuous) AS
SELECT 
    symbol,
    timeframe,
    time_bucket('1 hour', open_time) AS hour,
    COUNT(*) as candle_count,
    AVG(close_price) as avg_price,
    MAX(high_price) as max_price,
    MIN(low_price) as min_price
FROM candlestick_data
GROUP BY symbol, timeframe, hour;

-- 継続的な集計ビューのリフレッシュポリシー
SELECT add_continuous_aggregate_policy('candlestick_hourly_stats',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE);

-- マイグレーション完了ログ
INSERT INTO migration_log (version, description, applied_at) 
VALUES (1, 'TimescaleDB テーブル作成', NOW())
ON CONFLICT (version) DO NOTHING;