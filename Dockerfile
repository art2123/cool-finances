FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# pyproject.toml уже в репо — не зависим от requirements.txt
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
RUN chmod +x scripts/entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV RUN_MODE=web

EXPOSE 8000

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
