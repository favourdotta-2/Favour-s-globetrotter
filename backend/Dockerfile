FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/data/destinations.json ./data/destinations.json

ARG SERVICE_NAME=monolith
ENV SERVICE_NAME=${SERVICE_NAME} \
    DATA_DIR=/var/lib/globetrotter \
    CATALOG_PATH=/app/data/destinations.json \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN useradd --create-home --uid 10001 traveler \
    && mkdir -p /var/lib/globetrotter \
    && chown -R traveler:traveler /app /var/lib/globetrotter
USER traveler
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
