FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY backend /app/backend
COPY data/examples /app/data/examples
RUN python -m pip install --no-cache-dir /app/backend \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "pharma_validator_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
