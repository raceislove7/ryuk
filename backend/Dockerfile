# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /app/backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY backend/requirements.txt ./
COPY --chown=10001:10001 backend/app ./app
COPY --chown=10001:10001 fixtures/hotels.json /app/fixtures/hotels.json
RUN --mount=type=secret,id=proxy_ca \
    mkdir -p /app/data && chown 10001:10001 /app/data && chmod 700 /app/data && \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.txt
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
