import sys
import os
import asyncio
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.rag_pipeline import RagPipeline

async def mock_crawl(*args, **kwargs):
    return [{
        "url": "hybrid_test",
        "title": "Hybrid Test Page",
        "markdown": """# Hybrid Test
This is a test of the hybrid pipeline.

## Python Example
Here is a very interesting python example that does something very specific. It shows how you test hybrid pipelines.
```python
def test_hybrid():
    print("hybrid test successful!")
```
This example is very good and is used to test the backend.
"""
    }]

async def run_test():
    pipeline = RagPipeline()
    collection = pipeline.qdrant.escape_url("hybrid_test")
    
    # Overwrite crawler just for the test
    pipeline.crawler.crawl_urls = mock_crawl
    
    print("\n--- Running STANDARD Ingestion ---")
    result_standard = await pipeline.ingest_url("hybrid_test", enable_contextual_ai=False)
    print(result_standard)
    
    # Reset
    try:
        pipeline.qdrant.client.delete_collection(collection)
        pipeline.qdrant.client.delete_collection(collection + "_code")
    except: pass
    
    print("\n--- Running AI-CONTEXT Ingestion ---")
    result_ai = await pipeline.ingest_url("hybrid_test", enable_contextual_ai=True)
    print(result_ai)
    
    print("\n--- Querying Code Snippets ---")
    search = pipeline.qdrant.search_code(collection, [0.0]*pipeline.embeddings.dimension, limit=1)
    if search:
        print("Code Snippet Embedded Payload:\n")
        print(search[0]['content'])

if __name__ == "__main__":
    asyncio.run(run_test())
