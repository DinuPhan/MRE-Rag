# Stage 1: Builder
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy AS builder

# Set env for uv (Pragmatic Speed)
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /build

# Install uv for high-performance dependency management
RUN pip install --no-cache-dir uv

# Copy only dependency files first to maximize cache hit ratio
COPY pyproject.toml . 

# Build dependencies including tree-sitter
# We use a cache mount to persist uv's cache between builds
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system \
    "crawl4ai>=0.4.0" \
    "tree-sitter>=0.21.0" \
    "tree-sitter-python" \
    "fastapi>=0.115.0" \
    "uvicorn>=0.30.6" \
    "qdrant-client>=1.11.0" \
    "google-genai>=0.3.0" \
    "neo4j>=5.24.0" \
    "beautifulsoup4>=4.12.3"

# Stage 2: Runtime
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy AS runtime

# CIS Compliance: Create a non-privileged user
RUN groupadd -g 10001 graphrag && \
    useradd -u 10001 -g graphrag -m -s /sbin/nologin graphrag

WORKDIR /app

# Copy the python environment from builder
COPY --from=builder /usr/local/lib/python3.11/dist-packages /usr/local/lib/python3.11/dist-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Install ONLY Chromium (Skip WebKit/Firefox to save ~700MB)
# We use the playwright user to ensure permissions are correct
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.ms-playwright
RUN playwright install --with-deps chromium && \
    rm -rf /var/lib/apt/lists/*

# Pre-prepare Tree-sitter grammar cache directory
RUN mkdir -p /app/tree-sitter-grammars && \
    chown -R graphrag:graphrag /app

# Copy application source
COPY --chown=graphrag:graphrag . .

# Switch to non-root user
USER graphrag

# Healthcheck to ensure FastAPI is alive
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8051/health || exit 1

EXPOSE 8051

# Use absolute paths for stability
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8051"]