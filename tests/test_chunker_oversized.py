import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.chunking import IntelligentChunker

text = """
```python
import asyncio
import time
from crawl4ai import CrawlerRunConfig, AsyncWebCrawler, CacheMode
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy, BestFirstCrawlingStrategy

async def stream_vs_nonstream():
    print("Stream vs Non-stream")
    base_config = CrawlerRunConfig(
        deep_crawl_strategy=BFSDeepCrawlStrategy(max_depth=1, include_external=False),
        scraping_strategy=LXMLWebScrapingStrategy(),
        verbose=False,
    )

    async with AsyncWebCrawler() as crawler:
        print("NON-STREAMING MODE")
        non_stream_config = base_config.clone()
        non_stream_config.stream = False

        start_time = time.perf_counter()
        results = await crawler.arun(
            url="https://docs.crawl4ai.com", config=non_stream_config
        )

        print(f"Received all {len(results)} results at once")
        
async def basic_deep_crawl():
    print("===== BASIC DEEP CRAWL SETUP =====")
    config = CrawlerRunConfig(
        deep_crawl_strategy=BFSDeepCrawlStrategy(max_depth=2, include_external=False),
        scraping_strategy=LXMLWebScrapingStrategy(),
        verbose=True,  # Show progress during crawling
    )

    async with AsyncWebCrawler() as crawler:
        start_time = time.perf_counter()
        results = await crawler.arun(url="https://docs.crawl4ai.com", config=config)

        pages_by_depth = {}
        for result in results:
            depth = result.metadata.get("depth", 0)
            if depth not in pages_by_depth:
                pages_by_depth[depth] = []
            pages_by_depth[depth].append(result.url)

        print(f"Crawled {len(results)} pages total")
        
```

## Options
Here are some options.
"""

chunker = IntelligentChunker(chunk_size=500)
chunks = chunker.chunk_text(text)
for i, c in enumerate(chunks):
    print(f"--- Chunk {i} ({len(c)} chars) ---")
    print(c)
    print("="*40)
