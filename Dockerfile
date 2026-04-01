FROM python:3.11-slim

WORKDIR /app

# 🔥 CHANGE HERE (no nested folder now)
COPY . /app

RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    pkg-config \
    libcairo2-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 5000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "3"]