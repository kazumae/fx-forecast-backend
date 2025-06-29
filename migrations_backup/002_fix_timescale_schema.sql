-- Migration 002: TimescaleDB スキーマ修正
-- 作成日: 2025-06-29
-- 説明: ハイパーテーブル対応のためのスキーマ修正とテーブル再作成

-- 既存テーブルの削除（必要に応じて）
DROP TABLE IF EXISTS candlestick_data CASCADE;
DROP TABLE IF EXISTS technical_indicators CASCADE;
DROP TABLE IF EXISTS ai_analysis_results CASCADE;
DROP TABLE IF EXISTS notification_history CASCADE;
DROP TABLE IF EXISTS price_zones CASCADE;

-- ローソク足データテーブル（パーティションキーを主キーに含める）
CREATE TABLE candlestick_data (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time TIMESTAMPTZ NOT NULL,
    close_time TIMESTAMPTZ NOT NULL,
    open_price DECIMAL(12, 6) NOT NULL,
    high_price DECIMAL(12, 6) NOT NULL,
    low_price DECIMAL(12, 6) NOT NULL,
    close_price DECIMAL(12, 6) NOT NULL,
    tick_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (symbol, timeframe, open_time)
);

-- TimescaleDBハイパーテーブル化（1日ごとのチャンク）
SELECT create_hypertable('candlestick_data', 'open_time', chunk_time_interval => INTERVAL '1 day');

-- インデックス設定
CREATE INDEX idx_candlestick_symbol_timeframe_time ON candlestick_data (symbol, timeframe, open_time DESC);

-- 技術指標データテーブル（パーティションキーを主キーに含める）
CREATE TABLE technical_indicators (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    indicator_type TEXT NOT NULL,
    value DECIMAL(12, 6) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (symbol, timeframe, timestamp, indicator_type)
);

-- TimescaleDBハイパーテーブル化（1日ごとのチャンク）
SELECT create_hypertable('technical_indicators', 'timestamp', chunk_time_interval => INTERVAL '1 day');

-- インデックス設定
CREATE INDEX idx_technical_indicators_lookup ON technical_indicators (symbol, timeframe, indicator_type, timestamp DESC);

-- AI解析結果テーブル
CREATE TABLE ai_analysis_results (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    analysis_timestamp TIMESTAMPTZ NOT NULL,
    timeframe TEXT NOT NULL,
    entry_signal TEXT,
    confidence_score DECIMAL(5, 4),
    reasoning TEXT,
    technical_data JSONB,
    anthropic_response JSONB,
    notification_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- インデックス設定
CREATE INDEX idx_ai_analysis_symbol_time ON ai_analysis_results (symbol, analysis_timestamp DESC);
CREATE INDEX idx_ai_analysis_signals ON ai_analysis_results (entry_signal, notification_sent);

-- 通知履歴テーブル
CREATE TABLE notification_history (
    id BIGSERIAL PRIMARY KEY,
    analysis_id BIGINT REFERENCES ai_analysis_results(id),
    notification_type TEXT NOT NULL,
    recipient TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    sent_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 価格ゾーン管理テーブル
CREATE TABLE price_zones (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    zone_type TEXT NOT NULL,
    price_level DECIMAL(12, 6) NOT NULL,
    strength INTEGER DEFAULT 1,
    first_touch TIMESTAMPTZ NOT NULL,
    last_touch TIMESTAMPTZ,
    touch_count INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- インデックス設定
CREATE INDEX idx_price_zones_symbol_active ON price_zones (symbol, is_active);
CREATE INDEX idx_price_zones_price ON price_zones (symbol, price_level);

-- データ保持ポリシー設定
SELECT add_retention_policy('candlestick_data', INTERVAL '1 year', if_not_exists => TRUE);
SELECT add_retention_policy('technical_indicators', INTERVAL '1 year', if_not_exists => TRUE);

-- 圧縮ポリシー設定（パフォーマンス向上）
-- TimescaleDB 2.14+ で columnstore が利用可能
-- ALTER TABLE candlestick_data SET (timescaledb.compress);
-- ALTER TABLE technical_indicators SET (timescaledb.compress);
-- SELECT add_compression_policy('candlestick_data', INTERVAL '7 days', if_not_exists => TRUE);
-- SELECT add_compression_policy('technical_indicators', INTERVAL '7 days', if_not_exists => TRUE);

-- マイグレーション完了ログ
INSERT INTO migration_log (version, description, applied_at) 
VALUES (2, 'TimescaleDB スキーマ修正', NOW())
ON CONFLICT (version) DO NOTHING;