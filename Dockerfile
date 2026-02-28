FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app

# Copy dependency files
COPY pyproject.toml .

# Install dependencies (since pyproject.toml has requires-python and dependencies)
RUN pip install --no-cache-dir \
    "crawl4ai>=0.4.0" \
    "mcp>=1.0.0" \
    "fastapi>=0.115.0" \
    "uvicorn>=0.30.6" \
    "pydantic>=2.9.0" \
    "qdrant-client>=1.11.0" \
    "google-genai>=0.3.0" \
    "python-dotenv>=1.0.1" \
    "httpx>=0.27.0" \
    "markdown>=3.7" \
    "beautifulsoup4>=4.12.3" \
    "neo4j>=5.24.0"

# Install Chromium matching the pip playwright version
RUN playwright install chromium

# Copy the rest of the application
COPY . .

# Expose the API port
EXPOSE 8051

# Run the FastAPI server
CMD ["sh", "-c", "cd src && uvicorn server:app --host 0.0.0.0 --port 8051"]
