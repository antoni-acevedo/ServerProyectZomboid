FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && set -eux; \
       curl -fsSL "https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz" -o /tmp/docker.tgz; \
       tar xzf /tmp/docker.tgz -C /tmp; \
       mv /tmp/docker/docker /usr/local/bin/docker; \
       chmod +x /usr/local/bin/docker; \
       rm -rf /tmp/docker*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY schema.py .
COPY templates ./templates

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -fsS -u "${PANEL_USERNAME:-admin}:${PANEL_PASSWORD:-admin}" http://localhost:8080/healthz || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
