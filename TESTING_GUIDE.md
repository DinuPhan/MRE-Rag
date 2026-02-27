# Testing Guide

This project embraces a containerized environment to ensure clean, isolated, and reproducible execution. All testing scripts located in the `/tests` directory should be executed directly within the active application container.

## Prerequisites

Before running any tests, ensure your Docker Compose environment is active and the containers are running:
```bash
docker compose up -d
```

## Running Tests via Docker

The generalized approach for running any test script is to execute it within the `mre_rag-app-1` container using the `docker exec` command:

```bash
docker exec mre_rag-app-1 python3 /app/tests/<script_name>.py
```

### Available Test Scripts

#### 1. `test_chunker.py`
Tests the `IntelligentChunker` module in isolation. Verifies that markdown headers are correctly split and code blocks are preserved without sending anything to the database or embedding APIs.
**Execute:**
```bash
docker exec mre_rag-app-1 python3 /app/tests/test_chunker.py
```

#### 2. `test_pipeline.py`
Performs a full ingestion run using the `RagPipeline`. It crawls the setup URL, generates textual chunks, retrieves embeddings, upserts them to the database, and conducts a query to ensure retrieval works.
**Execute:**
```bash
docker exec mre_rag-app-1 python3 /app/tests/test_pipeline.py
```

#### 3. `test_hybrid_pipeline.py`
Tests the Phase 6 Contextual AI and Code Snippet isolation pipeline, including the new concurrent embedding execution and AI query expansion features. Checks if code blocks are properly extracted, titled, and stored in the dedicated `_code` collection.
**Execute:**
```bash
docker exec mre_rag-app-1 python3 /app/tests/test_hybrid_pipeline.py
```

#### 4. `test_db.py`
A simple utility to verify the state of your Qdrant database, listing out all active collections and providing a 150-character sample of an embedded document inside them.
**Execute:**
```bash
docker exec mre_rag-app-1 python3 /app/tests/test_db.py
```

---
*Note: While scripts like `test_chunker.py` and `test_db.py` can technically be run locally safely, executing them uniformly through the Docker container guarantees zero environment or dependency mismatch warnings.*
