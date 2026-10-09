# Single container: FastAPI API + built TrustShield UI. Build: docker build -t trustshield-poc .
FROM node:22-slim AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PORT=8080 STATIC_DIR=/app/web/dist
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-gcp.txt
COPY backend/ ./
COPY --from=web /web/dist /app/web/dist
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
