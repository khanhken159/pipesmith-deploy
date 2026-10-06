# ---- Stage 1: cài thư viện vào virtualenv riêng (/opt/venv) ----
FROM python:3.11-slim AS builder

WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: image chạy (không có công cụ build, chạy bằng user thường) ----
FROM python:3.11-slim

WORKDIR /app
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DBT_SEND_ANONYMOUS_USAGE_STATS=false \
    LLM_PROVIDER=mock

COPY --from=builder /opt/venv /opt/venv
RUN useradd -m appuser

COPY . .
RUN mkdir -p /app/data /app/pipelines/workspaces && chown -R appuser:appuser /app

USER appuser

# Render/Railway truyền cổng qua biến PORT; chạy máy thì mặc định 8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", \"8000\")}/health')" || exit 1

CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
