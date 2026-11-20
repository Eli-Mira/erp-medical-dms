FROM python:3.14.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY web/ ./web/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini

RUN chown -R 1000:1000 /app
USER 1000:1000

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; r = urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:8000/health', timeout=4); code = r.status; r.close(); sys.exit(0 if code == 200 else 1)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
