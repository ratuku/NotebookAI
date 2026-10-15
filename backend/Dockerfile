FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements-dev.lock /app/requirements.lock
RUN pip install -r requirements.lock
COPY ai /app/ai
COPY backend /app/backend
RUN pip install --no-deps ./ai ./backend && \
    useradd --create-home --uid 10001 notebook && \
    mkdir -p /data/models /data/qdrant && chown -R notebook:notebook /data
USER notebook
WORKDIR /app/backend
ENV MODEL_CACHE_PATH=/data/models QDRANT_PATH=/data/qdrant HF_HOME=/data/models/huggingface
EXPOSE 8000
CMD ["uvicorn", "notebook_backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
