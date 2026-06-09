FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x scripts/entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV RUN_MODE=web

EXPOSE 8000

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
