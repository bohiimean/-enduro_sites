FROM python:3.12-slim

# Chromium нужен ровно одному провайдеру — investing.com. Он же делает образ
# тяжёлым, поэтому на машинах, где источник выключен, контейнер всё равно
# поднимается: браузер просто не запускается.
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CHROME_BINARY_PATH=/usr/bin/chromium

WORKDIR /app
COPY requirements.txt .
ENV PIP_DEFAULT_TIMEOUT=300
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
