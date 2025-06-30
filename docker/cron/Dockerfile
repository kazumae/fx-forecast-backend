FROM python:3.11-slim

# cronとビルドツールをインストール
RUN apt-get update && apt-get install -y \
    cron \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# 必要なファイルをコピー
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# cronジョブファイルをコピー
COPY docker/cron/crontab /etc/cron.d/fx-cron

# cronファイルに実行権限を付与
RUN chmod 0644 /etc/cron.d/fx-cron

# crontabを適用
RUN crontab /etc/cron.d/fx-cron

# ログディレクトリを作成
RUN mkdir -p /var/log/cron

# cronをフォアグラウンドで実行
CMD ["cron", "-f"]