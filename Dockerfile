# Multi-stage build: small, pinned, non-root — supply-chain conscious.
FROM python:3.12-slim AS build

WORKDIR /app
COPY pyproject.toml README.md ./
COPY control_plane ./control_plane
COPY data ./data
RUN pip install --no-cache-dir --prefix=/install ".[api]"

FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/LoluPapi/ai-control-plane"
LABEL org.opencontainers.image.description="Multi-tenant AI control plane API"
LABEL org.opencontainers.image.licenses="MIT"

RUN useradd --create-home --uid 1000 aicp
COPY --from=build /install /usr/local
COPY --from=build /app/data /app/data

USER aicp
WORKDIR /app
ENV AICP_DATA_ROOT=/app/data
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')"

CMD ["uvicorn", "control_plane.api:app", "--host", "0.0.0.0", "--port", "8080"]
