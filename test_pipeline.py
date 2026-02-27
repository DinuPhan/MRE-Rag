import asyncio
import sys
import os
import time

# Add the 'src' directory to the Python path to resolve imports properly
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.rag_pipeline import RagPipeline
import time

async def main():
    print("Initializing RagPipeline...")
    pipeline = RagPipeline()
    
    url_to_crawl = "https://docs.crawl4ai.com/core/quickstart/"
    print(f"\n--- Testing Ingestion for {url_to_crawl} ---")
    start_time = time.time()
    result = await pipeline.ingest_url(url_to_crawl)
    end_time = time.time()
    
    print("\n[Ingestion Result]")
    print(result)
    print(f"Time Taken: {end_time - start_time:.2f} seconds")

    if result.get("success"):
        query = "How to install crawl4ai?"
        print(f"\n--- Testing Query: '{query}' ---")
        start_time = time.time()
        search_results = pipeline.query(query, limit=3)
        end_time = time.time()
        
        print("\n[Query Result]")
        for i, res in enumerate(search_results):
            print(f"[{i+1}] Score: {res.get('score')} | Content snippet: {res.get('content')[:100]}")
        
        print(f"Query Time Taken: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main())
