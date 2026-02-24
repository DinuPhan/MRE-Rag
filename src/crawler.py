import os
from pathlib import Path
from typing import List, Optional
import asyncio

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

class CrawlerOptions:
    def __init__(self, max_depth: int = 1, chunk_size: int = 5000):
        self.max_depth = max_depth
        self.chunk_size = chunk_size

class MreCrawler:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def crawl_url(self, url: str) -> dict:
        """
        Crawls a single URL using Crawl4AI and returns the extracted content.
        Uses the default markdown generator to keep the format structured for LLMs.
        """
        print(f"Starting crawl for: {url}")
        
        config = CrawlerRunConfig(
            markdown_generator=DefaultMarkdownGenerator()
        )
        
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(
                url=url,
                config=config
            )
            
            if not result.success:
                print(f"Failed to crawl {url}: {result.error_message}")
                return {"success": False, "error": result.error_message}
                
            # We want to export this immediately to llms.txt format as a raw knowledge dump
            
            raw_markdown = result.markdown.raw_markdown if hasattr(result.markdown, 'raw_markdown') else result.markdown
            
            self._export_to_llms_txt(url, raw_markdown)
            
            return {
                "success": True,
                "url": url,
                "markdown": raw_markdown,
                "title": result.metadata.get('title', 'Untitled') if result.metadata else 'Untitled'
            }
            
    def _export_to_llms_txt(self, url: str, content: str):
        """
        Exports the crawled markdown content to the local output directory.
        The filename is derived from the URL.
        """
        # Create a simple safe filename
        safe_name = "".join([c if c.isalnum() else "_" for c in url]).strip("_")
        # Truncate to avoid extremely long filenames
        safe_name = safe_name[:50]
        
        file_path = self.output_dir / f"{safe_name}_llms.txt"
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# Source: {url}\n\n")
                f.write(content)
            print(f"Successfully exported knowledge to {file_path}")
        except Exception as e:
            print(f"Failed to export knowledge to {file_path}: {e}")

# Simple routine for direct testing
if __name__ == "__main__":
    crawler = MreCrawler()
    asyncio.run(crawler.crawl_url("https://crawl4ai.com"))
