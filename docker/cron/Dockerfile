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

# cronジョブファイルとスクリプトをコピー
COPY docker/cron/crontab /etc/cron.d/fx-cron
COPY docker/cron/entrypoint.sh /app/docker/cron/entrypoint.sh

# cronファイルとスクリプトに実行権限を付与、dos2unixをインストールして改行コードを修正
RUN apt-get update && apt-get install -y dos2unix && \
    chmod 0644 /etc/cron.d/fx-cron && \
    chmod +x /app/docker/cron/entrypoint.sh && \
    dos2unix /app/docker/cron/entrypoint.sh && \
    rm -rf /var/lib/apt/lists/*

# ログディレクトリを作成
RUN mkdir -p /var/log/cron

# cronスタートスクリプトをコピー
COPY docker/cron/start-cron.sh /start-cron.sh
RUN chmod +x /start-cron.sh

# cronを起動
CMD ["/start-cron.sh"]