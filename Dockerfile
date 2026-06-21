FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-deu \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server ./server
COPY src ./src
COPY scripts ./scripts
COPY docker/backend-start.sh /usr/local/bin/backend-start.sh
RUN chmod +x /usr/local/bin/backend-start.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import json, urllib.request; json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3))"

ENTRYPOINT ["backend-start.sh"]
CMD ["uvicorn", "server.app.api:app", "--host", "0.0.0.0", "--port", "8000"]
