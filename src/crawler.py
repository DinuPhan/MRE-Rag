import os
import re
from pathlib import Path
from typing import List, Optional, Set, Dict, Any
import asyncio
import httpx
from bs4 import BeautifulSoup

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

class CrawlerOptions:
    def __init__(self, max_depth: int = 0, max_pages: int = 10, chunk_size: int = 5000):
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.chunk_size = chunk_size

class MreCrawler:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def _fetch_sitemap_urls(self, sitemap_url: str) -> List[str]:
        urls = []
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(sitemap_url, timeout=10.0)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "xml")
                # Find all <loc> tags in sitemap
                for loc in soup.find_all("loc"):
                    if loc.text:
                        urls.append(loc.text.strip())
        except Exception as e:
            print(f"Error parsing sitemap {sitemap_url}: {e}")
        return urls

    async def crawl_urls(self, start_url: str, max_depth: int = 0, max_pages: int = 10) -> List[dict]:
        """
        Crawls a URL (or sitemap/.txt list), with optional recursive internal link discovery.
        Returns a list of extracted markdown dictionaries.
        """
        print(f"Starting execution for: {start_url} (Max Depth: {max_depth}, Max Pages: {max_pages})")
        
        config = CrawlerRunConfig(
            markdown_generator=DefaultMarkdownGenerator()
        )
        
        all_results = []
        visited_urls: Set[str] = set()
        queue = []
        
        # 1. Smart URL Detection
        if start_url.lower().endswith('.xml'):
            print(f"Detected sitemap: {start_url}")
            sitemap_urls = await self._fetch_sitemap_urls(start_url)
            queue = [(u, 0) for u in sitemap_urls[:max_pages]]
        elif start_url.lower().endswith('.txt'):
            print(f"Detected text list: {start_url}")
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(start_url, timeout=10.0)
                    urls = [line.strip() for line in response.text.splitlines() if line.strip().startswith("http")]
                    queue = [(u, 0) for u in urls[:max_pages]]
            except Exception as e:
                print(f"Error reading txt {start_url}: {e}")
        else:
            queue = [(start_url, 0)]
            
        async with AsyncWebCrawler() as crawler:
            while queue and len(visited_urls) < max_pages:
                # Process in batches to avoid overwhelming Crawl4AI
                current_batch = []
                while queue and len(current_batch) < 5 and (len(visited_urls) + len(current_batch)) < max_pages:
                    url, depth = queue.pop(0)
                    if url not in visited_urls:
                        visited_urls.add(url)
                        current_batch.append((url, depth))
                
                if not current_batch:
                    break
                    
                urls_to_crawl = [item[0] for item in current_batch]
                depths_to_crawl = {item[0]: item[1] for item in current_batch}
                
                print(f"Crawling batch of {len(urls_to_crawl)} URLs...")
                results = await crawler.arun_many(
                    urls=urls_to_crawl,
                    config=config
                )
                
                for result in results:
                    url = result.url
                    depth = depths_to_crawl.get(url, 0)
                    
                    if not result.success:
                        print(f"Failed to crawl {url}: {result.error_message}")
                        continue
                        
                    raw_markdown = result.markdown.raw_markdown if hasattr(result.markdown, 'raw_markdown') else result.markdown
                    self._export_to_llms_txt(url, raw_markdown)
                    
                    all_results.append({
                        "success": True,
                        "url": url,
                        "markdown": raw_markdown,
                        "title": result.metadata.get('title', 'Untitled') if result.metadata else 'Untitled'
                    })
                    
                    # 2. Recursive Link Extraction
                    if depth < max_depth:
                        internal_links = result.links.get("internal", [])
                        for link_info in internal_links:
                            next_url = link_info.get("href")
                            if next_url and next_url not in visited_urls:
                                queue.append((next_url, depth + 1))
                                
        return all_results
            
    def _export_to_llms_txt(self, url: str, content: str):
        """
        Exports the crawled markdown content to the local output directory.
        """
        safe_name = "".join([c if c.isalnum() else "_" for c in url]).strip("_")
        safe_name = safe_name[:50]
        file_path = self.output_dir / f"{safe_name}_llms.txt"
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# Source: {url}\n\n")
                f.write(content)
        except Exception as e:
            print(f"Failed to export knowledge to {file_path}: {e}")

if __name__ == "__main__":
    crawler = MreCrawler()
    asyncio.run(crawler.crawl_urls("https://crawl4ai.com"))
