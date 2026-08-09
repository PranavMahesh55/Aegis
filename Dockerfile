FROM node:22-bookworm-slim AS web-build
WORKDIR /build/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AEGIS_DATABASE_PATH=/app/var/aegis.db \
    AEGIS_CONTEXT_DATABASE_PATH=/app/var/aegis-context.db \
    AEGIS_DATA_MODE=seeded \
    AEGIS_PRIME_BLOCKED=true
WORKDIR /app
COPY apps/api/requirements.lock /app/apps/api/requirements.lock
RUN pip install --no-cache-dir -r /app/apps/api/requirements.lock
COPY apps/api/ /app/apps/api/
RUN pip install --no-cache-dir --no-deps /app/apps/api
COPY infra/datahub/ /app/infra/datahub/
COPY scripts/datahub/ /app/scripts/datahub/
COPY --from=web-build /build/apps/web/dist /app/apps/web/dist
RUN mkdir -p /app/var && useradd --create-home --uid 10001 aegis && chown -R aegis:aegis /app
USER aegis
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live')"
CMD ["uvicorn", "aegis.main:app", "--app-dir", "apps/api", "--host", "0.0.0.0", "--port", "8000"]
