# データベース構成

## 概要
このシステムはPostgreSQL 15を使用したFX取引データ管理システムです。

## データベース情報
- **データベース名**: fx_forecast
- **ユーザー**: fx_user
- **ポート**: 6543（デフォルトの5432から変更）

## テーブル構成

### 1. forex_rates
リアルタイムの為替レートデータを格納

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | INTEGER | 主キー |
| currency_pair | VARCHAR | 通貨ペア（例：XAUUSD） |
| rate | FLOAT | 中間価格 |
| bid | FLOAT | ビッド価格 |
| ask | FLOAT | アスク価格 |
| volume | FLOAT | 取引量（現在未使用） |
| timestamp | TIMESTAMP WITH TIME ZONE | レート時刻 |
| created_at | TIMESTAMP WITH TIME ZONE | 作成時刻 |

### 2. candlestick_data
ローソク足データを格納（複数の時間枠）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| symbol | TEXT | 通貨ペア |
| timeframe | TEXT | 時間枠（1m, 5m, 15m, 1h, 4h, 1d） |
| open_time | TIMESTAMP WITH TIME ZONE | 開始時刻 |
| close_time | TIMESTAMP WITH TIME ZONE | 終了時刻 |
| open_price | DECIMAL(12,6) | 始値 |
| high_price | DECIMAL(12,6) | 高値 |
| low_price | DECIMAL(12,6) | 安値 |
| close_price | DECIMAL(12,6) | 終値 |
| tick_count | INTEGER | ティック数 |
| created_at | TIMESTAMP WITH TIME ZONE | 作成時刻 |
| updated_at | TIMESTAMP WITH TIME ZONE | 更新時刻 |

### 3. technical_indicators
技術指標データを格納

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | INTEGER | 主キー |
| symbol | VARCHAR(10) | 通貨ペア |
| timeframe | VARCHAR(5) | 時間枠 |
| timestamp | TIMESTAMP WITH TIME ZONE | 計算時刻 |
| ema_5, ema_10, ema_15, ema_20, ema_50, ema_100, ema_200 | FLOAT | 指数移動平均線 |
| rsi_14 | FLOAT | RSI（14期間） |
| macd | FLOAT | MACD値 |
| macd_signal | FLOAT | MACDシグナル |
| macd_histogram | FLOAT | MACDヒストグラム |
| bb_upper | FLOAT | ボリンジャーバンド上限 |
| bb_middle | FLOAT | ボリンジャーバンド中央 |
| bb_lower | FLOAT | ボリンジャーバンド下限 |
| atr_14 | FLOAT | ATR（14期間） |
| stoch_k | FLOAT | ストキャスティクス %K |
| stoch_d | FLOAT | ストキャスティクス %D |
| created_at | TIMESTAMP WITH TIME ZONE | 作成時刻 |

## データフロー
1. TraderMade WebSocket → forex_rates
2. forex_rates → candlestick_data（リアルタイム生成）
3. candlestick_data → technical_indicators（1分ごとに計算）

## 管理コマンド

### データベース接続
```bash
docker-compose exec db psql -U fx_user -d fx_forecast
```

### データ確認
```sql
-- 最新の為替レート
SELECT * FROM forex_rates ORDER BY created_at DESC LIMIT 10;

-- ローソク足データ
SELECT * FROM candlestick_data WHERE timeframe = '1m' ORDER BY open_time DESC LIMIT 10;

-- 技術指標
SELECT * FROM technical_indicators ORDER BY created_at DESC LIMIT 10;
```

### データサイズ確認
```sql
SELECT 
    table_name,
    pg_size_pretty(pg_total_relation_size(table_name::regclass)) as size
FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY pg_total_relation_size(table_name::regclass) DESC;
```