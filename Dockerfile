FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /bin/bash -m appuser

RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app && \
    chmod -R 775 /app/logs

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY --chown=appuser:appuser . /app

USER appuser

CMD ["python", "scripts/smoke_test_db.py"]