# MRE for RAG (Minimum Relevant Extraction for RAG)

A ready-to-use containerized web crawling and Retrieval-Augmented Generation (RAG) pipeline powered by FastAPI, `crawl4ai`, Qdrant that supports multiple embedding providers (Gemini, OpenAI, In-House LLMs)

## Overview

This project provides a complete, easy-to-deploy backend that can:
1. Crawl websites and extract clean markdown utilizing `crawl4ai` and Playwright.
2. Store the raw extracted text as `.txt` files locally for external consumption.
3. Chunk the content and compute embeddings using multiple supported providers (Google Gemini, OpenAI-compatible APIs, or custom In-House endpoints).
4. Store these embeddings in a local Qdrant vector database (dynamically adapting to the provider's vector dimensionality).
5. Provide a semantic search endpoint to query the ingested knowledge base.
6. Serve as an active Model Context Protocol (MCP) server.

## Architecture & Tech Stack

- **FastAPI**: Serves the RESTful endpoints (`/crawl` and `/query`).
- **FastMCP**: Provides the Model Context Protocol tools.
- **Qdrant**: Vector database running in a dedicated Docker container, persisting data to `./qdrant_storage`.
- **Text Embeddings**: Abstracted using `httpx` and `google-genai` to swap between Google Gemini, OpenAI `/v1/embeddings`, and custom API endpoints.
- **crawl4ai & Playwright**: Headless browser automation for high-quality webpage extraction.
- **Docker Compose**: Orchestrates the FastAPI app and the Qdrant database containers.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose.
- A valid Google Gemini API Key.

## Setup & Installation

1. Clone this repository.
2. Create a `.env` file in the root directory (you can copy `.env.example` if it exists) and configure your embedding provider:

```env
# Choose: GEMINI, OPENAI, or INHOUSE
EMBEDDING_PROVIDER=GEMINI

# If using GEMINI
GEMINI_API_KEY=your_gemini_api_key

# If using OPENAI 
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=your_openai_api_key
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSION=1536

# If using INHOUSE (/bi_encoder/encode format)
INHOUSE_BASE_URL=http://localhost:8000/api/v1
INHOUSE_API_KEY=your_inhouse_token
INHOUSE_EMBEDDING_DIMENSION=768
```
3. Start the application using Docker Compose:
   ```bash
   docker compose up -d --build
   ```

The application will be available at `http://localhost:8051`. Qdrant runs natively on ports `6333` and `6334`.

## API Usage

### 1. Ingesting Data (Crawl)

To crawl a webpage, generate embeddings, and store them in Qdrant, send a POST request to the `/crawl` endpoint with the target URL:

```bash
curl -X POST "http://localhost:8051/crawl" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://docs.crawl4ai.com/core/quickstart"}'
```

### 2. Semantic Search (Query)

To query the ingested knowledge base, send a POST request covering your search semantics:

```bash
curl -X POST "http://localhost:8051/query" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "Generating Markdown Output", 
       "url": "https://docs.crawl4ai.com/core/quickstart",
       "limit": 2
     }'
```

## Local Environment

If you ever wish to run the app outside of docker:
1. Set up a Python 3.12 virtual environment.
2. Install dependencies using `pip`: `pip install .` (or install manually matching `pyproject.toml`).
3. Manually initialize Playwright: `playwright install --with-deps chromium`.
4. Boot the server using Uvicorn directly from the `src` folder:
   ```bash
   cd src && uvicorn server:app --host 0.0.0.0 --port 8051
   ```
*(Note: If `QDRANT_URL` isn't found in your environment, Qdrant will automatically fall back to an in-memory instance for testing purposes.)*
