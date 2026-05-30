FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY frontend/ frontend/

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

RUN adduser --disabled-password --gecos '' appuser
USER appuser

WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
