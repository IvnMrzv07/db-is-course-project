FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY . .
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend
CMD ["uvicorn", "content_service.presentation.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "deploy/config/runtime-logging.yaml"]
