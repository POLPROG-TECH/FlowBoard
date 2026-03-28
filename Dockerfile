FROM python:3.13-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir --prefix=/install .

# ── Runtime stage ──────────────────────────────────────────────────
FROM python:3.13-slim

LABEL maintainer="FlowBoard Team"
LABEL org.opencontainers.image.title="FlowBoard"
LABEL org.opencontainers.image.description="Jira-Based Delivery & Workload Intelligence Dashboard"

RUN groupadd -r flowboard && useradd -r -g flowboard -d /app flowboard

COPY --from=builder /install /usr/local
COPY src/ /app/src/
COPY examples/ /app/examples/
COPY config.schema.json /app/

WORKDIR /app
RUN mkdir -p /app/output && chown -R flowboard:flowboard /app

USER flowboard

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    FLOWBOARD_LOG_FORMAT=json \
    PORT=8084

EXPOSE 8084

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",\"8084\")}/health/live')" || exit 1

ENTRYPOINT ["flowboard"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8084"]
