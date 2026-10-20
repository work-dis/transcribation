FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml .
COPY src ./src
COPY apps ./apps
COPY migrations ./migrations
COPY alembic.ini .
RUN pip install --no-cache-dir -e .[dev]
ENV PYTHONPATH=/app/src:/app
