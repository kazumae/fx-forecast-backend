-- Migration 000: マイグレーション管理テーブル作成
-- 作成日: 2025-06-29
-- 説明: マイグレーション履歴を管理するためのテーブル

CREATE TABLE IF NOT EXISTS migration_log (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    checksum VARCHAR(64)
);

-- 初期レコード挿入
INSERT INTO migration_log (version, description, applied_at) 
VALUES (0, 'マイグレーション管理テーブル作成', NOW())
ON CONFLICT (version) DO NOTHING;