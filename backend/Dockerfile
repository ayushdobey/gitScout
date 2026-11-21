# =============================================================================
# GitScout Backend Production Dockerfile
# Multi-stage, non-root secure container for FastAPI & Code Intelligence Engine
# =============================================================================

FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies for compiling native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# -----------------------------------------------------------------------------
# Final Production Stage
# -----------------------------------------------------------------------------
FROM python:3.11-slim as runner

WORKDIR /app

# Install runtime dependencies (git, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create secure unprivileged user
RUN groupadd -g 10001 gitscout && \
    useradd -u 10000 -g gitscout -m -s /bin/bash gitscout

# Copy installed Python packages from builder stage
COPY --from=builder /root/.local /home/gitscout/.local
ENV PATH=/home/gitscout/.local/bin:$PATH
ENV PYTHONPATH=/app

# Copy application source code and migrations
COPY --chown=gitscout:gitscout alembic alembic
COPY --chown=gitscout:gitscout alembic.ini .
COPY --chown=gitscout:gitscout app app

USER gitscout

# Health check probe against API health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

