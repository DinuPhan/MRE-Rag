import asyncio
from typing import List, Dict, Any
from crawler import MreCrawler
from embeddings import EmbeddingManager
from qdrant_manager import QdrantManager

class RagPipeline:
    def __init__(self):
        """
        Orchestrates Crawler, Embeddings, and Vector Store.
        """
        self.crawler = MreCrawler()
        self.embeddings = EmbeddingManager()
        self.qdrant = QdrantManager(vector_size=self.embeddings.dimension)

    def chunk_text(self, text: str, chunk_size: int = 1500) -> List[str]:
        """
        Naive chunking function for text.
        Splits by characters but tries to respect paragraphs where possible.
        """
        chunks = []
        paragraphs = text.split("\n\n")
        current_chunk = ""
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) <= chunk_size:
                current_chunk += paragraph + "\n\n"
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + "\n\n"
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
            
        return chunks

    async def ingest_url(self, url: str, max_depth: int = 0, max_pages: int = 10) -> dict:
        """
        Crawls a URL (or sitemap/.txt), chunks the content from all pages, embeds them, and saves to Qdrant.
        """
        # 1. Crawl
        crawl_results = await self.crawler.crawl_urls(url, max_depth=max_depth, max_pages=max_pages)
        if not crawl_results:
            return {"success": False, "error": "No pages were successfully crawled."}
            
        all_chunks = []
        all_metadatas = []
        
        # 2. Chunk
        for crawl_result in crawl_results:
            markdown = crawl_result["markdown"]
            page_url = crawl_result["url"]
            title = crawl_result["title"]
            
            chunks = self.chunk_text(markdown)
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metadatas.append({
                    "url": page_url,
                    "title": title,
                    "chunk_index": i
                })
                
        if not all_chunks:
            return {"success": False, "error": "No text extracted to chunk from any page."}
            
        print(f"Extracted {len(all_chunks)} chunks from {len(crawl_results)} pages.")
        
        # 3. Embed (in batches to avoid overwhelming the Embedding API payload limits)
        vectors = []
        try:
            batch_size = 100
            for i in range(0, len(all_chunks), batch_size):
                batch_chunks = all_chunks[i:i + batch_size]
                batch_vectors = self.embeddings.create_embeddings_batch(batch_chunks)
                vectors.extend(batch_vectors)
        except Exception as e:
            return {"success": False, "error": f"Embedding generator failed: {str(e)}"}
            
        # 4. Insert
        # We group all sub-pages under the collection name of the initial target URL
        collection_name = QdrantManager.escape_url(url)
        self.qdrant.upsert_knowledge_chunks(collection_name, all_chunks, vectors, all_metadatas)
        
        return {
            "success": True,
            "message": f"Successfully ingested {len(crawl_results)} pages into Qdrant collection '{collection_name}'.",
            "chunks_processed": len(all_chunks),
            "pages_processed": len(crawl_results)
        }

    def query(self, text: str, url: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Queries the Qdrant database using Gemini embedding on the query.
        """
        try:
            query_vector = self.embeddings.create_embedding(text)
            if url:
                collection_name = QdrantManager.escape_url(url)
                return self.qdrant.search(collection_name, query_vector=query_vector, limit=limit)
            else:
                return self.qdrant.search_all(query_vector=query_vector, limit=limit)
        except Exception as e:
            print(f"Query Error: {e}")
            return []

if __name__ == "__main__":
    pipeline = RagPipeline()
    query_text = "What is this document about?"
    results = pipeline.query(query_text)
    print("Test Query Result: ", results)
