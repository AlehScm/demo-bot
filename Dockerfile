FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=DEV

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN adduser --disabled-password --gecos "" app && \
    chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "interfaces.api.routes:app", "--host", "0.0.0.0", "--port", "8000"]