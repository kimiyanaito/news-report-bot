FROM python:3.12-slim

# Locale / timezone
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=Asia/Tokyo \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# tzdata だけ入れておく（日本時間のログ出力用）
RUN apt-get update && apt-get install -y --no-install-recommends \
        tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存関係
COPY requirements.txt ./
RUN pip install -r requirements.txt

# アプリ本体
COPY src/ ./src/
COPY config/ ./config/
COPY templates/ ./templates/

# Railway cron 起動コマンド
CMD ["python", "-m", "src.main"]
