FROM python:3.12-slim

# curl is used by Render's health check probe
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy requirements first so this layer is cached when only code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R appuser:appuser /app
USER appuser

# Render dynamically injects $PORT; exposing 8080 is documentation only
EXPOSE 8080

# Shell form so $PORT is expanded at runtime by /bin/sh
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
