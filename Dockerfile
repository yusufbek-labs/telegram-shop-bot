FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

# The SQLite file lives in /app/data, which docker-compose mounts as a volume.
RUN useradd --create-home bot && mkdir -p /app/data && chown -R bot /app
USER bot

# Seed the demo catalog if the database is empty, then start the bot.
CMD ["sh", "-c", "python -m scripts.seed && python -m app"]
