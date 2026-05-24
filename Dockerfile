# ── Stage 1: build frontend ──────────────────────────────────────────────────
FROM node:22-alpine AS fe-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ARG YANDEX_MAPS_API_KEY
ENV YANDEX_MAPS_API_KEY=${YANDEX_MAPS_API_KEY}
RUN npm run build

# ── Stage 2: Python backend ───────────────────────────────────────────────────
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=fe-build /frontend/dist /app/static

EXPOSE 8000
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
